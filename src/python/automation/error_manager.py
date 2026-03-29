"""
RDA Automation System - Error Manager Module

This module provides automatic error detection and purging functionality for the RDA automation system.
It identifies failed requests that meet specific criteria and provides mechanisms to purge them from
the database while maintaining an audit trail.

Key Features:
- Automatic detection of failed requests based on configurable criteria
- Purging of persistent errors that exceed retry limits
- Audit logging of all purging activities
- Preparation of purged requests for resubmission
- Support for various error patterns and age-based purging
"""

import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from logger_utils import get_logger


@dataclass
class ErrorRequest:
    """Data class representing a failed request that may be purged."""
    id: int
    session_id: str
    file_path: str
    region: str
    parameter: str
    status: str
    request_id: Optional[str]
    submitted_at: Optional[str]
    completed_at: Optional[str]
    download_path: Optional[str]
    error_message: Optional[str]
    retry_count: int


@dataclass
class PurgeConfig:
    """Configuration for error purging criteria."""
    max_retries: int = 3
    max_age_hours: int = 24
    error_patterns: List[str] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.error_patterns is None:
            self.error_patterns = [
                "HTTP 400: Unknown error",
                "HTTP 500: Internal Server Error",
                "Connection timeout",
                "Request timeout"
            ]


class ErrorManager:
    """
    Manages automatic error detection and purging for the RDA automation system.
    
    This class provides functionality to:
    - Detect failed requests that meet purging criteria
    - Purge persistent errors from the database
    - Log all purging activities for audit purposes
    - Prepare purged requests for potential resubmission
    """
    
    def __init__(self, db_path: str, config: Optional[PurgeConfig] = None):
        """
        Initialize the ErrorManager.
        
        Args:
            db_path: Path to the SQLite database file
            config: Configuration for purging criteria (uses defaults if None)
        """
        self.db_path = db_path
        self.config = config or PurgeConfig()
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.error_manager', level=logging.INFO)
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def detect_error_requests(self, session_id: Optional[str] = None) -> List[ErrorRequest]:
        """
        Detect requests that meet the purging criteria.
        
        Args:
            session_id: Optional session ID to limit detection to specific session
            
        Returns:
            List of ErrorRequest objects that meet purging criteria
        """
        if not self.config.enabled:
            self.logger.info("Error detection is disabled in configuration")
            return []
            
        query = """
        SELECT id, session_id, file_path, region, parameter, status, request_id,
               submitted_at, completed_at, download_path, error_message, retry_count
        FROM file_status 
        WHERE status = 'failed'
        """
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
            
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
            error_requests = []
            for row in rows:
                error_request = ErrorRequest(
                    id=row['id'],
                    session_id=row['session_id'],
                    file_path=row['file_path'],
                    region=row['region'],
                    parameter=row['parameter'],
                    status=row['status'],
                    request_id=row['request_id'],
                    submitted_at=row['submitted_at'],
                    completed_at=row['completed_at'],
                    download_path=row['download_path'],
                    error_message=row['error_message'],
                    retry_count=row['retry_count']
                )
                error_requests.append(error_request)
                
            self.logger.info(f"Detected {len(error_requests)} failed requests")
            return error_requests
            
        except sqlite3.Error as e:
            self.logger.error(f"Database error while detecting error requests: {e}")
            return []
    
    def get_purge_candidates(self, session_id: Optional[str] = None) -> List[ErrorRequest]:
        """
        Get list of requests that should be purged based on configured criteria.
        
        Args:
            session_id: Optional session ID to limit candidates to specific session
            
        Returns:
            List of ErrorRequest objects that meet purging criteria
        """
        error_requests = self.detect_error_requests(session_id)
        purge_candidates = []
        
        current_time = datetime.now()
        
        for request in error_requests:
            should_purge = False
            purge_reasons = []
            
            # Check retry count criteria
            if request.retry_count >= self.config.max_retries:
                should_purge = True
                purge_reasons.append(f"retry_count ({request.retry_count}) >= max_retries ({self.config.max_retries})")
            
            # Check error pattern criteria
            if request.error_message:
                for pattern in self.config.error_patterns:
                    if pattern in request.error_message:
                        should_purge = True
                        purge_reasons.append(f"error_pattern_match: '{pattern}'")
                        break
            
            # Check age criteria
            if request.submitted_at:
                try:
                    submitted_time = datetime.fromisoformat(request.submitted_at.replace('Z', '+00:00'))
                    age_hours = (current_time - submitted_time.replace(tzinfo=None)).total_seconds() / 3600
                    if age_hours > self.config.max_age_hours:
                        should_purge = True
                        purge_reasons.append(f"age ({age_hours:.1f}h) > max_age ({self.config.max_age_hours}h)")
                except (ValueError, AttributeError) as e:
                    self.logger.warning(f"Could not parse submitted_at time for request {request.id}: {e}")
            
            if should_purge:
                self.logger.info(f"Request {request.id} ({request.region}_{request.parameter}) marked for purging: {', '.join(purge_reasons)}")
                purge_candidates.append(request)
        
        self.logger.info(f"Found {len(purge_candidates)} requests meeting purge criteria")
        return purge_candidates
    
    def prepare_for_resubmission(self, error_requests: List[ErrorRequest]) -> List[Dict[str, Any]]:
        """
        Prepare purged requests for resubmission by extracting relevant details.
        
        Args:
            error_requests: List of ErrorRequest objects to prepare
            
        Returns:
            List of dictionaries containing request details for resubmission
        """
        resubmission_data = []
        
        for request in error_requests:
            request_data = {
                'original_id': request.id,
                'session_id': request.session_id,
                'file_path': request.file_path,
                'region': request.region,
                'parameter': request.parameter,
                'original_error': request.error_message,
                'retry_count': request.retry_count,
                'purged_at': datetime.now().isoformat(),
                'resubmission_ready': True
            }
            resubmission_data.append(request_data)
        
        self.logger.info(f"Prepared {len(resubmission_data)} requests for resubmission")
        return resubmission_data
    
    def purge_error_requests(self, error_requests: List[ErrorRequest], 
                           create_backup: bool = True) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Purge failed requests from the database.
        
        Args:
            error_requests: List of ErrorRequest objects to purge
            create_backup: Whether to create backup data for resubmission
            
        Returns:
            Tuple of (number_purged, resubmission_data)
        """
        if not error_requests:
            self.logger.info("No error requests to purge")
            return 0, []
        
        # Prepare resubmission data before purging if requested
        resubmission_data = []
        if create_backup:
            resubmission_data = self.prepare_for_resubmission(error_requests)
        
        purged_count = 0
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                for request in error_requests:
                    # Log the purging action
                    self.logger.info(
                        f"Purging request {request.id}: {request.region}_{request.parameter} "
                        f"(session: {request.session_id}, retries: {request.retry_count}, "
                        f"error: {request.error_message})"
                    )
                    
                    # Delete the request from the database
                    cursor.execute("DELETE FROM file_status WHERE id = ?", (request.id,))
                    
                    if cursor.rowcount > 0:
                        purged_count += 1
                        self.logger.info(f"Successfully purged request {request.id}")
                    else:
                        self.logger.warning(f"Request {request.id} was not found in database")
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while purging requests: {e}")
            return 0, []
        
        self.logger.info(f"Successfully purged {purged_count} error requests")
        
        # Log purging summary for audit trail
        self._log_purge_audit(error_requests, purged_count)
        
        return purged_count, resubmission_data
    
    def _log_purge_audit(self, purged_requests: List[ErrorRequest], purged_count: int):
        """
        Log detailed audit information about the purging operation.
        
        Args:
            purged_requests: List of requests that were purged
            purged_count: Number of requests actually purged
        """
        audit_data = {
            'timestamp': datetime.now().isoformat(),
            'operation': 'purge_error_requests',
            'total_candidates': len(purged_requests),
            'successfully_purged': purged_count,
            'config': {
                'max_retries': self.config.max_retries,
                'max_age_hours': self.config.max_age_hours,
                'error_patterns': self.config.error_patterns
            },
            'purged_requests': [
                {
                    'id': req.id,
                    'session_id': req.session_id,
                    'region': req.region,
                    'parameter': req.parameter,
                    'error_message': req.error_message,
                    'retry_count': req.retry_count,
                    'file_path': req.file_path
                }
                for req in purged_requests
            ]
        }
        
        self.logger.info(f"AUDIT: Purge operation completed - {json.dumps(audit_data, indent=2)}")
    
    def get_error_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about error requests in the database.
        
        Args:
            session_id: Optional session ID to limit statistics to specific session
            
        Returns:
            Dictionary containing error statistics
        """
        query_base = """
        SELECT 
            COUNT(*) as total_failed,
            COUNT(CASE WHEN retry_count >= ? THEN 1 END) as exceeded_retries,
            AVG(retry_count) as avg_retry_count,
            MAX(retry_count) as max_retry_count
        FROM file_status 
        WHERE status = 'failed'
        """
        
        params = [self.config.max_retries]
        
        if session_id:
            query_base += " AND session_id = ?"
            params.append(session_id)
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute(query_base, params)
                stats = cursor.fetchone()
                
                # Get error pattern statistics
                pattern_stats = {}
                for pattern in self.config.error_patterns:
                    pattern_query = query_base.replace("WHERE status = 'failed'", 
                                                     "WHERE status = 'failed' AND error_message LIKE ?")
                    pattern_params = params.copy()
                    pattern_params.insert(-1 if session_id else 0, f"%{pattern}%")
                    
                    cursor = conn.execute(pattern_query, pattern_params)
                    pattern_result = cursor.fetchone()
                    pattern_stats[pattern] = pattern_result['total_failed'] if pattern_result else 0
                
                return {
                    'total_failed_requests': stats['total_failed'] if stats else 0,
                    'requests_exceeding_retries': stats['exceeded_retries'] if stats else 0,
                    'average_retry_count': round(stats['avg_retry_count'], 2) if stats and stats['avg_retry_count'] else 0,
                    'max_retry_count': stats['max_retry_count'] if stats else 0,
                    'error_pattern_counts': pattern_stats,
                    'session_id': session_id,
                    'generated_at': datetime.now().isoformat()
                }
                
        except sqlite3.Error as e:
            self.logger.error(f"Database error while getting error statistics: {e}")
            return {}
    
    def auto_purge_session(self, session_id: str) -> Dict[str, Any]:
        """
        Automatically purge all eligible error requests for a specific session.
        
        Args:
            session_id: Session ID to purge errors for
            
        Returns:
            Dictionary containing purge results and statistics
        """
        self.logger.info(f"Starting auto-purge for session: {session_id}")
        
        # Get statistics before purging
        pre_stats = self.get_error_statistics(session_id)
        
        # Get purge candidates
        candidates = self.get_purge_candidates(session_id)
        
        if not candidates:
            self.logger.info(f"No purge candidates found for session {session_id}")
            return {
                'session_id': session_id,
                'purged_count': 0,
                'resubmission_data': [],
                'pre_purge_stats': pre_stats,
                'post_purge_stats': pre_stats,
                'timestamp': datetime.now().isoformat()
            }
        
        # Perform purging
        purged_count, resubmission_data = self.purge_error_requests(candidates)
        
        # Get statistics after purging
        post_stats = self.get_error_statistics(session_id)
        
        result = {
            'session_id': session_id,
            'purged_count': purged_count,
            'candidate_count': len(candidates),
            'resubmission_data': resubmission_data,
            'pre_purge_stats': pre_stats,
            'post_purge_stats': post_stats,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info(f"Auto-purge completed for session {session_id}: {purged_count} requests purged")
        return result


def create_error_manager(db_path: str = "data/automation_state.db",
                        max_retries: int = 3,
                        max_age_hours: int = 24) -> ErrorManager:
    """
    Factory function to create an ErrorManager with common configuration.
    
    Args:
        db_path: Path to the SQLite database file
        max_retries: Maximum retry count before purging
        max_age_hours: Maximum age in hours before purging
        
    Returns:
        Configured ErrorManager instance
    """
    config = PurgeConfig(
        max_retries=max_retries,
        max_age_hours=max_age_hours
    )
    return ErrorManager(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    # Create error manager with default configuration
    error_manager = create_error_manager()
    
    # Get error statistics
    print("=== Error Statistics ===")
    stats = error_manager.get_error_statistics()
    print(json.dumps(stats, indent=2))
    
    # Detect error requests
    print("\n=== Detecting Error Requests ===")
    error_requests = error_manager.detect_error_requests()
    print(f"Found {len(error_requests)} failed requests")
    
    # Get purge candidates
    print("\n=== Purge Candidates ===")
    candidates = error_manager.get_purge_candidates()
    print(f"Found {len(candidates)} requests meeting purge criteria")
    
    for candidate in candidates:
        print(f"  - {candidate.region}_{candidate.parameter} (retries: {candidate.retry_count}, error: {candidate.error_message})")
    
    # Ask for confirmation before purging
    if candidates and len(sys.argv) > 1 and sys.argv[1] == "--purge":
        print(f"\n=== Purging {len(candidates)} Requests ===")
        purged_count, resubmission_data = error_manager.purge_error_requests(candidates)
        print(f"Successfully purged {purged_count} requests")
        print(f"Prepared {len(resubmission_data)} requests for resubmission")
    elif candidates:
        print(f"\nTo actually purge these {len(candidates)} requests, run with --purge flag")