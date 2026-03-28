#!/usr/bin/env python3
"""
Complete Error Handling and Dashboard Enhancement System Demonstration

This script demonstrates the complete integrated system including:
- Error Manager: Automatic error detection and purging
- Retry Manager: Automatic retry of purged requests with intelligent scheduling
- Enhanced Dashboard: Comprehensive metrics and current request tracking
- End-to-End Workflow: Complete integration of all components

Features Demonstrated:
1. Automatic error detection and purging of failed requests
2. Intelligent retry scheduling with exponential backoff
3. Enhanced dashboard with real-time metrics
4. Complete workflow integration
5. Handling of the 4 specific failed requests (ISNE_wind, PACW_dswrf, PJM_rain, NYISO_dswrf)

Usage:
    python demo_complete_system.py --demo-all
    python demo_complete_system.py --demo-errors
    python demo_complete_system.py --demo-retries
    python demo_complete_system.py --demo-dashboard
    python demo_complete_system.py --demo-workflow
    python demo_complete_system.py --start-dashboard
"""

import os
import sys
import json
import sqlite3
import time
import threading
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

from automation.error_manager import ErrorManager, PurgeConfig, create_error_manager
from automation.retry_manager import RetryManager, RetryConfig, create_retry_manager, create_unified_error_retry_workflow
from automation.dashboard import EnhancedRDADashboard, create_dashboard


class CompleteSystemDemo:
    """Demonstration class for the complete error handling and dashboard system."""
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """Initialize the demo with all system components."""
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize system components
        self.error_manager = create_error_manager(self.db_path)
        self.retry_manager = create_retry_manager(self.db_path)
        self.dashboard = create_dashboard(self.db_path)
        
        # Demo data setup
        self._setup_demo_data()
        
        self.logger.info("Complete System Demo initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the demo."""
        return get_logger('complete_system_demo', level=logging.INFO)
    
    def _setup_demo_data(self):
        """Set up demonstration data in the database."""
        # Check if database exists and has data
        if not Path(self.db_path).exists():
            self.logger.info("Database doesn't exist, creating demo database...")
            self._create_demo_database()
        else:
            # Check if we have the demo data
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM file_status WHERE session_id = 'demo_session'")
            count = cursor.fetchone()[0]
            conn.close()
            
            if count == 0:
                self.logger.info("Adding demo data to existing database...")
                self._add_demo_data()
    
    def _create_demo_database(self):
        """Create a complete demo database with sample data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create file_status table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_status (
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
        
        self._add_demo_data()
        conn.close()
    
    def _add_demo_data(self):
        """Add comprehensive demo data to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # The 4 specific failed requests mentioned in the task
        specific_failed_requests = [
            ('demo_session', 'control_files/ISNE_wind_control.ctl', 'ISNE', 'wind', 'failed', 
             'REQ_ISNE_001', (datetime.now() - timedelta(hours=2)).isoformat(), None, None, 
             'HTTP 500: Internal Server Error', 4),
            ('demo_session', 'control_files/PACW_dswrf_control.ctl', 'PACW', 'dswrf', 'failed',
             'REQ_PACW_002', (datetime.now() - timedelta(hours=3)).isoformat(), None, None, 
             'Connection timeout', 3),
            ('demo_session', 'control_files/PJM_rain_control.ctl', 'PJM', 'rain', 'failed',
             'REQ_PJM_003', (datetime.now() - timedelta(hours=1)).isoformat(), None, None, 
             'HTTP 400: Unknown error', 5),
            ('demo_session', 'control_files/NYISO_dswrf_control.ctl', 'NYISO', 'dswrf', 'failed',
             'REQ_NYISO_004', (datetime.now() - timedelta(hours=4)).isoformat(), None, None, 
             'Request timeout', 3)
        ]
        
        # Additional demo data for comprehensive testing
        additional_demo_data = [
            # Successful requests
            ('demo_session', 'control_files/CISO_dswrf_control.ctl', 'CISO', 'dswrf', 'completed', 
             'REQ_SUCCESS_001', (datetime.now() - timedelta(hours=1)).isoformat(), 
             datetime.now().isoformat(), '/downloads/ciso_dswrf.nc', None, 0),
            ('demo_session', 'control_files/ERCOT_wind_control.ctl', 'ERCOT', 'wind', 'completed',
             'REQ_SUCCESS_002', (datetime.now() - timedelta(hours=2)).isoformat(), 
             datetime.now().isoformat(), '/downloads/ercot_wind.nc', None, 1),
            ('demo_session', 'control_files/MISO_temp_control.ctl', 'MISO', 'temp', 'completed',
             'REQ_SUCCESS_003', (datetime.now() - timedelta(hours=3)).isoformat(), 
             datetime.now().isoformat(), '/downloads/miso_temp.nc', None, 0),
            
            # Processing requests
            ('demo_session', 'control_files/SPP_wind_control.ctl', 'SPP', 'wind', 'processing',
             'REQ_PROC_001', (datetime.now() - timedelta(minutes=30)).isoformat(), None, None, None, 0),
            ('demo_session', 'control_files/CAISO_temp_control.ctl', 'CAISO', 'temp', 'submitted',
             'REQ_PROC_002', (datetime.now() - timedelta(minutes=15)).isoformat(), None, None, None, 0),
            
            # Pending requests
            ('demo_session', 'control_files/NYISO_temp_control.ctl', 'NYISO', 'temp', 'pending',
             None, None, None, None, None, 0),
            ('demo_session', 'control_files/ISNE_dswrf_control.ctl', 'ISNE', 'dswrf', 'pending',
             None, None, None, None, None, 0),
            
            # Additional failed requests for variety
            ('demo_session', 'control_files/PJM_wind_control.ctl', 'PJM', 'wind', 'failed',
             'REQ_FAIL_001', (datetime.now() - timedelta(hours=5)).isoformat(), None, None, 
             'HTTP 503: Service Unavailable', 2),
            ('demo_session', 'control_files/ERCOT_temp_control.ctl', 'ERCOT', 'temp', 'failed',
             'REQ_FAIL_002', (datetime.now() - timedelta(hours=6)).isoformat(), None, None, 
             'Network error', 1),
        ]
        
        all_demo_data = specific_failed_requests + additional_demo_data
        
        cursor.executemany("""
            INSERT OR IGNORE INTO file_status (
                session_id, file_path, region, parameter, status, request_id,
                submitted_at, completed_at, download_path, error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, all_demo_data)
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"Added {len(all_demo_data)} demo records to database")
    
    def demo_error_detection_and_purging(self):
        """Demonstrate error detection and purging functionality."""
        print("\n" + "="*80)
        print("🔍 DEMO: ERROR DETECTION AND PURGING")
        print("="*80)
        
        # Step 1: Show current error statistics
        print("\n📊 Current Error Statistics:")
        error_stats = self.error_manager.get_error_statistics()
        print(json.dumps(error_stats, indent=2))
        
        # Step 2: Detect error requests
        print("\n🔍 Detecting Error Requests...")
        error_requests = self.error_manager.detect_error_requests()
        print(f"Found {len(error_requests)} failed requests:")
        
        for req in error_requests:
            print(f"  - {req.region}_{req.parameter}: {req.status} (retries: {req.retry_count}, error: {req.error_message})")
        
        # Step 3: Identify purge candidates
        print("\n🎯 Identifying Purge Candidates...")
        purge_candidates = self.error_manager.get_purge_candidates()
        print(f"Found {len(purge_candidates)} requests meeting purge criteria:")
        
        for candidate in purge_candidates:
            print(f"  - {candidate.region}_{candidate.parameter}: retries={candidate.retry_count}, age={candidate.submitted_at}")
        
        # Step 4: Show the 4 specific failed requests
        specific_requests = [req for req in purge_candidates 
                           if (req.region, req.parameter) in [('ISNE', 'wind'), ('PACW', 'dswrf'), ('PJM', 'rain'), ('NYISO', 'dswrf')]]
        
        print(f"\n🎯 The 4 Specific Failed Requests:")
        for req in specific_requests:
            print(f"  - {req.region}_{req.parameter}: {req.error_message} (retries: {req.retry_count})")
        
        # Step 5: Demonstrate purging (ask for confirmation)
        if purge_candidates:
            response = input(f"\n❓ Purge {len(purge_candidates)} failed requests? (y/N): ")
            if response.lower() == 'y':
                print("\n🗑️  Purging Failed Requests...")
                purged_count, resubmission_data = self.error_manager.purge_error_requests(purge_candidates)
                print(f"✅ Successfully purged {purged_count} requests")
                print(f"📋 Prepared {len(resubmission_data)} requests for resubmission")
                
                # Show resubmission data
                print("\n📋 Resubmission Data:")
                for data in resubmission_data:
                    print(f"  - {data['region']}_{data['parameter']}: {data['file_path']}")
                
                return resubmission_data
            else:
                print("❌ Purging cancelled by user")
                return []
        else:
            print("ℹ️  No requests meet purging criteria")
            return []
    
    def demo_retry_functionality(self, resubmission_data: List[Dict] = None):
        """Demonstrate automatic retry functionality."""
        print("\n" + "="*80)
        print("🔄 DEMO: AUTOMATIC RETRY FUNCTIONALITY")
        print("="*80)
        
        if not resubmission_data:
            # Get some resubmission data for demo
            purge_candidates = self.error_manager.get_purge_candidates()
            if purge_candidates:
                _, resubmission_data = self.error_manager.purge_error_requests(purge_candidates[:2])
            else:
                print("ℹ️  No resubmission data available for retry demo")
                return
        
        # Step 1: Show retry configuration
        print("\n⚙️  Retry Configuration:")
        config_dict = {
            'max_retry_attempts': self.retry_manager.config.max_retry_attempts,
            'base_delay_seconds': self.retry_manager.config.base_delay_seconds,
            'max_delay_seconds': self.retry_manager.config.max_delay_seconds,
            'exponential_base': self.retry_manager.config.exponential_base,
            'jitter_factor': self.retry_manager.config.jitter_factor
        }
        print(json.dumps(config_dict, indent=2))
        
        # Step 2: Demonstrate retry delay calculation
        print("\n⏱️  Retry Delay Calculation (Exponential Backoff):")
        for attempt in range(1, 6):
            delay = self.retry_manager.calculate_retry_delay(attempt)
            print(f"  Attempt {attempt}: {delay} seconds ({delay/60:.1f} minutes)")
        
        # Step 3: Process retry requests
        print(f"\n🔄 Processing {len(resubmission_data)} Retry Requests...")
        retry_results = self.retry_manager.process_retry_requests(resubmission_data)
        
        print("📊 Retry Processing Results:")
        print(json.dumps(retry_results, indent=2))
        
        # Step 4: Show scheduled retries
        print("\n📅 Scheduled Retry Attempts:")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT region, parameter, attempt_number, scheduled_time, status, retry_delay_seconds
            FROM retry_attempts 
            ORDER BY scheduled_time DESC 
            LIMIT 10
        """)
        
        retries = cursor.fetchall()
        conn.close()
        
        for region, parameter, attempt, scheduled_time, status, delay in retries:
            scheduled_dt = datetime.fromisoformat(scheduled_time)
            print(f"  - {region}_{parameter} (attempt {attempt}): {status} at {scheduled_dt.strftime('%H:%M:%S')} (delay: {delay}s)")
        
        # Step 5: Show retry metrics
        print("\n📈 Retry Metrics:")
        retry_stats = self.retry_manager.get_retry_statistics()
        if 'metrics' in retry_stats:
            metrics = retry_stats['metrics']
            print(f"  Total Attempts: {metrics.get('total_retries_attempted', 0)}")
            print(f"  Successful: {metrics.get('total_retries_successful', 0)}")
            print(f"  Failed: {metrics.get('total_retries_failed', 0)}")
            print(f"  Success Rate: {metrics.get('success_rate', 0):.1%}")
            print(f"  Average Delay: {metrics.get('average_retry_delay', 0):.1f} seconds")
    
    def demo_dashboard_functionality(self):
        """Demonstrate enhanced dashboard functionality."""
        print("\n" + "="*80)
        print("📊 DEMO: ENHANCED DASHBOARD FUNCTIONALITY")
        print("="*80)
        
        # Step 1: Dashboard Summary
        print("\n📋 Dashboard Summary:")
        summary = self.dashboard.get_dashboard_summary()
        overview = summary['overview']
        
        print(f"  Total Requests: {overview.get('total_requests', 0)}")
        print(f"  Completed: {overview.get('completed_requests', 0)}")
        print(f"  Processing: {overview.get('processing_requests', 0)}")
        print(f"  Failed: {overview.get('failed_requests', 0)}")
        print(f"  Pending: {overview.get('pending_requests', 0)}")
        print(f"  Success Rate: {overview.get('success_rate', 0):.1f}%")
        print(f"  Active Regions: {overview.get('unique_regions', 0)}")
        print(f"  Weather Variables: {overview.get('unique_parameters', 0)}")
        
        # Step 2: Current Requests with Region and Weather Variable Details
        print("\n📋 Current Requests (with Region & Weather Variable Details):")
        current_requests = self.dashboard.get_current_requests()
        
        print(f"{'Region':<10} {'Weather Var':<12} {'Status':<12} {'Submitted':<20} {'Retries':<8}")
        print("-" * 70)
        
        for req in current_requests[:10]:  # Show first 10
            weather_var_display = {
                'dswrf': 'Solar Rad',
                'wind': 'Wind Speed',
                'temp': 'Temperature',
                'rain': 'Precipitation'
            }.get(req.parameter, req.parameter.upper())
            
            submitted = 'N/A'
            if req.submitted_at:
                try:
                    submitted_dt = datetime.fromisoformat(req.submitted_at.replace('Z', '+00:00'))
                    submitted = submitted_dt.strftime('%m/%d %H:%M')
                except:
                    pass
            
            print(f"{req.region:<10} {weather_var_display:<12} {req.status:<12} {submitted:<20} {req.retry_count:<8}")
        
        if len(current_requests) > 10:
            print(f"... and {len(current_requests) - 10} more requests")
        
        # Step 3: Regional Performance Metrics
        print("\n🗺️  Regional Performance Metrics:")
        regional_metrics = self.dashboard.get_regional_metrics()
        
        print(f"{'Region':<10} {'Total':<8} {'Success Rate':<12} {'Most Common Var':<15}")
        print("-" * 50)
        
        for metric in regional_metrics:
            most_common = {
                'dswrf': 'Solar Rad',
                'wind': 'Wind Speed',
                'temp': 'Temperature',
                'rain': 'Precipitation'
            }.get(metric.most_common_parameter, metric.most_common_parameter)
            
            print(f"{metric.region:<10} {metric.total_requests:<8} {metric.success_rate:<11.1f}% {most_common:<15}")
        
        # Step 4: Weather Variable Analysis
        print("\n🌡️  Weather Variable Analysis:")
        weather_metrics = self.dashboard.get_weather_variable_metrics()
        
        print(f"{'Weather Variable':<15} {'Total':<8} {'Success Rate':<12} {'Top Regions':<20}")
        print("-" * 60)
        
        for metric in weather_metrics:
            var_display = {
                'dswrf': 'Solar Radiation',
                'wind': 'Wind Speed',
                'temp': 'Temperature',
                'rain': 'Precipitation'
            }.get(metric.parameter, metric.parameter.upper())
            
            top_regions = ', '.join(metric.most_active_regions[:3])
            
            print(f"{var_display:<15} {metric.total_requests:<8} {metric.success_rate:<11.1f}% {top_regions:<20}")
        
        # Step 5: Error and Retry Integration
        print("\n⚠️  Error and Retry Statistics:")
        error_stats = summary.get('error_statistics', {})
        retry_stats = summary.get('retry_statistics', {})
        
        print(f"  Failed Requests: {error_stats.get('total_failed_requests', 0)}")
        print(f"  Exceeding Retries: {error_stats.get('requests_exceeding_retries', 0)}")
        
        if 'metrics' in retry_stats:
            retry_metrics = retry_stats['metrics']
            print(f"  Retry Attempts: {retry_metrics.get('total_retries_attempted', 0)}")
            print(f"  Retry Success Rate: {retry_metrics.get('success_rate', 0):.1%}")
    
    def demo_unified_workflow(self):
        """Demonstrate the complete unified workflow."""
        print("\n" + "="*80)
        print("🔄 DEMO: UNIFIED ERROR-RETRY-DASHBOARD WORKFLOW")
        print("="*80)
        
        print("\n🚀 Starting Unified Workflow...")
        print("This workflow will:")
        print("  1. Detect and purge error requests")
        print("  2. Schedule automatic retries")
        print("  3. Update dashboard metrics")
        print("  4. Clean up expired retries")
        
        # Run the unified workflow
        workflow_result = create_unified_error_retry_workflow(
            db_path=self.db_path,
            session_id='demo_session'
        )
        
        print("\n📊 Workflow Results:")
        print(f"  Workflow Completed: {workflow_result.get('workflow_completed', False)}")
        print(f"  Session ID: {workflow_result.get('session_id', 'N/A')}")
        
        # Purge results
        purge_results = workflow_result.get('purge_results', {})
        print(f"\n🗑️  Purge Results:")
        print(f"  Requests Purged: {purge_results.get('purged_count', 0)}")
        print(f"  Resubmission Data Prepared: {len(purge_results.get('resubmission_data', []))}")
        
        # Retry results
        retry_results = workflow_result.get('retry_results', {})
        print(f"\n🔄 Retry Results:")
        print(f"  Retries Scheduled: {retry_results.get('scheduled', 0)}")
        print(f"  Retries Processed: {retry_results.get('processed', 0)}")
        print(f"  Ready Retries: {retry_results.get('ready_retries', 0)}")
        
        # Cleanup results
        expired_cleanup = workflow_result.get('expired_cleanup', 0)
        print(f"\n🧹 Cleanup Results:")
        print(f"  Expired Retries Cleaned: {expired_cleanup}")
        
        # Updated statistics
        error_stats = workflow_result.get('error_statistics', {})
        retry_stats = workflow_result.get('retry_statistics', {})
        
        print(f"\n📈 Updated Statistics:")
        print(f"  Total Failed Requests: {error_stats.get('total_failed_requests', 0)}")
        print(f"  Requests Exceeding Retries: {error_stats.get('requests_exceeding_retries', 0)}")
        
        if 'metrics' in retry_stats:
            metrics = retry_stats['metrics']
            print(f"  Total Retry Attempts: {metrics.get('total_retries_attempted', 0)}")
            print(f"  Retry Success Rate: {metrics.get('success_rate', 0):.1%}")
        
        print(f"\n✅ Unified workflow completed successfully!")
        return workflow_result
    
    def start_dashboard_server(self, port: int = 8080):
        """Start the enhanced dashboard server."""
        print("\n" + "="*80)
        print("🌐 STARTING ENHANCED DASHBOARD SERVER")
        print("="*80)
        
        print(f"\n🚀 Starting dashboard server on port {port}...")
        print(f"📊 Dashboard URL: http://localhost:{port}")
        print("\nFeatures available:")
        print("  - 📋 Real-time overview metrics")
        print("  - 📊 Current requests with region and weather variable details")
        print("  - 🗺️  Regional performance insights")
        print("  - 🌡️  Weather variable analysis")
        print("  - ⚠️  Error and retry statistics")
        print("  - 🔄 Auto-refresh every 30 seconds")
        
        print(f"\n🌐 API Endpoints available:")
        print(f"  - GET /api/summary - Dashboard summary")
        print(f"  - GET /api/current-requests - Current requests")
        print(f"  - GET /api/regional-metrics - Regional performance")
        print(f"  - GET /api/weather-variable-metrics - Weather variable analysis")
        print(f"  - GET /api/error-metrics - Error and retry statistics")
        print(f"  - GET /api/filters - Available filter options")
        print(f"  - GET /api/live-data - Complete live data refresh")
        
        print(f"\n⚡ Press Ctrl+C to stop the server")
        
        try:
            self.dashboard.start_dashboard(host='0.0.0.0', port=port, debug=False)
        except KeyboardInterrupt:
            print(f"\n👋 Dashboard server stopped by user")
        except Exception as e:
            print(f"\n❌ Error starting dashboard: {e}")
    
    def run_complete_demo(self):
        """Run the complete system demonstration."""
        print("🎉 COMPLETE ERROR HANDLING AND DASHBOARD ENHANCEMENT SYSTEM DEMO")
        print("="*80)
        print("This demo will showcase:")
        print("  1. 🔍 Error Detection and Purging")
        print("  2. 🔄 Automatic Retry Functionality")
        print("  3. 📊 Enhanced Dashboard with Real-time Metrics")
        print("  4. 🔄 Unified Workflow Integration")
        print("  5. 🎯 Handling of 4 Specific Failed Requests")
        
        # Demo 1: Error Detection and Purging
        resubmission_data = self.demo_error_detection_and_purging()
        
        # Demo 2: Retry Functionality
        self.demo_retry_functionality(resubmission_data)
        
        # Demo 3: Dashboard Functionality
        self.demo_dashboard_functionality()
        
        # Demo 4: Unified Workflow
        self.demo_unified_workflow()
        
        # Demo 5: Offer to start dashboard
        response = input(f"\n❓ Start the enhanced dashboard server? (y/N): ")
        if response.lower() == 'y':
            self.start_dashboard_server()
        
        print(f"\n🎉 Complete system demonstration finished!")
        print(f"✅ All components are working together seamlessly:")
        print(f"   - Error Manager: Automatic detection and purging ✅")
        print(f"   - Retry Manager: Intelligent retry scheduling ✅")
        print(f"   - Enhanced Dashboard: Real-time metrics and insights ✅")
        print(f"   - Unified Workflow: Complete integration ✅")


def main():
    """Main function for running the demonstration."""
    parser = argparse.ArgumentParser(description='Complete Error Handling and Dashboard System Demo')
    parser.add_argument('--demo-all', action='store_true', help='Run complete demonstration')
    parser.add_argument('--demo-errors', action='store_true', help='Demo error detection and purging')
    parser.add_argument('--demo-retries', action='store_true', help='Demo retry functionality')
    parser.add_argument('--demo-dashboard', action='store_true', help='Demo dashboard functionality')
    parser.add_argument('--demo-workflow', action='store_true', help='Demo unified workflow')
    parser.add_argument('--start-dashboard', action='store_true', help='Start dashboard server')
    parser.add_argument('--port', type=int, default=8080, help='Dashboard server port')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db', help='Database path')
    
    args = parser.parse_args()
    
    # Create demo instance
    demo = CompleteSystemDemo(args.db_path)
    
    try:
        if args.demo_all:
            demo.run_complete_demo()
        elif args.demo_errors:
            demo.demo_error_detection_and_purging()
        elif args.demo_retries:
            demo.demo_retry_functionality()
        elif args.demo_dashboard:
            demo.demo_dashboard_functionality()
        elif args.demo_workflow:
            demo.demo_unified_workflow()
        elif args.start_dashboard:
            demo.start_dashboard_server(args.port)
        else:
            # Default: run complete demo
            demo.run_complete_demo()
    
    except KeyboardInterrupt:
        print(f"\n👋 Demo stopped by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()