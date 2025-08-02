#!/usr/bin/env python3
"""
Dashboard Enhancements Module for RDA Automation System

This module provides additional dashboard components, utilities, and enhancements
for comprehensive monitoring and visualization of the RDA automation system.

Key Features:
- Enhanced dashboard components for error tracking and progress monitoring
- Real-time data visualization utilities
- Interactive dashboard widgets and charts
- Alert system integration
- Dashboard configuration and customization
- Performance optimization utilities
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.error_dashboard_api import create_error_dashboard_api
from automation.progress_tracker_api import create_progress_tracker_api
from automation.real_time_sync_engine import create_real_time_sync_engine


@dataclass
class DashboardWidget:
    """Data class for dashboard widget configuration."""
    widget_id: str
    widget_type: str
    title: str
    data_source: str
    refresh_interval: int
    position: Dict[str, int]
    size: Dict[str, int]
    config: Dict[str, Any]
    enabled: bool = True


@dataclass
class AlertConfiguration:
    """Data class for alert configuration."""
    alert_id: str
    alert_type: str
    threshold_value: float
    comparison_operator: str
    metric_path: str
    severity: str
    enabled: bool = True
    notification_channels: List[str] = None


class DashboardEnhancements:
    """
    Enhanced dashboard components and utilities for comprehensive monitoring.
    
    Provides advanced dashboard features, real-time updates, and customization
    capabilities for the RDA automation system monitoring.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db"):
        """
        Initialize the Dashboard Enhancements.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize APIs
        self.error_api = create_error_dashboard_api(db_path)
        self.progress_api = create_progress_tracker_api(db_path)
        self.sync_engine = create_real_time_sync_engine(db_path)
        
        # Dashboard configuration
        self.widget_configs = {}
        self.alert_configs = {}
        
        # Thread safety
        self.enhancement_lock = threading.Lock()
        
        # Load default configurations
        self._load_default_configurations()
        
        self.logger.info("Dashboard Enhancements initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the dashboard enhancements."""
        logger = logging.getLogger('dashboard_enhancements')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _load_default_configurations(self):
        """Load default widget and alert configurations."""
        # Default widget configurations
        self.widget_configs = {
            'error_summary': DashboardWidget(
                widget_id='error_summary',
                widget_type='metric_card',
                title='Error Summary',
                data_source='/api/error-tracking/summary',
                refresh_interval=30,
                position={'x': 0, 'y': 0},
                size={'width': 4, 'height': 2},
                config={'show_trends': True, 'highlight_critical': True}
            ),
            'progress_overview': DashboardWidget(
                widget_id='progress_overview',
                widget_type='progress_bar',
                title='Overall Progress',
                data_source='/api/progress-tracking/overall',
                refresh_interval=60,
                position={'x': 4, 'y': 0},
                size={'width': 4, 'height': 2},
                config={'show_percentage': True, 'show_eta': True}
            ),
            'regional_health_map': DashboardWidget(
                widget_id='regional_health_map',
                widget_type='heat_map',
                title='Regional Health Map',
                data_source='/api/error-tracking/regional-health',
                refresh_interval=120,
                position={'x': 8, 'y': 0},
                size={'width': 4, 'height': 4},
                config={'color_scheme': 'health', 'show_labels': True}
            ),
            'error_trends_chart': DashboardWidget(
                widget_id='error_trends_chart',
                widget_type='line_chart',
                title='Error Trends (24h)',
                data_source='/api/error-tracking/trends',
                refresh_interval=300,
                position={'x': 0, 'y': 2},
                size={'width': 8, 'height': 3},
                config={'time_range': '24h', 'show_anomalies': True}
            ),
            'retry_queue_status': DashboardWidget(
                widget_id='retry_queue_status',
                widget_type='gauge',
                title='Retry Queue Status',
                data_source='/api/error-tracking/retry-queue-status',
                refresh_interval=30,
                position={'x': 0, 'y': 5},
                size={'width': 3, 'height': 2},
                config={'max_value': 100, 'warning_threshold': 70}
            ),
            'live_error_feed': DashboardWidget(
                widget_id='live_error_feed',
                widget_type='data_table',
                title='Live Error Feed',
                data_source='/api/error-tracking/live-feed',
                refresh_interval=15,
                position={'x': 3, 'y': 5},
                size={'width': 9, 'height': 4},
                config={'max_rows': 20, 'auto_refresh': True, 'show_filters': True}
            )
        }
        
        # Default alert configurations
        self.alert_configs = {
            'critical_errors_high': AlertConfiguration(
                alert_id='critical_errors_high',
                alert_type='threshold',
                threshold_value=5.0,
                comparison_operator='greater_than',
                metric_path='error_summary.summary.critical_errors',
                severity='critical',
                notification_channels=['dashboard', 'log']
            ),
            'error_rate_high': AlertConfiguration(
                alert_id='error_rate_high',
                alert_type='threshold',
                threshold_value=10.0,
                comparison_operator='greater_than',
                metric_path='error_summary.summary.error_rate_24h',
                severity='warning',
                notification_channels=['dashboard']
            ),
            'retry_success_rate_low': AlertConfiguration(
                alert_id='retry_success_rate_low',
                alert_type='threshold',
                threshold_value=70.0,
                comparison_operator='less_than',
                metric_path='retry_status.queue_status.success_rate',
                severity='warning',
                notification_channels=['dashboard', 'log']
            ),
            'processing_rate_low': AlertConfiguration(
                alert_id='processing_rate_low',
                alert_type='threshold',
                threshold_value=0.5,
                comparison_operator='less_than',
                metric_path='overall_progress.progress.processing_rate_per_hour',
                severity='warning',
                notification_channels=['dashboard']
            )
        }
    
    def get_dashboard_layout(self) -> Dict[str, Any]:
        """
        Get the complete dashboard layout configuration.
        
        Returns:
            Dictionary containing dashboard layout and widget configurations
        """
        try:
            layout = {
                'widgets': [asdict(widget) for widget in self.widget_configs.values()],
                'alerts': [asdict(alert) for alert in self.alert_configs.values()],
                'layout_config': {
                    'grid_size': 12,
                    'row_height': 60,
                    'margin': [10, 10],
                    'auto_refresh_enabled': True,
                    'theme': 'light'
                },
                'generated_at': datetime.now().isoformat()
            }
            
            return layout
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard layout: {e}")
            return {
                'widgets': [],
                'alerts': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_widget_data(self, widget_id: str) -> Dict[str, Any]:
        """
        Get data for a specific dashboard widget.
        
        Args:
            widget_id: ID of the widget to get data for
            
        Returns:
            Dictionary containing widget data
        """
        try:
            if widget_id not in self.widget_configs:
                return {'error': f'Widget {widget_id} not found'}
            
            widget = self.widget_configs[widget_id]
            
            # Route to appropriate data source
            if widget.data_source == '/api/error-tracking/summary':
                data = self.error_api.get_error_summary()
            elif widget.data_source == '/api/progress-tracking/overall':
                data = self.progress_api.get_overall_progress()
            elif widget.data_source == '/api/error-tracking/regional-health':
                data = self.error_api.get_regional_error_health()
            elif widget.data_source == '/api/error-tracking/trends':
                data = self.error_api.get_error_trends()
            elif widget.data_source == '/api/error-tracking/retry-queue-status':
                data = self.error_api.get_retry_queue_status()
            elif widget.data_source == '/api/error-tracking/live-feed':
                data = self.error_api.get_live_error_feed(limit=20)
            else:
                data = {'error': f'Unknown data source: {widget.data_source}'}
            
            # Add widget metadata
            data['widget_metadata'] = {
                'widget_id': widget_id,
                'widget_type': widget.widget_type,
                'title': widget.title,
                'last_updated': datetime.now().isoformat(),
                'refresh_interval': widget.refresh_interval
            }
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error getting widget data for {widget_id}: {e}")
            return {
                'error': str(e),
                'widget_id': widget_id,
                'generated_at': datetime.now().isoformat()
            }
    
    def get_all_widget_data(self) -> Dict[str, Any]:
        """
        Get data for all dashboard widgets.
        
        Returns:
            Dictionary containing data for all widgets
        """
        try:
            widget_data = {}
            
            for widget_id in self.widget_configs.keys():
                widget_data[widget_id] = self.get_widget_data(widget_id)
            
            return {
                'widgets': widget_data,
                'generated_at': datetime.now().isoformat(),
                'total_widgets': len(widget_data)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting all widget data: {e}")
            return {
                'widgets': {},
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all configured alerts and return active alerts.
        
        Returns:
            List of active alert dictionaries
        """
        active_alerts = []
        
        try:
            # Get current system data
            error_summary = self.error_api.get_error_summary()
            retry_status = self.error_api.get_retry_queue_status()
            overall_progress = self.progress_api.get_overall_progress()
            
            system_data = {
                'error_summary': error_summary,
                'retry_status': retry_status,
                'overall_progress': overall_progress
            }
            
            # Check each alert configuration
            for alert_id, alert_config in self.alert_configs.items():
                if not alert_config.enabled:
                    continue
                
                try:
                    # Extract metric value using path
                    metric_value = self._extract_metric_value(system_data, alert_config.metric_path)
                    
                    if metric_value is None:
                        continue
                    
                    # Check threshold
                    alert_triggered = self._check_threshold(
                        metric_value, 
                        alert_config.threshold_value, 
                        alert_config.comparison_operator
                    )
                    
                    if alert_triggered:
                        alert = {
                            'alert_id': alert_id,
                            'alert_type': alert_config.alert_type,
                            'severity': alert_config.severity,
                            'title': self._generate_alert_title(alert_config),
                            'message': self._generate_alert_message(alert_config, metric_value),
                            'metric_path': alert_config.metric_path,
                            'current_value': metric_value,
                            'threshold_value': alert_config.threshold_value,
                            'comparison_operator': alert_config.comparison_operator,
                            'notification_channels': alert_config.notification_channels or [],
                            'triggered_at': datetime.now().isoformat()
                        }
                        active_alerts.append(alert)
                        
                except Exception as e:
                    self.logger.error(f"Error checking alert {alert_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error checking alerts: {e}")
        
        return active_alerts
    
    def _extract_metric_value(self, data: Dict[str, Any], metric_path: str) -> Optional[float]:
        """Extract metric value from nested data using dot notation path."""
        try:
            keys = metric_path.split('.')
            current = data
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return None
            
            # Convert to float if possible
            if isinstance(current, (int, float)):
                return float(current)
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error extracting metric value for {metric_path}: {e}")
            return None
    
    def _check_threshold(self, value: float, threshold: float, operator: str) -> bool:
        """Check if value meets threshold condition."""
        if operator == 'greater_than':
            return value > threshold
        elif operator == 'less_than':
            return value < threshold
        elif operator == 'equal_to':
            return abs(value - threshold) < 0.001
        elif operator == 'greater_than_or_equal':
            return value >= threshold
        elif operator == 'less_than_or_equal':
            return value <= threshold
        else:
            return False
    
    def _generate_alert_title(self, alert_config: AlertConfiguration) -> str:
        """Generate alert title based on configuration."""
        titles = {
            'critical_errors_high': 'High Critical Error Count',
            'error_rate_high': 'High Error Rate Detected',
            'retry_success_rate_low': 'Low Retry Success Rate',
            'processing_rate_low': 'Slow Processing Rate'
        }
        return titles.get(alert_config.alert_id, f'Alert: {alert_config.alert_id}')
    
    def _generate_alert_message(self, alert_config: AlertConfiguration, current_value: float) -> str:
        """Generate alert message based on configuration and current value."""
        operator_text = {
            'greater_than': 'exceeds',
            'less_than': 'is below',
            'equal_to': 'equals',
            'greater_than_or_equal': 'is at or above',
            'less_than_or_equal': 'is at or below'
        }
        
        op_text = operator_text.get(alert_config.comparison_operator, 'meets condition for')
        
        return (f"Current value ({current_value:.2f}) {op_text} "
                f"threshold ({alert_config.threshold_value:.2f})")
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard metrics for performance monitoring.
        
        Returns:
            Dictionary containing dashboard performance metrics
        """
        try:
            # Get widget refresh statistics
            widget_stats = {}
            for widget_id, widget in self.widget_configs.items():
                widget_stats[widget_id] = {
                    'refresh_interval': widget.refresh_interval,
                    'enabled': widget.enabled,
                    'data_source': widget.data_source,
                    'last_refresh': datetime.now().isoformat()  # Would be tracked in real implementation
                }
            
            # Get alert statistics
            alert_stats = {
                'total_alerts': len(self.alert_configs),
                'enabled_alerts': len([a for a in self.alert_configs.values() if a.enabled]),
                'active_alerts': len(self.check_alerts())
            }
            
            # Get system performance metrics
            sync_status = self.sync_engine.get_live_sync_status()
            
            return {
                'dashboard_performance': {
                    'total_widgets': len(self.widget_configs),
                    'enabled_widgets': len([w for w in self.widget_configs.values() if w.enabled]),
                    'average_refresh_interval': sum(w.refresh_interval for w in self.widget_configs.values()) / len(self.widget_configs)
                },
                'widget_statistics': widget_stats,
                'alert_statistics': alert_stats,
                'sync_performance': {
                    'status': sync_status.status.value,
                    'sync_count': sync_status.sync_count,
                    'error_count': sync_status.error_count,
                    'data_freshness': sync_status.data_freshness.level.value
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting dashboard metrics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def update_widget_config(self, widget_id: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration for a specific widget.
        
        Args:
            widget_id: ID of the widget to update
            config_updates: Dictionary of configuration updates
            
        Returns:
            Dictionary containing update result
        """
        try:
            if widget_id not in self.widget_configs:
                return {
                    'success': False,
                    'error': f'Widget {widget_id} not found'
                }
            
            widget = self.widget_configs[widget_id]
            
            # Update allowed fields
            allowed_updates = ['title', 'refresh_interval', 'enabled', 'config', 'position', 'size']
            
            for key, value in config_updates.items():
                if key in allowed_updates:
                    if key == 'config':
                        # Merge config dictionaries
                        widget.config.update(value)
                    else:
                        setattr(widget, key, value)
            
            return {
                'success': True,
                'widget_id': widget_id,
                'updated_config': asdict(widget),
                'updated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error updating widget config for {widget_id}: {e}")
            return {
                'success': False,
                'widget_id': widget_id,
                'error': str(e)
            }
    
    def export_dashboard_config(self) -> Dict[str, Any]:
        """
        Export complete dashboard configuration for backup or sharing.
        
        Returns:
            Dictionary containing complete dashboard configuration
        """
        try:
            config = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'widgets': {
                    widget_id: asdict(widget) 
                    for widget_id, widget in self.widget_configs.items()
                },
                'alerts': {
                    alert_id: asdict(alert) 
                    for alert_id, alert in self.alert_configs.items()
                },
                'metadata': {
                    'total_widgets': len(self.widget_configs),
                    'total_alerts': len(self.alert_configs),
                    'database_path': self.db_path
                }
            }
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error exporting dashboard config: {e}")
            return {
                'error': str(e),
                'exported_at': datetime.now().isoformat()
            }


def create_dashboard_enhancements(db_path: str = "src/python/data/automation_state.db") -> DashboardEnhancements:
    """
    Factory function to create Dashboard Enhancements.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured DashboardEnhancements instance
    """
    return DashboardEnhancements(db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Dashboard Enhancements')
    parser.add_argument('--test-layout', action='store_true',
                       help='Test dashboard layout')
    parser.add_argument('--test-widgets', action='store_true',
                       help='Test widget data retrieval')
    parser.add_argument('--test-alerts', action='store_true',
                       help='Test alert checking')
    parser.add_argument('--test-metrics', action='store_true',
                       help='Test dashboard metrics')
    parser.add_argument('--export-config', action='store_true',
                       help='Export dashboard configuration')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create dashboard enhancements
    enhancements = create_dashboard_enhancements(args.db_path)
    
    try:
        if args.test_layout:
            print("=== Testing Dashboard Layout ===")
            layout = enhancements.get_dashboard_layout()
            print(json.dumps(layout, indent=2))
            
        elif args.test_widgets:
            print("=== Testing Widget Data ===")
            widget_data = enhancements.get_all_widget_data()
            print(json.dumps(widget_data, indent=2))
            
        elif args.test_alerts:
            print("=== Testing Alert Checking ===")
            alerts = enhancements.check_alerts()
            print(json.dumps(alerts, indent=2))
            
        elif args.test_metrics:
            print("=== Testing Dashboard Metrics ===")
            metrics = enhancements.get_dashboard_metrics()
            print(json.dumps(metrics, indent=2))
            
        elif args.export_config:
            print("=== Exporting Dashboard Configuration ===")
            config = enhancements.export_dashboard_config()
            print(json.dumps(config, indent=2))
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")