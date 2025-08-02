"""
RDA Automation System - Retry Manager Module

This module provides automatic retry functionality for purged requests in the RDA automation system.
It takes resubmission data from the error manager and automatically resubmits purged requests with
intelligent scheduling, exponential backoff, and comprehensive metrics tracking.

Key Features:
- Automatic retry processing for purged requests
- Intelligent retry scheduling with exponential backoff and jitter
- Integration with existing batch automation and queue management
- Comprehensive retry metrics and success rate tracking
- Database integration for retry attempt logging
- Configurable retry strategies and limits
"""

import sqlite3
import logging
import json
import time
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import existing modules for integration
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.error_manager import ErrorManager, create_error_manager
from batch_automation import BatchAutomationSystem, RequestStatus
from batch_queue_manager import IntelligentQueueManager, QueuedRequest, Priority


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retry_attempts: int = 5
    base_delay_seconds: int = 60
    max_delay_seconds: int = 3600
    exponential_base: float = 2.0
    jitter_factor: float = 0.1
    batch_size: int = 3
    retry_timeout_hours: int = 24
    success_rate_threshold: float = 0.7
    enabled: bool = True


@dataclass
class RetryAttempt:
    """Data class representing a retry attempt."""
    id: Optional[int] = None
    original_request_id: int = None
    session_id: str = None
    file_path: str = None
    region: str = None
    parameter: str = None
    attempt_number: int = 1
    scheduled_time: str = None
    attempted_time: Optional[str] = None
    completed_time: Optional[str] = None
    status: str = "scheduled"  # scheduled, attempted, completed, failed, expired
    new_request_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_delay_seconds: int = 60


@dataclass
class RetryMetrics:
    """Metrics for retry operations."""
    total_retries_attempted: int = 0
    total_retries_successful: int = 0
    total_retries_failed: int = 0
    average_retry_delay: float = 0.0
    success_rate: float = 0.0
    last_updated: str = None


class RetryManager:
    """
    Manages automatic retry functionality for purged requests.
    
    This class provides functionality to:
    - Process resubmission data from the error manager
    - Schedule retries with intelligent timing
    - Resubmit requests using existing batch automation
    - Track retry metrics and success rates
    - Integrate with queue management for optimal scheduling
    """
    
    def __init__(self, db_path: str, batch_system: Optional[BatchAutomationSystem] = None,
                 queue_manager: Optional[IntelligentQueueManager] = None,
                 config: Optional[RetryConfig] = None):
        """
        Initialize the RetryManager.
        
        Args:
            db_path: Path to the SQLite database file
            batch_system: Optional BatchAutomationSystem instance
            queue_manager: Optional IntelligentQueueManager instance
            config: Configuration for retry behavior (uses defaults if None)
        """
        self.db_path = db_path
        self.config = config or RetryConfig()
        self.logger = self._setup_logging()
        
        # Initialize or use provided systems
        self.batch_system = batch_system or BatchAutomationSystem()
        self.queue_manager = queue_manager or IntelligentQueueManager(self.batch_system)
        
        # Threading for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.retry_lock = threading.Lock()
        
        # Initialize database tables
        self._initialize_database()
        
        self.logger.info("RetryManager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the retry manager."""
        logger = logging.getLogger('rda_automation.retry_manager')
        
        # Only add handler if it doesn't already exist
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self):
        """Initialize database tables for retry tracking."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Create retry_attempts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retry_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_request_id INTEGER NOT NULL,
                        session_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        region TEXT NOT NULL,
                        parameter TEXT NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        scheduled_time TEXT NOT NULL,
                        attempted_time TEXT,
                        completed_time TEXT,
                        status TEXT NOT NULL DEFAULT 'scheduled',
                        new_request_id TEXT,
                        error_message TEXT,
                        retry_delay_seconds INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create retry_metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS retry_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        total_retries_attempted INTEGER DEFAULT 0,
                        total_retries_successful INTEGER DEFAULT 0,
                        total_retries_failed INTEGER DEFAULT 0,
                        average_retry_delay REAL DEFAULT 0.0,
                        success_rate REAL DEFAULT 0.0,
                        last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_attempts_status 
                    ON retry_attempts(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_attempts_scheduled_time 
                    ON retry_attempts(scheduled_time)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_attempts_session 
                    ON retry_attempts(session_id)
                """)
                
                conn.commit()
                self.logger.info("Database tables initialized successfully")
                
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise
    
    def calculate_retry_delay(self, attempt_number: int) -> int:
        """
        Calculate retry delay using exponential backoff with jitter.
        
        Args:
            attempt_number: The retry attempt number (1-based)
            
        Returns:
            Delay in seconds before next retry
        """
        if attempt_number <= 0:
            attempt_number = 1
        
        # Exponential backoff: base_delay * (exponential_base ^ (attempt - 1))
        exponential_delay = self.config.base_delay_seconds * (
            self.config.exponential_base ** (attempt_number - 1)
        )
        
        # Cap at maximum delay
        exponential_delay = min(exponential_delay, self.config.max_delay_seconds)
        
        # Add jitter to avoid thundering herd
        jitter_range = exponential_delay * self.config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)
        
        final_delay = max(self.config.base_delay_seconds, exponential_delay + jitter)
        
        # Ensure we don't exceed the maximum delay
        final_delay = min(final_delay, self.config.max_delay_seconds)
        
        self.logger.debug(f"Calculated retry delay for attempt {attempt_number}: {final_delay:.1f}s")
        return int(final_delay)
    
    def schedule_retry(self, resubmission_data: Dict[str, Any], attempt_number: int = 1) -> Optional[RetryAttempt]:
        """
        Schedule a retry for a purged request.
        
        Args:
            resubmission_data: Data from error manager's prepare_for_resubmission
            attempt_number: The retry attempt number
            
        Returns:
            RetryAttempt object if scheduled successfully, None otherwise
        """
        try:
            if not self.config.enabled:
                self.logger.info("Retry scheduling is disabled")
                return None
            
            if attempt_number > self.config.max_retry_attempts:
                self.logger.warning(f"Attempt number {attempt_number} exceeds max retries {self.config.max_retry_attempts}")
                return None
            
            # Calculate delay and scheduled time
            delay_seconds = self.calculate_retry_delay(attempt_number)
            scheduled_time = datetime.now() + timedelta(seconds=delay_seconds)
            
            # Create retry attempt
            retry_attempt = RetryAttempt(
                original_request_id=resubmission_data['original_id'],
                session_id=resubmission_data['session_id'],
                file_path=resubmission_data['file_path'],
                region=resubmission_data['region'],
                parameter=resubmission_data['parameter'],
                attempt_number=attempt_number,
                scheduled_time=scheduled_time.isoformat(),
                status="scheduled",
                retry_delay_seconds=delay_seconds
            )
            
            # Save to database
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO retry_attempts (
                        original_request_id, session_id, file_path, region, parameter,
                        attempt_number, scheduled_time, status, retry_delay_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    retry_attempt.original_request_id,
                    retry_attempt.session_id,
                    retry_attempt.file_path,
                    retry_attempt.region,
                    retry_attempt.parameter,
                    retry_attempt.attempt_number,
                    retry_attempt.scheduled_time,
                    retry_attempt.status,
                    retry_attempt.retry_delay_seconds
                ))
                
                retry_attempt.id = cursor.lastrowid
                conn.commit()
            
            self.logger.info(f"Scheduled retry {retry_attempt.id} for {retry_attempt.region}_{retry_attempt.parameter} "
                           f"(attempt {attempt_number}, delay {delay_seconds}s)")
            
            return retry_attempt
            
        except Exception as e:
            self.logger.error(f"Error scheduling retry: {e}")
            return None
    
    def get_ready_retries(self) -> List[RetryAttempt]:
        """
        Get retry attempts that are ready to be processed.
        
        Returns:
            List of RetryAttempt objects ready for processing
        """
        try:
            current_time = datetime.now().isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM retry_attempts 
                    WHERE status = 'scheduled' 
                    AND scheduled_time <= ?
                    ORDER BY scheduled_time ASC
                    LIMIT ?
                """, (current_time, self.config.batch_size))
                
                rows = cursor.fetchall()
                
            ready_retries = []
            for row in rows:
                retry_attempt = RetryAttempt(
                    id=row['id'],
                    original_request_id=row['original_request_id'],
                    session_id=row['session_id'],
                    file_path=row['file_path'],
                    region=row['region'],
                    parameter=row['parameter'],
                    attempt_number=row['attempt_number'],
                    scheduled_time=row['scheduled_time'],
                    attempted_time=row['attempted_time'],
                    completed_time=row['completed_time'],
                    status=row['status'],
                    new_request_id=row['new_request_id'],
                    error_message=row['error_message'],
                    retry_delay_seconds=row['retry_delay_seconds']
                )
                ready_retries.append(retry_attempt)
            
            if ready_retries:
                self.logger.info(f"Found {len(ready_retries)} retry attempts ready for processing")
            
            return ready_retries
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting ready retries: {e}")
            return []
    
    def resubmit_request(self, retry_attempt: RetryAttempt) -> bool:
        """
        Resubmit a single request to the RDA system.
        
        Args:
            retry_attempt: RetryAttempt object to process
            
        Returns:
            True if resubmission was successful, False otherwise
        """
        try:
            with self.retry_lock:
                # Update status to attempted
                self._update_retry_status(retry_attempt.id, "attempted", 
                                        attempted_time=datetime.now().isoformat())
            
            self.logger.info(f"Resubmitting retry {retry_attempt.id}: {retry_attempt.region}_{retry_attempt.parameter} "
                           f"(attempt {retry_attempt.attempt_number})")
            
            # Use batch system to submit the request
            success = self.batch_system.submit_request(retry_attempt.file_path)
            
            if success:
                # Get the new request ID from batch system
                request_status = self.batch_system.requests_state.get(retry_attempt.file_path)
                new_request_id = request_status.request_id if request_status else None
                
                with self.retry_lock:
                    self._update_retry_status(
                        retry_attempt.id, "completed",
                        completed_time=datetime.now().isoformat(),
                        new_request_id=new_request_id
                    )
                
                self.logger.info(f"Successfully resubmitted retry {retry_attempt.id} -> New Request ID: {new_request_id}")
                
                # Add to queue manager for monitoring
                if self.queue_manager:
                    queued_request = self.queue_manager.analyze_control_file(retry_attempt.file_path)
                    queued_request.priority = Priority.HIGH  # Give retries higher priority
                    self.queue_manager.add_to_queue([retry_attempt.file_path])
                
                return True
            else:
                error_msg = "Batch system submission failed"
                with self.retry_lock:
                    self._update_retry_status(retry_attempt.id, "failed", error_message=error_msg)
                
                self.logger.error(f"Failed to resubmit retry {retry_attempt.id}: {error_msg}")
                return False
                
        except Exception as e:
            error_msg = f"Exception during resubmission: {e}"
            with self.retry_lock:
                self._update_retry_status(retry_attempt.id, "failed", error_message=error_msg)
            
            self.logger.error(f"Error resubmitting retry {retry_attempt.id}: {e}")
            return False
    
    def _update_retry_status(self, retry_id: int, status: str, **kwargs):
        """Update retry attempt status in database."""
        try:
            update_fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            update_values = [status]
            
            for field, value in kwargs.items():
                if value is not None:
                    update_fields.append(f"{field} = ?")
                    update_values.append(value)
            
            update_values.append(retry_id)
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE retry_attempts 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """, update_values)
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating retry status: {e}")
    
    def process_retry_requests(self, resubmission_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main function to process retry requests from resubmission data.
        
        Args:
            resubmission_data_list: List of resubmission data from error manager
            
        Returns:
            Dictionary containing processing results and statistics
        """
        if not self.config.enabled:
            self.logger.info("Retry processing is disabled")
            return {"processed": 0, "scheduled": 0, "errors": 0}
        
        self.logger.info(f"Processing {len(resubmission_data_list)} retry requests")
        
        scheduled_count = 0
        error_count = 0
        
        # Schedule new retries
        for resubmission_data in resubmission_data_list:
            try:
                retry_attempt = self.schedule_retry(resubmission_data)
                if retry_attempt:
                    scheduled_count += 1
                else:
                    error_count += 1
            except Exception as e:
                self.logger.error(f"Error processing resubmission data: {e}")
                error_count += 1
        
        # Process ready retries
        ready_retries = self.get_ready_retries()
        processed_count = 0
        
        if ready_retries:
            self.logger.info(f"Processing {len(ready_retries)} ready retry attempts")
            
            # Process retries concurrently
            futures = []
            for retry_attempt in ready_retries:
                future = self.executor.submit(self.resubmit_request, retry_attempt)
                futures.append((future, retry_attempt))
            
            # Collect results
            for future, retry_attempt in futures:
                try:
                    success = future.result(timeout=300)  # 5 minute timeout
                    if success:
                        processed_count += 1
                    else:
                        # Schedule next retry if not exceeded max attempts
                        if retry_attempt.attempt_number < self.config.max_retry_attempts:
                            next_resubmission_data = {
                                'original_id': retry_attempt.original_request_id,
                                'session_id': retry_attempt.session_id,
                                'file_path': retry_attempt.file_path,
                                'region': retry_attempt.region,
                                'parameter': retry_attempt.parameter
                            }
                            self.schedule_retry(next_resubmission_data, retry_attempt.attempt_number + 1)
                        
                except Exception as e:
                    self.logger.error(f"Error processing retry future: {e}")
                    error_count += 1
        
        # Update metrics
        self._update_retry_metrics()
        
        result = {
            "processed": processed_count,
            "scheduled": scheduled_count,
            "ready_retries": len(ready_retries),
            "errors": error_count,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"Retry processing completed: {result}")
        return result
    
    def track_retry_metrics(self, session_id: Optional[str] = None) -> RetryMetrics:
        """
        Track and calculate retry metrics.
        
        Args:
            session_id: Optional session ID to limit metrics to specific session
            
        Returns:
            RetryMetrics object with current statistics
        """
        try:
            query = """
                SELECT 
                    COUNT(*) as total_attempted,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
                    AVG(retry_delay_seconds) as avg_delay
                FROM retry_attempts
            """
            params = []
            
            if session_id:
                query += " WHERE session_id = ?"
                params.append(session_id)
            
            with self._get_db_connection() as conn:
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                
                total_attempted = row['total_attempted'] or 0
                successful = row['successful'] or 0
                failed = row['failed'] or 0
                avg_delay = row['avg_delay'] or 0.0
                
                success_rate = (successful / total_attempted) if total_attempted > 0 else 0.0
                
                metrics = RetryMetrics(
                    total_retries_attempted=total_attempted,
                    total_retries_successful=successful,
                    total_retries_failed=failed,
                    average_retry_delay=avg_delay,
                    success_rate=success_rate,
                    last_updated=datetime.now().isoformat()
                )
                
                return metrics
                
        except sqlite3.Error as e:
            self.logger.error(f"Error calculating retry metrics: {e}")
            return RetryMetrics()
    
    def _update_retry_metrics(self, session_id: Optional[str] = None):
        """Update retry metrics in database."""
        try:
            metrics = self.track_retry_metrics(session_id)
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Insert or update metrics
                cursor.execute("""
                    INSERT OR REPLACE INTO retry_metrics (
                        session_id, total_retries_attempted, total_retries_successful,
                        total_retries_failed, average_retry_delay, success_rate, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    metrics.total_retries_attempted,
                    metrics.total_retries_successful,
                    metrics.total_retries_failed,
                    metrics.average_retry_delay,
                    metrics.success_rate,
                    metrics.last_updated
                ))
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating retry metrics: {e}")
    
    def get_retry_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive retry statistics.
        
        Args:
            session_id: Optional session ID to limit statistics to specific session
            
        Returns:
            Dictionary containing detailed retry statistics
        """
        try:
            metrics = self.track_retry_metrics(session_id)
            
            # Get status distribution
            status_query = """
                SELECT status, COUNT(*) as count
                FROM retry_attempts
            """
            params = []
            
            if session_id:
                status_query += " WHERE session_id = ?"
                params.append(session_id)
            
            status_query += " GROUP BY status"
            
            with self._get_db_connection() as conn:
                cursor = conn.execute(status_query, params)
                status_distribution = {row['status']: row['count'] for row in cursor.fetchall()}
                
                # Get recent activity (last 24 hours)
                recent_query = """
                    SELECT COUNT(*) as recent_count
                    FROM retry_attempts
                    WHERE created_at >= datetime('now', '-24 hours')
                """
                if session_id:
                    recent_query += " AND session_id = ?"
                
                cursor = conn.execute(recent_query, params)
                recent_activity = cursor.fetchone()['recent_count']
            
            return {
                'metrics': asdict(metrics),
                'status_distribution': status_distribution,
                'recent_activity_24h': recent_activity,
                'config': asdict(self.config),
                'session_id': session_id,
                'generated_at': datetime.now().isoformat()
            }
            
        except sqlite3.Error as e:
            self.logger.error(f"Error getting retry statistics: {e}")
            return {}
    
    def cleanup_expired_retries(self) -> int:
        """
        Clean up expired retry attempts that are beyond the timeout window.
        
        Returns:
            Number of expired retries cleaned up
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.config.retry_timeout_hours)
            cutoff_time_str = cutoff_time.isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Mark expired scheduled retries as expired
                cursor.execute("""
                    UPDATE retry_attempts 
                    SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'scheduled' 
                    AND scheduled_time < ?
                """, (cutoff_time_str,))
                
                expired_count = cursor.rowcount
                conn.commit()
                
                if expired_count > 0:
                    self.logger.info(f"Marked {expired_count} retry attempts as expired")
                
                return expired_count
                
        except sqlite3.Error as e:
            self.logger.error(f"Error cleaning up expired retries: {e}")
            return 0


def create_unified_error_retry_workflow(db_path: str = "src/python/data/automation_state.db",
                                      batch_system: Optional[BatchAutomationSystem] = None,
                                      queue_manager: Optional[IntelligentQueueManager] = None,
                                      session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Unified workflow function that combines error detection, purging, and retry functionality.
    
    Args:
        db_path: Path to the SQLite database file
        batch_system: Optional BatchAutomationSystem instance
        queue_manager: Optional IntelligentQueueManager instance
        session_id: Optional session ID to limit processing to specific session
        
    Returns:
        Dictionary containing comprehensive workflow results
    """
    logger = logging.getLogger('rda_automation.unified_workflow')
    logger.info("Starting unified error detection and retry workflow")
    
    try:
        # Initialize components
        error_manager = create_error_manager(db_path)
        retry_manager = RetryManager(db_path, batch_system, queue_manager)
        
        # Step 1: Detect and purge error requests
        logger.info("Step 1: Detecting and purging error requests")
        purge_result = error_manager.auto_purge_session(session_id) if session_id else {}
        
        if not session_id:
            # Process all sessions if no specific session provided
            candidates = error_manager.get_purge_candidates()
            if candidates:
                purged_count, resubmission_data = error_manager.purge_error_requests(candidates)
                purge_result = {
                    'purged_count': purged_count,
                    'resubmission_data': resubmission_data,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                purge_result = {
                    'purged_count': 0,
                    'resubmission_data': [],
                    'timestamp': datetime.now().isoformat()
                }
        
        # Step 2: Process retry requests
        logger.info("Step 2: Processing retry requests")
        resubmission_data = purge_result.get('resubmission_data', [])
        retry_result = retry_manager.process_retry_requests(resubmission_data)
        
        # Step 3: Clean up expired retries
        logger.info("Step 3: Cleaning up expired retries")
        expired_count = retry_manager.cleanup_expired_retries()
        
        # Step 4: Generate comprehensive statistics
        logger.info("Step 4: Generating statistics")
        error_stats = error_manager.get_error_statistics(session_id)
        retry_stats = retry_manager.get_retry_statistics(session_id)
        
        # Compile unified results
        unified_result = {
            'workflow_completed': True,
            'session_id': session_id,
            'purge_results': purge_result,
            'retry_results': retry_result,
            'expired_cleanup': expired_count,
            'error_statistics': error_stats,
            'retry_statistics': retry_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Unified workflow completed successfully: "
                   f"Purged {purge_result.get('purged_count', 0)} requests, "
                   f"Processed {retry_result.get('processed', 0)} retries, "
                   f"Cleaned up {expired_count} expired retries")
        
        return unified_result
        
    except Exception as e:
        logger.error(f"Error in unified workflow: {e}")
        return {
            'workflow_completed': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def create_retry_manager(db_path: str = "src/python/data/automation_state.db",
                        batch_system: Optional[BatchAutomationSystem] = None,
                        queue_manager: Optional[IntelligentQueueManager] = None,
                        max_retry_attempts: int = 5,
                        base_delay_seconds: int = 60) -> RetryManager:
    """
    Factory function to create a RetryManager with common configuration.
    
    Args:
        db_path: Path to the SQLite database file
        batch_system: Optional BatchAutomationSystem instance
        queue_manager: Optional IntelligentQueueManager instance
        max_retry_attempts: Maximum number of retry attempts
        base_delay_seconds: Base delay between retries
        
    Returns:
        Configured RetryManager instance
    """
    config = RetryConfig(
        max_retry_attempts=max_retry_attempts,
        base_delay_seconds=base_delay_seconds
    )
    return RetryManager(db_path, batch_system, queue_manager, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='RDA Retry Manager')
    parser.add_argument('--test-workflow', action='store_true',
                       help='Test the unified error detection and retry workflow')
    parser.add_argument('--session-id', type=str,
                       help='Session ID to process (optional)')
    parser.add_argument('--stats', action='store_true',
                       help='Show retry statistics')
    
    args = parser.parse_args()
    
    if args.test_workflow:
        print("=== Testing Unified Error Detection and Retry Workflow ===")
        result = create_unified_error_retry_workflow(session_id=args.session_id)
        print(json.dumps(result, indent=2))
    
    elif args.stats:
        print("=== Retry Statistics ===")
        retry_manager = create_retry_manager()
        stats = retry_manager.get_retry_statistics(args.session_id)