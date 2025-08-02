#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for RDA Automation System tests.

This module provides common fixtures and configuration for all test modules
in the RDA automation system test suite.
"""

import os
import sys
import json
import tempfile
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

# Add src/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))


@pytest.fixture(scope="session")
def test_config():
    """Provide a standard test configuration for all tests."""
    return {
        "automation": {
            "max_concurrent_requests": 8,
            "check_interval_seconds": 300,
            "retry_attempts": 3,
            "retry_delay_seconds": 60,
            "auto_upload_enabled": True,
            "status_check_interval_seconds": 180
        },
        "upload": {
            "dest_file": "./ds0841.1_control.ctl",
            "rate_limit_delay": 2.0,
            "auto_discover_incoming": True
        },
        "directories": {
            "base_download_dir": "./test_downloads",
            "logs_dir": "./test_logs",
            "control_files_dir": "./test_control_files"
        },
        "database": {
            "path": "./test_automation_state.db"
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }


@pytest.fixture
def temp_config_file(test_config):
    """Create a temporary configuration file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(test_config, f, indent=2)
        config_file_path = f.name
    
    yield config_file_path
    
    # Cleanup
    try:
        os.unlink(config_file_path)
    except OSError:
        pass


@pytest.fixture
def temp_database():
    """Create a temporary SQLite database for testing."""
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    db_path = temp_db.name
    
    # Initialize database with basic schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create file_status table (standard schema)
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
    
    # Create retry_attempts table
    cursor.execute("""
        CREATE TABLE retry_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_request_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            file_path TEXT NOT NULL,
            region TEXT NOT NULL,
            parameter TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            scheduled_time TEXT NOT NULL,
            executed_time TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled',
            retry_delay_seconds INTEGER NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create retry_metrics table
    cursor.execute("""
        CREATE TABLE retry_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            total_retries_attempted INTEGER DEFAULT 0,
            total_retries_successful INTEGER DEFAULT 0,
            total_retries_failed INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 0.0,
            average_retry_delay REAL DEFAULT 0.0,
            calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def mock_batch_system():
    """Create a mock batch automation system."""
    mock_system = Mock()
    mock_system.submit_request.return_value = True
    mock_system._get_current_request_count.return_value = 5
    mock_system.requests_state = {}
    mock_system.config = {}
    
    # Create a proper context manager mock for status_lock
    mock_status_lock = Mock()
    mock_status_lock.__enter__ = Mock(return_value=mock_status_lock)
    mock_status_lock.__exit__ = Mock(return_value=None)
    mock_system.status_lock = mock_status_lock
    mock_system.initialize_requests = Mock()
    
    return mock_system


@pytest.fixture
def mock_queue_manager():
    """Create a mock queue manager."""
    mock_queue = Mock()
    mock_queue.add_to_queue = Mock()
    mock_queue.get_queue_status = Mock(return_value={'pending': 0, 'processing': 0})
    mock_queue.process_queue = Mock()
    return mock_queue


@pytest.fixture
def mock_upload_files():
    """Create mock upload_files module functions."""
    mock_upload = Mock()
    mock_upload.discover_control_files.return_value = [
        "./test_control_files/CISO_wind_control.ctl",
        "./test_control_files/ERCOT_temp_control.ctl"
    ]
    mock_upload.submit_batch_files.return_value = {
        'success': True,
        'submitted_files': [
            "./test_control_files/CISO_wind_control.ctl",
            "./test_control_files/ERCOT_temp_control.ctl"
        ],
        'failed_files': [],
        'request_ids': ['12345', '12346'],
        'errors': []
    }
    return mock_upload


@pytest.fixture
def sample_test_data():
    """Provide sample test data for various test scenarios."""
    return {
        'regions': ['CISO', 'ERCOT', 'PJM', 'MISO', 'NYISO'],
        'parameters': ['dswrf', 'wind', 'temp', 'rain'],
        'control_files': [
            'CISO_dswrf_control.ctl',
            'ERCOT_wind_control.ctl',
            'PJM_temp_control.ctl',
            'MISO_rain_control.ctl'
        ],
        'request_ids': ['REQ_001', 'REQ_002', 'REQ_003', 'REQ_004'],
        'error_messages': [
            'HTTP 500: Internal Server Error',
            'Connection timeout',
            'HTTP 400: Bad Request',
            'Authentication failed'
        ]
    }


@pytest.fixture
def test_directories(tmp_path):
    """Create temporary test directories."""
    directories = {
        'downloads': tmp_path / 'downloads',
        'logs': tmp_path / 'logs',
        'control_files': tmp_path / 'control_files',
        'results': tmp_path / 'results'
    }
    
    # Create all directories
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    
    return directories


@pytest.fixture
def populated_database(temp_database, sample_test_data):
    """Create a database populated with test data."""
    conn = sqlite3.connect(temp_database)
    cursor = conn.cursor()
    
    # Insert sample file status records
    test_requests = [
        ('session_1', 'control_files/CISO_dswrf_control.ctl', 'CISO', 'dswrf', 'completed', 
         'REQ_001', datetime.now().isoformat(), datetime.now().isoformat(), 
         '/downloads/CISO/dswrf/data.nc', None, 0),
        ('session_1', 'control_files/ERCOT_wind_control.ctl', 'ERCOT', 'wind', 'failed',
         'REQ_002', datetime.now().isoformat(), None, None, 'Connection timeout', 2),
        ('session_1', 'control_files/PJM_temp_control.ctl', 'PJM', 'temp', 'processing',
         'REQ_003', datetime.now().isoformat(), None, None, None, 0),
        ('session_2', 'control_files/MISO_rain_control.ctl', 'MISO', 'rain', 'failed',
         'REQ_004', datetime.now().isoformat(), None, None, 'HTTP 500: Internal Server Error', 3)
    ]
    
    cursor.executemany("""
        INSERT INTO file_status (
            session_id, file_path, region, parameter, status, request_id,
            submitted_at, completed_at, download_path, error_message, retry_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_requests)
    
    conn.commit()
    conn.close()
    
    return temp_database


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Automatically set up test environment for all tests."""
    # Set environment variables for testing
    os.environ['TESTING'] = '1'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    yield
    
    # Cleanup environment variables
    os.environ.pop('TESTING', None)
    os.environ.pop('LOG_LEVEL', None)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_db: mark test as requiring database"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add integration marker for tests in integration directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add unit marker for tests in unit directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add requires_db marker for tests that use database fixtures
        if any(fixture in item.fixturenames for fixture in ['temp_database', 'populated_database']):
            item.add_marker(pytest.mark.requires_db)