#!/usr/bin/env python3
"""
Test suite for the auto-upload integration functionality.

This tests the missing integration that automatically calls upload_files.py
when there are fewer than 10 active requests.
"""

import os
import sys
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add src/python to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))

from batch_automation_integrated import IntegratedBatchSystem


class TestAutoUploadIntegration(unittest.TestCase):
    """Test cases for auto-upload integration functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
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
            }
        }
        
        # Create test config file
        self.config_file = "test_automation_config.json"
        with open(self.config_file, 'w') as f:
            json.dump(self.test_config, f, indent=2)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.config_file):
            os.remove(self.config_file)
    
    @patch('batch_automation_integrated.upload_files')
    @patch('batch_automation_integrated.BatchAutomationSystem')
    @patch('batch_automation_integrated.IntelligentQueueManager')
    @patch('batch_automation_integrated.BatchMonitor')
    def test_auto_upload_when_slots_available(self, mock_monitor, mock_queue, mock_batch, mock_upload_files):
        """Test that auto-upload is triggered when request count < 10."""
        
        # Mock the batch system to return low request count
        mock_batch_instance = Mock()
        mock_batch_instance._get_current_request_count.return_value = 5  # 5 < 10, should trigger auto-upload
        mock_batch_instance.requests_state = {}
        mock_batch_instance.config = self.test_config
        # Create a proper context manager mock for status_lock
        mock_status_lock = Mock()
        mock_status_lock.__enter__ = Mock(return_value=mock_status_lock)
        mock_status_lock.__exit__ = Mock(return_value=None)
        mock_batch_instance.status_lock = mock_status_lock
        mock_batch_instance.initialize_requests = Mock()  # Mock initialize_requests
        mock_batch.return_value = mock_batch_instance
        
        # Mock upload_files functions
        mock_upload_files.discover_control_files.return_value = [
            "./test_control_files/CISO_wind_control.ctl",
            "./test_control_files/ERCOT_temp_control.ctl"
        ]
        
        mock_upload_files.submit_batch_files.return_value = {
            'success': True,
            'submitted_files': [
                "./test_control_files/CISO_wind_control.ctl",
                "./test_control_files/ERCOT_temp_control.ctl"
            ],
            'failed_files': [],
            'request_ids': ['12345', '12346'],
            'errors': []
        }
        
        # Mock queue manager
        mock_queue_instance = Mock()
        mock_queue_instance.add_to_queue = Mock()
        mock_queue.return_value = mock_queue_instance
        
        # Create integrated system
        system = IntegratedBatchSystem(self.config_file)
        
        # Test the auto-upload functionality
        system._auto_upload_new_files(available_slots=5)
        
        # Verify upload_files functions were called
        mock_upload_files.discover_control_files.assert_called_once()
        mock_upload_files.submit_batch_files.assert_called_once()
        
        # Verify files were added to queue
        mock_queue_instance.add_to_queue.assert_called_once()
        
        # Verify batch system was updated
        mock_batch_instance.initialize_requests.assert_called_once()
    
    @patch('batch_automation_integrated.upload_files')
    @patch('batch_automation_integrated.BatchAutomationSystem')
    @patch('batch_automation_integrated.IntelligentQueueManager')
    @patch('batch_automation_integrated.BatchMonitor')
    def test_auto_upload_disabled_in_config(self, mock_monitor, mock_queue, mock_batch, mock_upload_files):
        """Test that auto-upload is skipped when disabled in configuration."""
        
        # Disable auto-upload in config
        self.test_config['automation']['auto_upload_enabled'] = False
        with open(self.config_file, 'w') as f:
            json.dump(self.test_config, f, indent=2)
        
        # Mock the batch system
        mock_batch_instance = Mock()
        mock_batch_instance._get_current_request_count.return_value = 5
        mock_batch_instance.requests_state = {}
        mock_batch_instance.config = self.test_config
        
        # Create a proper context manager mock for status_lock
        mock_status_lock = Mock()
        mock_status_lock.__enter__ = Mock(return_value=mock_status_lock)
        mock_status_lock.__exit__ = Mock(return_value=None)
        mock_batch_instance.status_lock = mock_status_lock
        
        mock_batch.return_value = mock_batch_instance
        
        # Create integrated system
        system = IntegratedBatchSystem(self.config_file)
        
        # Test the auto-upload functionality
        system._auto_upload_new_files(available_slots=5)
        
        # Verify upload_files functions were NOT called
        mock_upload_files.discover_control_files.assert_not_called()
        mock_upload_files.submit_batch_files.assert_not_called()
    
    @patch('batch_automation_integrated.upload_files')
    @patch('batch_automation_integrated.BatchAutomationSystem')
    @patch('batch_automation_integrated.IntelligentQueueManager')
    @patch('batch_automation_integrated.BatchMonitor')
    def test_auto_upload_no_new_files(self, mock_monitor, mock_queue, mock_batch, mock_upload_files):
        """Test auto-upload behavior when no new files are found."""
        
        # Mock the batch system
        mock_batch_instance = Mock()
        mock_batch_instance._get_current_request_count.return_value = 3
        mock_batch_instance.requests_state = {}
        mock_batch_instance.config = self.test_config
        
        # Create a proper context manager mock for status_lock
        mock_status_lock = Mock()
        mock_status_lock.__enter__ = Mock(return_value=mock_status_lock)
        mock_status_lock.__exit__ = Mock(return_value=None)
        mock_batch_instance.status_lock = mock_status_lock
        
        mock_batch.return_value = mock_batch_instance
        
        # Mock upload_files to return no files
        mock_upload_files.discover_control_files.return_value = []
        
        # Create integrated system
        system = IntegratedBatchSystem(self.config_file)
        
        # Test the auto-upload functionality
        system._auto_upload_new_files(available_slots=7)
        
        # Verify discover was called but submit was not
        mock_upload_files.discover_control_files.assert_called_once()
        mock_upload_files.submit_batch_files.assert_not_called()
    
    @patch('batch_automation_integrated.upload_files')
    @patch('batch_automation_integrated.BatchAutomationSystem')
    @patch('batch_automation_integrated.IntelligentQueueManager')
    @patch('batch_automation_integrated.BatchMonitor')
    def test_auto_upload_respects_slot_limit(self, mock_monitor, mock_queue, mock_batch, mock_upload_files):
        """Test that auto-upload respects the available slot limit."""
        
        # Mock the batch system
        mock_batch_instance = Mock()
        mock_batch_instance._get_current_request_count.return_value = 8  # 2 slots available
        mock_batch_instance.requests_state = {}
        mock_batch_instance.config = self.test_config
        
        # Create a proper context manager mock for status_lock
        mock_status_lock = Mock()
        mock_status_lock.__enter__ = Mock(return_value=mock_status_lock)
        mock_status_lock.__exit__ = Mock(return_value=None)
        mock_batch_instance.status_lock = mock_status_lock
        
        mock_batch.return_value = mock_batch_instance
        
        # Mock upload_files to return more files than available slots
        mock_upload_files.discover_control_files.return_value = [
            "./test_control_files/CISO_wind_control.ctl",
            "./test_control_files/ERCOT_temp_control.ctl",
            "./test_control_files/PJM_rain_control.ctl",
            "./test_control_files/MISO_dswrf_control.ctl"
        ]
        
        mock_upload_files.submit_batch_files.return_value = {
            'success': True,
            'submitted_files': [
                "./test_control_files/CISO_wind_control.ctl",
                "./test_control_files/ERCOT_temp_control.ctl"
            ],
            'failed_files': [],
            'request_ids': ['12345', '12346'],
            'errors': []
        }
        
        # Mock queue manager
        mock_queue_instance = Mock()
        mock_queue.return_value = mock_queue_instance
        
        # Create integrated system
        system = IntegratedBatchSystem(self.config_file)
        
        # Test the auto-upload functionality with 2 available slots
        system._auto_upload_new_files(available_slots=2)
        
        # Verify submit_batch_files was called with only 2 files (respecting slot limit)
        call_args = mock_upload_files.submit_batch_files.call_args
        submitted_files = call_args[1]['file_paths']  # keyword argument
        self.assertEqual(len(submitted_files), 2, "Should only submit files up to available slot limit")
    
    def test_integration_in_main_loop_logic(self):
        """Test that the integration logic is properly placed in the main processing loop."""
        
        # Read the integrated batch system file to verify the integration
        integrated_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python', 'batch_automation_integrated.py')
        
        with open(integrated_file_path, 'r') as f:
            content = f.read()
        
        # Verify key integration components are present
        self.assertIn('_get_current_request_count()', content, 
                     "Should call _get_current_request_count() to check active requests")
        
        self.assertIn('current_request_count < 10', content,
                     "Should check if request count is less than 10")
        
        self.assertIn('_auto_upload_new_files', content,
                     "Should call _auto_upload_new_files method")
        
        self.assertIn('Available request slots detected', content,
                     "Should log when slots are available")
        
        self.assertIn('upload_files', content,
                     "Should import and use upload_files functionality")


class TestAutoUploadIntegrationFlow(unittest.TestCase):
    """Integration tests for the complete auto-upload flow."""
    
    def test_workflow_specification_compliance(self):
        """Test that the implementation matches the user specification exactly."""
        
        # The user specification states:
        # "As soon as the requests are freed up and notice there is space to submit a request, 
        # usually done by checking if there are fewer than 10 requests, I will then go ahead 
        # and run the upload_files.py file to submit a request."
        
        integrated_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python', 'batch_automation_integrated.py')
        
        with open(integrated_file_path, 'r') as f:
            content = f.read()
        
        # Verify the exact workflow is implemented
        self.assertIn('current_request_count = self.batch_system._get_current_request_count()', content,
                     "Should get current request count from batch system")
        
        self.assertIn('if current_request_count < 10:', content,
                     "Should check if fewer than 10 requests are active")
        
        self.assertIn('upload_files.py', content,
                     "Should reference upload_files.py functionality")
        
        self.assertIn('submit_batch_files', content,
                     "Should call upload_files submit functionality")
        
        # Verify it's in the main processing loop
        self.assertIn('while self.running:', content,
                     "Should be integrated into the main processing loop")


if __name__ == '__main__':
    unittest.main()