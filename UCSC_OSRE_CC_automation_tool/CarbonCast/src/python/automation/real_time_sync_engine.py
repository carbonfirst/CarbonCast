#!/usr/bin/env python3
"""
Real-Time Sync Engine for RDA Automation Dashboard

This module provides real-time data synchronization capabilities with immediate sync triggers,
data freshness management, and live status indicators. It eliminates the 30-second cache gap
and provides instant data updates when the dashboard is accessed.

Key Features:
- Immediate sync triggers (0-second delay)
- Data freshness detection and warnings
- Real-time sync status indicators
- Configurable freshness thresholds
- Automatic refresh triggers for stale data
- Enhanced error handling for sync failures
"""

import os
import sys
import json
import sqlite3
import logging
import threading
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import time
import random

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.data_sync import RDADataSyncService, create_data_sync_service


class SyncStatus(Enum):
    """Enumeration for sync status states."""
    IDLE = "idle"
    SYNCING = "syncing"
    SUCCESS = "success"
    ERROR = "error"
    STALE = "stale"


class DataFreshnessLevel(Enum):
    """Enumeration for data freshness levels."""
    FRESH = "fresh"
    ACCEPTABLE = "acceptable"
    STALE = "stale"
    CRITICAL = "critical"


@dataclass
class SyncResult:
    """Data class for sync operation results."""
    success: bool
    timestamp: str
    duration_seconds: float
    total_requests: int
    error_message: Optional[str] = None
    data_source: str = "live_rda_api"
    sync_trigger: str = "unknown"


@dataclass
class DataFreshnessInfo:
    """Data class for data freshness information."""
    level: DataFreshnessLevel
    last_update: datetime
    age_seconds: float
    threshold_seconds: float
    warning_message: Optional[str] = None


@dataclass
class LiveSyncStatus:
    """Data class for live sync status information."""
    status: SyncStatus
    last_sync: Optional[datetime]
    next_sync: Optional[datetime]
    sync_count: int
    error_count: int
    last_error: Optional[str]
    data_freshness: DataFreshnessInfo


class RealTimeSyncEngine:
    """
    Real-Time Sync Engine for immediate data synchronization.
    
    Provides zero-delay sync triggers, data freshness management,
    and real-time status indicators for the dashboard.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db", 
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Real-Time Sync Engine.
        
        Args:
            db_path: Path to the SQLite database file
            config: Configuration dictionary for sync settings
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Load configuration with defaults
        self.config = self._load_config(config or {})
        
        # Initialize data sync service
        self.data_sync_service = create_data_sync_service(db_path)
        
        # Sync status tracking
        self._sync_status = SyncStatus.IDLE
        self._last_sync_time: Optional[datetime] = None
        self._sync_count = 0
        self._error_count = 0
        self._last_error: Optional[str] = None
        
        # Thread safety
        self._sync_lock = threading.Lock()
        self._status_lock = threading.Lock()
        
        # Event callbacks
        self._sync_callbacks: List[Callable[[SyncResult], None]] = []
        self._freshness_callbacks: List[Callable[[DataFreshnessInfo], None]] = []
        
        self.logger.info("Real-Time Sync Engine initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the sync engine."""
        logger = logging.getLogger('rda_automation.real_time_sync')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _load_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load configuration with defaults."""
        default_config = {
            # Freshness thresholds (in seconds)
            'freshness_thresholds': {
                'fresh': 30,        # Data is fresh for 30 seconds
                'acceptable': 300,  # Data is acceptable for 5 minutes
                'stale': 1800,      # Data is stale after 30 minutes
                'critical': 3600    # Data is critical after 1 hour
            },
            
            # Sync behavior
            'immediate_sync_on_access': True,
            'auto_refresh_stale_data': True,
            'max_sync_retries': 3,
            'sync_timeout_seconds': 60,
            
            # Performance settings
            'enable_background_sync': False,
            'background_sync_interval': 300,  # 5 minutes
            'enable_sync_queue': True,
            
            # Error handling
            'retry_on_failure': True,
            'exponential_backoff': True,
            'max_retry_delay': 300  # 5 minutes
        }
        
        # Merge with provided config
        merged_config = default_config.copy()
        merged_config.update(config)
        
        return merged_config
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_last_update_time(self) -> Optional[datetime]:
        """Get the timestamp of the last data update."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT MAX(updated_at) as last_update 
                    FROM rda_requests
                """)
                result = cursor.fetchone()
                
                if result and result['last_update']:
                    return datetime.fromisoformat(result['last_update'])
                    
        except Exception as e:
            self.logger.error(f"Error getting last update time: {e}")
        
        return None
    
    def get_data_freshness(self) -> DataFreshnessInfo:
        """
        Analyze data freshness and return freshness information.
        
        Returns:
            DataFreshnessInfo object with freshness details
        """
        last_update = self._get_last_update_time()
        current_time = datetime.now()
        
        if not last_update:
            return DataFreshnessInfo(
                level=DataFreshnessLevel.CRITICAL,
                last_update=current_time,
                age_seconds=float('inf'),
                threshold_seconds=0,
                warning_message="No data available - sync required"
            )
        
        age_seconds = (current_time - last_update).total_seconds()
        thresholds = self.config['freshness_thresholds']
        
        # Determine freshness level
        if age_seconds <= thresholds['fresh']:
            level = DataFreshnessLevel.FRESH
            warning_message = None
        elif age_seconds <= thresholds['acceptable']:
            level = DataFreshnessLevel.ACCEPTABLE
            warning_message = f"Data is {age_seconds:.0f} seconds old"
        elif age_seconds <= thresholds['stale']:
            level = DataFreshnessLevel.STALE
            warning_message = f"Data is stale ({age_seconds/60:.1f} minutes old)"
        else:
            level = DataFreshnessLevel.CRITICAL
            warning_message = f"Data is critically stale ({age_seconds/3600:.1f} hours old)"
        
        return DataFreshnessInfo(
            level=level,
            last_update=last_update,
            age_seconds=age_seconds,
            threshold_seconds=thresholds[level.value],
            warning_message=warning_message
        )
    
    def should_trigger_sync(self, trigger_reason: str = "unknown") -> bool:
        """
        Determine if a sync should be triggered based on data freshness.
        
        Args:
            trigger_reason: Reason for checking sync trigger
            
        Returns:
            True if sync should be triggered
        """
        freshness = self.get_data_freshness()
        
        # Always sync if immediate sync is enabled and data is not fresh
        if self.config['immediate_sync_on_access']:
            if freshness.level != DataFreshnessLevel.FRESH:
                self.logger.info(f"Triggering immediate sync: {trigger_reason} - {freshness.warning_message}")
                return True
        
        # Auto-refresh stale data
        if self.config['auto_refresh_stale_data']:
            if freshness.level in [DataFreshnessLevel.STALE, DataFreshnessLevel.CRITICAL]:
                self.logger.info(f"Triggering auto-refresh: {trigger_reason} - {freshness.warning_message}")
                return True
        
        return False
    
    def perform_immediate_sync(self, trigger_reason: str = "manual") -> SyncResult:
        """
        Perform immediate data synchronization with enhanced error handling and retry logic.
        
        Args:
            trigger_reason: Reason for triggering the sync
            
        Returns:
            SyncResult object with sync details
        """
        start_time = datetime.now()
        max_retries = self.config.get('max_sync_retries', 3)
        retry_count = 0
        last_error = None
        
        with self._sync_lock:
            while retry_count <= max_retries:
                try:
                    # Update sync status
                    with self._status_lock:
                        self._sync_status = SyncStatus.SYNCING
                    
                    if retry_count > 0:
                        self.logger.info(f"Retrying sync (attempt {retry_count + 1}/{max_retries + 1}): {trigger_reason}")
                        # Exponential backoff with jitter
                        if self.config.get('exponential_backoff', True):
                            delay = min(2 ** retry_count + random.uniform(0, 1), self.config.get('max_retry_delay', 300))
                            time.sleep(delay)
                    else:
                        self.logger.info(f"Starting immediate sync: {trigger_reason}")
                    
                    # Perform the actual sync with timeout
                    sync_result = self._perform_sync_with_timeout()
                    
                    # Create result object
                    duration = (datetime.now() - start_time).total_seconds()
                    result = SyncResult(
                        success=sync_result['success'],
                        timestamp=start_time.isoformat(),
                        duration_seconds=duration,
                        total_requests=sync_result.get('total_requests', 0),
                        error_message=sync_result.get('error') if not sync_result['success'] else None,
                        data_source=sync_result.get('data_source', 'live_rda_api'),
                        sync_trigger=trigger_reason
                    )
                    
                    # Update internal status
                    with self._status_lock:
                        if result.success:
                            self._sync_status = SyncStatus.SUCCESS
                            self._last_sync_time = start_time
                            self._sync_count += 1
                            # Reset error state on success
                            if retry_count > 0:
                                self.logger.info(f"Sync recovered after {retry_count} retries")
                        else:
                            self._sync_status = SyncStatus.ERROR
                            self._error_count += 1
                            self._last_error = result.error_message
                            last_error = result.error_message
                    
                    # If successful or non-retryable error, break the retry loop
                    if result.success or not self._is_retryable_error(result.error_message):
                        break
                        
                    retry_count += 1
                    
                except Exception as e:
                    retry_count += 1
                    last_error = str(e)
                    
                    with self._status_lock:
                        self._sync_status = SyncStatus.ERROR
                        self._error_count += 1
                        self._last_error = last_error
                    
                    self.logger.error(f"Error during sync attempt {retry_count}: {e}")
                    
                    # If this was the last retry or error is not retryable, break
                    if retry_count > max_retries or not self._is_retryable_error(str(e)):
                        break
            
            # Create final result if all retries failed
            if 'result' not in locals():
                duration = (datetime.now() - start_time).total_seconds()
                result = SyncResult(
                    success=False,
                    timestamp=start_time.isoformat(),
                    duration_seconds=duration,
                    total_requests=0,
                    error_message=f"Sync failed after {retry_count} attempts. Last error: {last_error}",
                    sync_trigger=trigger_reason
                )
            
            # Notify callbacks
            for callback in self._sync_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    self.logger.error(f"Error in sync callback: {e}")
            
            if result.success:
                self.logger.info(f"Immediate sync completed successfully in {result.duration_seconds:.2f}s - {result.total_requests} requests")
            else:
                self.logger.error(f"Immediate sync failed after {retry_count} attempts: {result.error_message}")
            
            return result
    
    def _perform_sync_with_timeout(self) -> Dict[str, Any]:
        """Perform sync with timeout handling using threading."""
        import threading
        import queue
        
        timeout_seconds = self.config.get('sync_timeout_seconds', 60)
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def sync_worker():
            try:
                result = self.data_sync_service.perform_full_sync()
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        # Start sync in a separate thread
        sync_thread = threading.Thread(target=sync_worker)
        sync_thread.daemon = True
        sync_thread.start()
        
        # Wait for completion or timeout
        sync_thread.join(timeout_seconds)
        
        if sync_thread.is_alive():
            # Timeout occurred
            raise TimeoutError("Sync operation timed out")
        
        # Check for exceptions
        if not exception_queue.empty():
            raise exception_queue.get()
        
        # Return result
        if not result_queue.empty():
            return result_queue.get()
        else:
            raise RuntimeError("Sync completed but no result returned")
    
    def _is_retryable_error(self, error_message: str) -> bool:
        """
        Determine if an error is retryable.
        
        Args:
            error_message: Error message to analyze
            
        Returns:
            True if the error should be retried
        """
        if not error_message:
            return False
        
        error_lower = error_message.lower()
        
        # Network-related errors that are typically retryable
        retryable_patterns = [
            'timeout',
            'connection',
            'network',
            'temporary',
            'service unavailable',
            'server error',
            'http 5',  # 5xx HTTP errors
            'dns',
            'socket',
            'ssl',
            'certificate'
        ]
        
        # Non-retryable errors
        non_retryable_patterns = [
            'authentication',
            'authorization',
            'permission denied',
            'invalid credentials',
            'http 4',  # 4xx HTTP errors (except 408, 429)
            'not found',
            'bad request'
        ]
        
        # Check for non-retryable patterns first
        for pattern in non_retryable_patterns:
            if pattern in error_lower:
                return False
        
        # Check for retryable patterns
        for pattern in retryable_patterns:
            if pattern in error_lower:
                return True
        
        # Default to retryable for unknown errors
        return True
    
    def sync_on_dashboard_access(self) -> SyncResult:
        """
        Trigger sync when dashboard is accessed (0-second delay).
        
        Returns:
            SyncResult object with sync details
        """
        if self.should_trigger_sync("dashboard_access"):
            return self.perform_immediate_sync("dashboard_access")
        else:
            # Return cached status if no sync needed
            freshness = self.get_data_freshness()
            return SyncResult(
                success=True,
                timestamp=datetime.now().isoformat(),
                duration_seconds=0.0,
                total_requests=0,
                sync_trigger="dashboard_access_cached",
                data_source=f"cached_data_{freshness.level.value}"
            )
    
    def get_live_sync_status(self) -> LiveSyncStatus:
        """
        Get current live sync status information.
        
        Returns:
            LiveSyncStatus object with current status
        """
        with self._status_lock:
            freshness = self.get_data_freshness()
            
            return LiveSyncStatus(
                status=self._sync_status,
                last_sync=self._last_sync_time,
                next_sync=None,  # Immediate sync doesn't have scheduled next sync
                sync_count=self._sync_count,
                error_count=self._error_count,
                last_error=self._last_error,
                data_freshness=freshness
            )
    
    def register_sync_callback(self, callback: Callable[[SyncResult], None]):
        """Register a callback to be called after each sync operation."""
        self._sync_callbacks.append(callback)
    
    def register_freshness_callback(self, callback: Callable[[DataFreshnessInfo], None]):
        """Register a callback to be called when data freshness changes."""
        self._freshness_callbacks.append(callback)
    
    def get_sync_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive sync metrics and statistics.
        
        Returns:
            Dictionary with sync metrics
        """
        with self._status_lock:
            freshness = self.get_data_freshness()
            
            return {
                'sync_statistics': {
                    'total_syncs': self._sync_count,
                    'total_errors': self._error_count,
                    'success_rate': (self._sync_count / (self._sync_count + self._error_count) * 100) 
                                  if (self._sync_count + self._error_count) > 0 else 0,
                    'last_sync': self._last_sync_time.isoformat() if self._last_sync_time else None,
                    'last_error': self._last_error
                },
                'current_status': {
                    'sync_status': self._sync_status.value,
                    'data_freshness': freshness.level.value,
                    'data_age_seconds': freshness.age_seconds,
                    'warning_message': freshness.warning_message
                },
                'configuration': {
                    'immediate_sync_enabled': self.config['immediate_sync_on_access'],
                    'auto_refresh_enabled': self.config['auto_refresh_stale_data'],
                    'freshness_thresholds': self.config['freshness_thresholds']
                },
                'timestamp': datetime.now().isoformat()
            }


def create_real_time_sync_engine(db_path: str = "src/python/data/automation_state.db", 
                                config: Optional[Dict[str, Any]] = None) -> RealTimeSyncEngine:
    """
    Factory function to create a Real-Time Sync Engine.
    
    Args:
        db_path: Path to the SQLite database file
        config: Configuration dictionary for sync settings
        
    Returns:
        Configured RealTimeSyncEngine instance
    """
    return RealTimeSyncEngine(db_path, config)


def main():
    """Main function for testing the real-time sync engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-Time Sync Engine')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Path to database file')
    parser.add_argument('--test-sync', action='store_true',
                       help='Test immediate sync functionality')
    parser.add_argument('--check-freshness', action='store_true',
                       help='Check data freshness')
    parser.add_argument('--status', action='store_true',
                       help='Show sync status')
    
    args = parser.parse_args()
    
    # Create sync engine
    sync_engine = create_real_time_sync_engine(args.db_path)
    
    if args.test_sync:
        print("🔄 Testing immediate sync...")
        result = sync_engine.perform_immediate_sync("test")
        
        if result.success:
            print(f"✅ Sync completed successfully!")
            print(f"📊 Total requests: {result.total_requests}")
            print(f"⏱️  Duration: {result.duration_seconds:.2f} seconds")
        else:
            print(f"❌ Sync failed: {result.error_message}")
    
    elif args.check_freshness:
        print("🕒 Checking data freshness...")
        freshness = sync_engine.get_data_freshness()
        
        print(f"📊 Freshness Level: {freshness.level.value}")
        print(f"🕐 Last Update: {freshness.last_update}")
        print(f"⏰ Age: {freshness.age_seconds:.0f} seconds")
        if freshness.warning_message:
            print(f"⚠️  Warning: {freshness.warning_message}")
    
    elif args.status:
        print("📊 Real-Time Sync Status:")
        status = sync_engine.get_live_sync_status()
        metrics = sync_engine.get_sync_metrics()
        
        print(f"🔄 Sync Status: {status.status.value}")
        print(f"📈 Total Syncs: {status.sync_count}")
        print(f"❌ Error Count: {status.error_count}")
        print(f"📊 Data Freshness: {status.data_freshness.level.value}")
        if status.last_sync:
            print(f"🕐 Last Sync: {status.last_sync}")
        if status.last_error:
            print(f"⚠️  Last Error: {status.last_error}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()