#!/usr/bin/env python3
"""
Integration tests for the RetryManager module.

This test suite verifies that the RetryManager integrates correctly with
the existing error_manager, batch_automation, and queue management systems.
"""

import os
import sys
import json
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the src/python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))

from automation.retry_manager import (
    RetryManager, RetryConfig, RetryAttempt, RetryMetrics,
    create_retry_manager, create_unified_error_retry_workflow
)
from automation.error_manager import ErrorManager, ErrorRequest, PurgeConfig


class TestRetryManagerIntegration(unittest.TestCase):
    """Test suite for RetryManager integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Initialize database with test data
        self._setup_test_database()
        
        # Create mock batch system and queue manager
        self.mock_batch_system = Mock()
        self.mock_queue_manager = Mock()
        
        # Configure mock batch system
        self.mock_batch_system.submit_request.return_value = True
        self.mock_batch_system.requests_state = {
            'test_control.ctl': Mock(request_id='TEST_REQ_123')
        }
        
        # Create retry manager
        self.retry_manager = RetryManager(
            db_path=self.db_path,
            batch_system=self.mock_batch_system,
            queue_manager=self.mock_queue_manager
        )
    
    def tearDown(self):
        """Clean up test environment."""
        # Close any open connections
        if hasattr(self.retry_manager, 'executor'):
            self.retry_manager.executor.shutdown(wait=True)
        
        # Remove temporary database
        try:
            os.unlink(self.db_path)
        except OSError:
            pass
    
    def _setup_test_database(self):
        """Set up test database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create file_status table (from existing system)
        cursor.execute("""
            CREATE TABLE file_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                region TEXT NOT NULL,
                parameter TEXT NOT NULL,
                status TEXT NOT NULL,
                request_id TEXT,
                submitted_at TEXT,
                completed_at TEXT,
                download_path TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        # Insert test failed requests
        test_requests = [
            ('session_1', 'control_files/CISO_dswrf_control.ctl', 'CISO', 'dswrf', 'failed', 
             'REQ_001', datetime.now().isoformat(), None, None, 'HTTP 500: Internal Server Error', 3),
            ('session_1', 'control_files/ERCOT_wind_control.ctl', 'ERCOT', 'wind', 'failed',
             'REQ_002', datetime.now().isoformat(), None, None, 'Connection timeout', 2),
            ('session_2', 'control_files/PJM_temp_control.ctl', 'PJM', 'temp', 'failed',
             'REQ_003', datetime.now().isoformat(), None, None, 'HTTP 400: Unknown error', 4)
        ]
        
        cursor.executemany("""
            INSERT INTO file_status (
                session_id, file_path, region, parameter, status, request_id,
                submitted_at, completed_at, download_path, error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_requests)
        
        conn.commit()
        conn.close()
    
    def test_retry_manager_initialization(self):
        """Test that RetryManager initializes correctly."""
        self.assertIsNotNone(self.retry_manager)
        self.assertEqual(self.retry_manager.db_path, self.db_path)
        self.assertIsNotNone(self.retry_manager.config)
        self.assertIsNotNone(self.retry_manager.logger)
        
        # Verify database tables were created
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check retry_attempts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='retry_attempts'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check retry_metrics table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='retry_metrics'")
        self.assertIsNotNone(cursor.fetchone())
        
        conn.close()
    
    def test_calculate_retry_delay(self):
        """Test exponential backoff calculation."""
        # Test first attempt
        delay1 = self.retry_manager.calculate_retry_delay(1)
        self.assertGreaterEqual(delay1, self.retry_manager.config.base_delay_seconds)
        
        # Test second attempt (should be longer)
        delay2 = self.retry_manager.calculate_retry_delay(2)
        self.assertGreater(delay2, delay1)
        
        # Test maximum delay cap
        delay_large = self.retry_manager.calculate_retry_delay(10)
        self.assertLessEqual(delay_large, self.retry_manager.config.max_delay_seconds)
    
    def test_schedule_retry(self):
        """Test retry scheduling functionality."""
        resubmission_data = {
            'original_id': 1,
            'session_id': 'test_session',
            'file_path': 'control_files/TEST_control.ctl',
            'region': 'TEST',
            'parameter': 'test',
            'original_error': 'Test error',
            'retry_count': 2,
            'purged_at': datetime.now().isoformat(),
            'resubmission_ready': True
        }
        
        # Schedule a retry
        retry_attempt = self.retry_manager.schedule_retry(resubmission_data, attempt_number=1)
        
        self.assertIsNotNone(retry_attempt)
        self.assertEqual(retry_attempt.original_request_id, 1)
        self.assertEqual(retry_attempt.session_id, 'test_session')
        self.assertEqual(retry_attempt.region, 'TEST')
        self.assertEqual(retry_attempt.parameter, 'test')
        self.assertEqual(retry_attempt.attempt_number, 1)
        self.assertEqual(retry_attempt.status, 'scheduled')
        
        # Verify it was saved to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM retry_attempts WHERE id = ?", (retry_attempt.id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        conn.close()
    
    def test_get_ready_retries(self):
        """Test getting ready retry attempts."""
        # Schedule a retry with past scheduled time
        past_time = datetime.now() - timedelta(minutes=5)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO retry_attempts (
                original_request_id, session_id, file_path, region, parameter,
                attempt_number, scheduled_time, status, retry_delay_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'test_session', 'test.ctl', 'TEST', 'test', 1, 
              past_time.isoformat(), 'scheduled', 60))
        conn.commit()
        conn.close()
        
        # Get ready retries
        ready_retries = self.retry_manager.get_ready_retries()
        
        self.assertEqual(len(ready_retries), 1)
        self.assertEqual(ready_retries[0].region, 'TEST')
        self.assertEqual(ready_retries[0].status, 'scheduled')
    
    def test_resubmit_request(self):
        """Test request resubmission."""
        # Create a retry attempt
        retry_attempt = RetryAttempt(
            id=1,
            original_request_id=1,
            session_id='test_session',
            file_path='test_control.ctl',
            region='TEST',
            parameter='test',
            attempt_number=1,
            scheduled_time=datetime.now().isoformat(),
            status='scheduled',
            retry_delay_seconds=60
        )
        
        # Insert into database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO retry_attempts (
                id, original_request_id, session_id, file_path, region, parameter,
                attempt_number, scheduled_time, status, retry_delay_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (retry_attempt.id, retry_attempt.original_request_id, retry_attempt.session_id,
              retry_attempt.file_path, retry_attempt.region, retry_attempt.parameter,
              retry_attempt.attempt_number, retry_attempt.scheduled_time,
              retry_attempt.status, retry_attempt.retry_delay_seconds))
        conn.commit()
        conn.close()
        
        # Test successful resubmission
        success = self.retry_manager.resubmit_request(retry_attempt)
        
        self.assertTrue(success)
        self.mock_batch_system.submit_request.assert_called_once_with('test_control.ctl')
        
        # Verify status was updated in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM retry_attempts WHERE id = ?", (retry_attempt.id,))
        row = cursor.fetchone()
        self.assertEqual(row[0], 'completed')
        conn.close()
    
    def test_track_retry_metrics(self):
        """Test retry metrics tracking."""
        # Insert test retry attempts
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        test_attempts = [
            (1, 'session_1', 'test1.ctl', 'TEST1', 'test', 1, 'completed'),
            (2, 'session_1', 'test2.ctl', 'TEST2', 'test', 1, 'completed'),
            (3, 'session_1', 'test3.ctl', 'TEST3', 'test', 1, 'failed'),
            (4, 'session_2', 'test4.ctl', 'TEST4', 'test', 1, 'completed')
        ]
        
        for attempt_data in test_attempts:
            cursor.execute("""
                INSERT INTO retry_attempts (
                    original_request_id, session_id, file_path, region, parameter,
                    attempt_number, status, scheduled_time, retry_delay_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, attempt_data + (datetime.now().isoformat(), 60))
        
        conn.commit()
        conn.close()
        
        # Test metrics for all sessions
        metrics = self.retry_manager.track_retry_metrics()
        self.assertEqual(metrics.total_retries_attempted, 4)
        self.assertEqual(metrics.total_retries_successful, 3)
        self.assertEqual(metrics.total_retries_failed, 1)
        self.assertEqual(metrics.success_rate, 0.75)
        
        # Test metrics for specific session
        session_metrics = self.retry_manager.track_retry_metrics('session_1')
        self.assertEqual(session_metrics.total_retries_attempted, 3)
        self.assertEqual(session_metrics.total_retries_successful, 2)
        self.assertEqual(session_metrics.total_retries_failed, 1)
    
    def test_process_retry_requests(self):
        """Test the main retry processing function."""
        resubmission_data_list = [
            {
                'original_id': 1,
                'session_id': 'test_session',
                'file_path': 'control_files/TEST1_control.ctl',
                'region': 'TEST1',
                'parameter': 'test',
                'original_error': 'Test error 1',
                'retry_count': 2,
                'purged_at': datetime.now().isoformat(),
                'resubmission_ready': True
            },
            {
                'original_id': 2,
                'session_id': 'test_session',
                'file_path': 'control_files/TEST2_control.ctl',
                'region': 'TEST2',
                'parameter': 'test',
                'original_error': 'Test error 2',
                'retry_count': 1,
                'purged_at': datetime.now().isoformat(),
                'resubmission_ready': True
            }
        ]
        
        # Process retry requests
        result = self.retry_manager.process_retry_requests(resubmission_data_list)
        
        self.assertIsInstance(result, dict)
        self.assertIn('scheduled', result)
        self.assertIn('processed', result)
        self.assertIn('errors', result)
        self.assertEqual(result['scheduled'], 2)  # Should schedule 2 retries
    
    @patch('automation.error_manager.create_error_manager')
    def test_unified_workflow(self, mock_create_error_manager):
        """Test the unified error detection and retry workflow."""
        # Mock error manager
        mock_error_manager = Mock()
        mock_error_manager.auto_purge_session.return_value = {
            'session_id': 'test_session',
            'purged_count': 2,
            'resubmission_data': [
                {
                    'original_id': 1,
                    'session_id': 'test_session',
                    'file_path': 'control_files/TEST_control.ctl',
                    'region': 'TEST',
                    'parameter': 'test',
                    'original_error': 'Test error',
                    'retry_count': 2,
                    'purged_at': datetime.now().isoformat(),
                    'resubmission_ready': True
                }
            ],
            'timestamp': datetime.now().isoformat()
        }
        mock_error_manager.get_error_statistics.return_value = {
            'total_failed_requests': 5,
            'requests_exceeding_retries': 2
        }
        
        mock_create_error_manager.return_value = mock_error_manager
        
        # Test unified workflow
        result = create_unified_error_retry_workflow(
            db_path=self.db_path,
            batch_system=self.mock_batch_system,
            queue_manager=self.mock_queue_manager,
            session_id='test_session'
        )
        
        self.assertTrue(result['workflow_completed'])
        self.assertEqual(result['session_id'], 'test_session')
        self.assertIn('purge_results', result)
        self.assertIn('retry_results', result)
        self.assertIn('error_statistics', result)
        self.assertIn('retry_statistics', result)
    
    def test_cleanup_expired_retries(self):
        """Test cleanup of expired retry attempts."""
        # Insert expired retry attempt
        expired_time = datetime.now() - timedelta(hours=25)  # Beyond 24-hour timeout
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO retry_attempts (
                original_request_id, session_id, file_path, region, parameter,
                attempt_number, scheduled_time, status, retry_delay_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (1, 'test_session', 'test.ctl', 'TEST', 'test', 1,
              expired_time.isoformat(), 'scheduled', 60))
        conn.commit()
        conn.close()
        
        # Clean up expired retries
        expired_count = self.retry_manager.cleanup_expired_retries()
        
        self.assertEqual(expired_count, 1)
        
        # Verify status was updated
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM retry_attempts WHERE scheduled_time = ?", 
                      (expired_time.isoformat(),))
        row = cursor.fetchone()
        self.assertEqual(row[0], 'expired')
        conn.close()
    
    def test_factory_function(self):
        """Test the factory function for creating RetryManager."""
        retry_manager = create_retry_manager(
            db_path=self.db_path,
            max_retry_attempts=3,
            base_delay_seconds=30
        )
        
        self.assertIsNotNone(retry_manager)
        self.assertEqual(retry_manager.config.max_retry_attempts, 3)
        self.assertEqual(retry_manager.config.base_delay_seconds, 30)


class TestRetryConfig(unittest.TestCase):
    """Test suite for RetryConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        
        self.assertEqual(config.max_retry_attempts, 5)
        self.assertEqual(config.base_delay_seconds, 60)
        self.assertEqual(config.max_delay_seconds, 3600)
        self.assertEqual(config.exponential_base, 2.0)
        self.assertEqual(config.jitter_factor, 0.1)
        self.assertEqual(config.batch_size, 3)
        self.assertEqual(config.retry_timeout_hours, 24)
        self.assertEqual(config.success_rate_threshold, 0.7)
        self.assertTrue(config.enabled)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_retry_attempts=3,
            base_delay_seconds=30,
            enabled=False
        )
        
        self.assertEqual(config.max_retry_attempts, 3)
        self.assertEqual(config.base_delay_seconds, 30)
        self.assertFalse(config.enabled)


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)