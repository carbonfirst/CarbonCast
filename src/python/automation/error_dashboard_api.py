#!/usr/bin/env python3
"""
Error Dashboard API for RDA Automation System

This module provides specialized API endpoints for comprehensive error tracking,
monitoring, and analysis. It integrates with the enhanced error tracking database
schema to provide real-time error insights, trend analysis, and resolution tools.

Key Features:
- Real-time error feed with filtering and search
- Error trend analysis and pattern recognition
- Regional error heat map and health indicators
- Interactive error resolution tools
- Comprehensive error metrics and analytics
- Integration with smart retry system
- Circuit breaker status monitoring
"""

import os
import sys
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.enhanced_database_schema import create_enhanced_schema_manager
from automation.smart_retry_manager import create_smart_retry_manager, SmartRetryConfig
from automation.error_manager import create_error_manager


@dataclass
class ErrorSummary:
    """Data class for error summary information."""
    total_errors: int
    active_errors: int
    resolved_errors: int
    critical_errors: int
    error_rate_24h: float
    most_common_error_type: str
    most_affected_region: str
    resolution_rate: float
    average_resolution_time_hours: float


@dataclass
class RegionalErrorHealth:
    """Data class for regional error health metrics."""
    region: str
    total_errors: int
    active_errors: int
    error_rate: float
    health_score: float
    dominant_error_types: List[str]
    last_error_time: Optional[str]
    recovery_trend: str
    circuit_breaker_status: str


@dataclass
class ErrorTrend:
    """Data class for error trend analysis."""
    time_period: str
    error_count: int
    error_rate: float
    trend_direction: str
    trend_magnitude: float
    anomaly_detected: bool
    prediction_next_hour: int


class ErrorDashboardAPI:
    """
    Specialized API for error tracking and monitoring dashboard.
    
    Provides comprehensive error analytics, real-time monitoring,
    and interactive error resolution tools.
    """
    
    def __init__(self, db_path: str = "./data/automation_state.db"):
        """
        Initialize the Error Dashboard API.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.logger = self._setup_logging()
        
        # Initialize database schema manager
        self.schema_manager = create_enhanced_schema_manager(db_path)
        
        # Initialize smart retry manager for integration
        try:
            retry_config = SmartRetryConfig(db_path=db_path)
            self.smart_retry_manager = create_smart_retry_manager(retry_config)
        except Exception as e:
            self.logger.warning(f"Could not initialize smart retry manager: {e}")
            self.smart_retry_manager = None
        
        # Initialize error manager for legacy integration
        try:
            self.error_manager = create_error_manager(db_path)
        except Exception as e:
            self.logger.warning(f"Could not initialize error manager: {e}")
            self.error_manager = None
        
        # Thread safety
        self.api_lock = threading.Lock()
        
        self.logger.info("Error Dashboard API initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the error dashboard API."""
        logger = logging.getLogger('error_dashboard_api')
        
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
    
    def get_error_summary(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive error summary for the dashboard.
        
        Args:
            time_window_hours: Time window for analysis in hours
            
        Returns:
            Dictionary containing error summary data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate time threshold
                time_threshold = (datetime.now() - timedelta(hours=time_window_hours)).isoformat()
                
                # Get total error counts
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_errors,
                        COUNT(CASE WHEN resolution_status = 'unresolved' THEN 1 END) as active_errors,
                        COUNT(CASE WHEN resolution_status = 'resolved' THEN 1 END) as resolved_errors,
                        COUNT(CASE WHEN error_severity = 'critical' THEN 1 END) as critical_errors,
                        COUNT(CASE WHEN created_at >= ? THEN 1 END) as recent_errors
                    FROM error_tracking_enhanced
                """, (time_threshold,))
                
                summary_data = cursor.fetchone()
                
                # Get most common error type
                cursor.execute("""
                    SELECT error_type, COUNT(*) as count
                    FROM error_tracking_enhanced
                    WHERE created_at >= ?
                    GROUP BY error_type
                    ORDER BY count DESC
                    LIMIT 1
                """, (time_threshold,))
                
                common_error = cursor.fetchone()
                most_common_error_type = common_error['error_type'] if common_error else 'None'
                
                # Get most affected region
                cursor.execute("""
                    SELECT region, COUNT(*) as count
                    FROM error_tracking_enhanced
                    WHERE created_at >= ? AND region IS NOT NULL
                    GROUP BY region
                    ORDER BY count DESC
                    LIMIT 1
                """, (time_threshold,))
                
                affected_region = cursor.fetchone()
                most_affected_region = affected_region['region'] if affected_region else 'None'
                
                # Calculate error rate (errors per hour)
                total_errors = summary_data['total_errors'] or 0
                recent_errors = summary_data['recent_errors'] or 0
                error_rate_24h = recent_errors / time_window_hours if time_window_hours > 0 else 0
                
                # Calculate resolution rate
                resolved_errors = summary_data['resolved_errors'] or 0
                resolution_rate = (resolved_errors / total_errors * 100) if total_errors > 0 else 0
                
                # Calculate average resolution time
                cursor.execute("""
                    SELECT AVG(
                        (julianday(resolved_at) - julianday(first_occurrence)) * 24
                    ) as avg_resolution_hours
                    FROM error_tracking_enhanced
                    WHERE resolution_status = 'resolved' 
                    AND resolved_at IS NOT NULL
                    AND first_occurrence IS NOT NULL
                """)
                
                resolution_time_result = cursor.fetchone()
                avg_resolution_time = resolution_time_result['avg_resolution_hours'] or 0
                
                return {
                    'summary': {
                        'total_errors': total_errors,
                        'active_errors': summary_data['active_errors'] or 0,
                        'resolved_errors': resolved_errors,
                        'critical_errors': summary_data['critical_errors'] or 0,
                        'error_rate_24h': round(error_rate_24h, 2),
                        'most_common_error_type': most_common_error_type,
                        'most_affected_region': most_affected_region,
                        'resolution_rate': round(resolution_rate, 1),
                        'average_resolution_time_hours': round(avg_resolution_time, 2)
                    },
                    'time_window_hours': time_window_hours,
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting error summary: {e}")
            return {
                'summary': {},
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_live_error_feed(self, limit: int = 50, region_filter: Optional[str] = None,
                           error_type_filter: Optional[str] = None, 
                           severity_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get live error feed with filtering capabilities.
        
        Args:
            limit: Maximum number of errors to return
            region_filter: Optional region filter
            error_type_filter: Optional error type filter
            severity_filter: Optional severity filter
            
        Returns:
            Dictionary containing live error feed data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Build query with filters
                query = """
                    SELECT 
                        id, request_id, request_index, error_type, error_category,
                        error_severity, error_message, region, variable_type,
                        retry_count, max_retries, is_retryable, resolution_status,
                        first_occurrence, last_occurrence, frequency_count,
                        impact_score, created_at, updated_at
                    FROM error_tracking_enhanced
                    WHERE 1=1
                """
                params = []
                
                if region_filter:
                    query += " AND region = ?"
                    params.append(region_filter)
                
                if error_type_filter:
                    query += " AND error_type = ?"
                    params.append(error_type_filter)
                
                if severity_filter:
                    query += " AND error_severity = ?"
                    params.append(severity_filter)
                
                query += " ORDER BY last_occurrence DESC, created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                errors = cursor.fetchall()
                
                # Convert to list of dictionaries
                error_list = []
                for error in errors:
                    error_dict = dict(error)
                    
                    # Add computed fields
                    error_dict['is_active'] = error_dict['resolution_status'] == 'unresolved'
                    error_dict['needs_attention'] = (
                        error_dict['error_severity'] == 'critical' or
                        error_dict['frequency_count'] > 5 or
                        error_dict['retry_count'] >= error_dict['max_retries']
                    )
                    
                    # Calculate age
                    if error_dict['last_occurrence']:
                        try:
                            last_occurrence = datetime.fromisoformat(error_dict['last_occurrence'])
                            age_seconds = (datetime.now() - last_occurrence).total_seconds()
                            error_dict['age_minutes'] = round(age_seconds / 60, 1)
                        except:
                            error_dict['age_minutes'] = None
                    
                    error_list.append(error_dict)
                
                return {
                    'errors': error_list,
                    'total_count': len(error_list),
                    'filters_applied': {
                        'region': region_filter,
                        'error_type': error_type_filter,
                        'severity': severity_filter,
                        'limit': limit
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting live error feed: {e}")
            return {
                'errors': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_regional_error_health(self) -> Dict[str, Any]:
        """
        Get regional error health metrics and heat map data.
        
        Returns:
            Dictionary containing regional error health data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get regional error statistics
                cursor.execute("""
                    SELECT 
                        region,
                        COUNT(*) as total_errors,
                        COUNT(CASE WHEN resolution_status = 'unresolved' THEN 1 END) as active_errors,
                        COUNT(CASE WHEN error_severity = 'critical' THEN 1 END) as critical_errors,
                        AVG(impact_score) as avg_impact_score,
                        MAX(last_occurrence) as last_error_time,
                        GROUP_CONCAT(DISTINCT error_type) as error_types
                    FROM error_tracking_enhanced
                    WHERE region IS NOT NULL
                    GROUP BY region
                    ORDER BY total_errors DESC
                """)
                
                regional_data = cursor.fetchall()
                
                regional_health = []
                for region_row in regional_data:
                    region = region_row['region']
                    total_errors = region_row['total_errors']
                    active_errors = region_row['active_errors']
                    critical_errors = region_row['critical_errors']
                    
                    # Calculate error rate (simplified as errors per day)
                    error_rate = total_errors / 7  # Assume 7-day window
                    
                    # Calculate health score (0-100, higher is better)
                    health_score = max(0, 100 - (active_errors * 10) - (critical_errors * 20))
                    
                    # Determine recovery trend (simplified)
                    recovery_trend = "stable"
                    if active_errors == 0:
                        recovery_trend = "recovering"
                    elif critical_errors > 0:
                        recovery_trend = "degrading"
                    
                    # Get dominant error types
                    error_types = region_row['error_types'].split(',') if region_row['error_types'] else []
                    dominant_error_types = error_types[:3]  # Top 3
                    
                    # Get circuit breaker status (if available)
                    circuit_breaker_status = "unknown"
                    if self.smart_retry_manager:
                        try:
                            can_execute = self.smart_retry_manager.circuit_breaker_manager.can_execute_request(
                                region, "rda_api"
                            )
                            circuit_breaker_status = "closed" if can_execute else "open"
                        except:
                            pass
                    
                    regional_health.append({
                        'region': region,
                        'total_errors': total_errors,
                        'active_errors': active_errors,
                        'critical_errors': critical_errors,
                        'error_rate': round(error_rate, 2),
                        'health_score': round(health_score, 1),
                        'dominant_error_types': dominant_error_types,
                        'last_error_time': region_row['last_error_time'],
                        'recovery_trend': recovery_trend,
                        'circuit_breaker_status': circuit_breaker_status
                    })
                
                return {
                    'regional_health': regional_health,
                    'total_regions': len(regional_health),
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting regional error health: {e}")
            return {
                'regional_health': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_error_trends(self, hours_back: int = 24, interval_hours: int = 1) -> Dict[str, Any]:
        """
        Get error trend analysis over time.
        
        Args:
            hours_back: Number of hours to analyze
            interval_hours: Interval for trend buckets
            
        Returns:
            Dictionary containing error trend data
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Generate time buckets
                trends = []
                current_time = datetime.now()
                
                for i in range(0, hours_back, interval_hours):
                    bucket_end = current_time - timedelta(hours=i)
                    bucket_start = bucket_end - timedelta(hours=interval_hours)
                    
                    # Count errors in this time bucket
                    cursor.execute("""
                        SELECT COUNT(*) as error_count
                        FROM error_tracking_enhanced
                        WHERE created_at >= ? AND created_at < ?
                    """, (bucket_start.isoformat(), bucket_end.isoformat()))
                    
                    result = cursor.fetchone()
                    error_count = result['error_count'] if result else 0
                    
                    # Calculate error rate (errors per hour)
                    error_rate = error_count / interval_hours
                    
                    trends.append({
                        'time_bucket': bucket_start.isoformat(),
                        'time_bucket_end': bucket_end.isoformat(),
                        'error_count': error_count,
                        'error_rate': round(error_rate, 2),
                        'hours_ago': i + interval_hours
                    })
                
                # Reverse to get chronological order
                trends.reverse()
                
                # Calculate trend direction and magnitude
                if len(trends) >= 2:
                    recent_rate = sum(t['error_rate'] for t in trends[-3:]) / min(3, len(trends))
                    older_rate = sum(t['error_rate'] for t in trends[:3]) / min(3, len(trends))
                    
                    if recent_rate > older_rate * 1.2:
                        trend_direction = "increasing"
                        trend_magnitude = (recent_rate - older_rate) / older_rate * 100
                    elif recent_rate < older_rate * 0.8:
                        trend_direction = "decreasing"
                        trend_magnitude = (older_rate - recent_rate) / older_rate * 100
                    else:
                        trend_direction = "stable"
                        trend_magnitude = 0
                else:
                    trend_direction = "insufficient_data"
                    trend_magnitude = 0
                
                # Simple anomaly detection (errors > 2x average)
                if trends:
                    avg_error_rate = sum(t['error_rate'] for t in trends) / len(trends)
                    anomaly_threshold = avg_error_rate * 2
                    
                    for trend in trends:
                        trend['anomaly_detected'] = trend['error_rate'] > anomaly_threshold
                
                return {
                    'trends': trends,
                    'analysis': {
                        'trend_direction': trend_direction,
                        'trend_magnitude': round(trend_magnitude, 1),
                        'average_error_rate': round(avg_error_rate, 2) if trends else 0,
                        'peak_error_rate': max(t['error_rate'] for t in trends) if trends else 0,
                        'anomalies_detected': sum(1 for t in trends if t.get('anomaly_detected', False))
                    },
                    'time_window': {
                        'hours_back': hours_back,
                        'interval_hours': interval_hours,
                        'total_buckets': len(trends)
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting error trends: {e}")
            return {
                'trends': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def get_retry_queue_status(self) -> Dict[str, Any]:
        """
        Get current retry queue status and metrics.
        
        Returns:
            Dictionary containing retry queue status
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get retry queue statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_items,
                        COUNT(CASE WHEN queue_status = 'pending' THEN 1 END) as pending_items,
                        COUNT(CASE WHEN queue_status = 'processing' THEN 1 END) as processing_items,
                        COUNT(CASE WHEN queue_status = 'completed' THEN 1 END) as completed_items,
                        COUNT(CASE WHEN queue_status = 'failed' THEN 1 END) as failed_items,
                        AVG(retry_attempt) as avg_retry_attempt,
                        AVG(success_probability) as avg_success_probability,
                        AVG(eligibility_score) as avg_eligibility_score
                    FROM retry_queue
                """)
                
                queue_stats = cursor.fetchone()
                
                # Get queue depth by priority
                cursor.execute("""
                    SELECT 
                        queue_priority,
                        COUNT(*) as count
                    FROM retry_queue
                    WHERE queue_status = 'pending'
                    GROUP BY queue_priority
                    ORDER BY queue_priority
                """)
                
                priority_distribution = {
                    str(row['queue_priority']): row['count'] 
                    for row in cursor.fetchall()
                }
                
                # Get next retry times
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN next_retry_time <= datetime('now') THEN 1 END) as ready_now,
                        COUNT(CASE WHEN next_retry_time <= datetime('now', '+1 hour') THEN 1 END) as ready_1h,
                        COUNT(CASE WHEN next_retry_time <= datetime('now', '+6 hours') THEN 1 END) as ready_6h
                    FROM retry_queue
                    WHERE queue_status = 'pending'
                """)
                
                retry_timing = cursor.fetchone()
                
                # Calculate success rates
                total_items = queue_stats['total_items'] or 0
                completed_items = queue_stats['completed_items'] or 0
                failed_items = queue_stats['failed_items'] or 0
                
                success_rate = (completed_items / (completed_items + failed_items) * 100) if (completed_items + failed_items) > 0 else 0
                
                return {
                    'queue_status': {
                        'total_items': total_items,
                        'pending_items': queue_stats['pending_items'] or 0,
                        'processing_items': queue_stats['processing_items'] or 0,
                        'completed_items': completed_items,
                        'failed_items': failed_items,
                        'success_rate': round(success_rate, 1)
                    },
                    'queue_metrics': {
                        'average_retry_attempt': round(queue_stats['avg_retry_attempt'] or 0, 1),
                        'average_success_probability': round(queue_stats['avg_success_probability'] or 0, 3),
                        'average_eligibility_score': round(queue_stats['avg_eligibility_score'] or 0, 3)
                    },
                    'priority_distribution': priority_distribution,
                    'retry_timing': {
                        'ready_now': retry_timing['ready_now'] or 0,
                        'ready_within_1h': retry_timing['ready_1h'] or 0,
                        'ready_within_6h': retry_timing['ready_6h'] or 0
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting retry queue status: {e}")
            return {
                'queue_status': {},
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
    
    def resolve_error(self, error_id: int, resolution_notes: str, 
                     resolved_by: str = "dashboard_user") -> Dict[str, Any]:
        """
        Mark an error as resolved with resolution notes.
        
        Args:
            error_id: ID of the error to resolve
            resolution_notes: Notes about the resolution
            resolved_by: Who resolved the error
            
        Returns:
            Dictionary containing resolution result
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Update error status
                cursor.execute("""
                    UPDATE error_tracking_enhanced
                    SET 
                        resolution_status = 'resolved',
                        resolution_notes = ?,
                        resolved_by = ?,
                        resolved_at = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    resolution_notes,
                    resolved_by,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    error_id
                ))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Error {error_id} resolved by {resolved_by}")
                    
                    return {
                        'success': True,
                        'error_id': error_id,
                        'resolved_by': resolved_by,
                        'resolved_at': datetime.now().isoformat(),
                        'message': 'Error successfully resolved'
                    }
                else:
                    return {
                        'success': False,
                        'error_id': error_id,
                        'message': 'Error not found or already resolved'
                    }
                    
        except Exception as e:
            self.logger.error(f"Error resolving error {error_id}: {e}")
            return {
                'success': False,
                'error_id': error_id,
                'error': str(e)
            }
    
    def get_error_patterns(self, min_frequency: int = 3) -> Dict[str, Any]:
        """
        Analyze error patterns and recurring issues.
        
        Args:
            min_frequency: Minimum frequency for pattern detection
            
        Returns:
            Dictionary containing error pattern analysis
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get error patterns by type and region
                cursor.execute("""
                    SELECT 
                        error_type,
                        region,
                        COUNT(*) as frequency,
                        AVG(impact_score) as avg_impact,
                        MAX(last_occurrence) as last_seen,
                        GROUP_CONCAT(DISTINCT error_message) as sample_messages
                    FROM error_tracking_enhanced
                    WHERE frequency_count >= ?
                    GROUP BY error_type, region
                    HAVING COUNT(*) >= ?
                    ORDER BY frequency DESC, avg_impact DESC
                """, (min_frequency, min_frequency))
                
                patterns = []
                for row in cursor.fetchall():
                    # Sample messages (first 3)
                    sample_messages = row['sample_messages'].split(',')[:3] if row['sample_messages'] else []
                    
                    patterns.append({
                        'error_type': row['error_type'],
                        'region': row['region'],
                        'frequency': row['frequency'],
                        'average_impact': round(row['avg_impact'] or 0, 2),
                        'last_seen': row['last_seen'],
                        'sample_messages': sample_messages,
                        'pattern_severity': 'high' if row['frequency'] > 10 else 'medium' if row['frequency'] > 5 else 'low'
                    })
                
                # Get correlation analysis (simplified)
                cursor.execute("""
                    SELECT 
                        error_category,
                        COUNT(DISTINCT region) as affected_regions,
                        COUNT(*) as total_occurrences,
                        AVG(retry_count) as avg_retries
                    FROM error_tracking_enhanced
                    GROUP BY error_category
                    ORDER BY total_occurrences DESC
                """)
                
                correlations = []
                for row in cursor.fetchall():
                    correlations.append({
                        'error_category': row['error_category'],
                        'affected_regions': row['affected_regions'],
                        'total_occurrences': row['total_occurrences'],
                        'average_retries': round(row['avg_retries'] or 0, 1),
                        'spread_factor': row['affected_regions'] / max(1, row['total_occurrences']) * 100
                    })
                
                return {
                    'patterns': patterns,
                    'correlations': correlations,
                    'analysis': {
                        'total_patterns_found': len(patterns),
                        'high_severity_patterns': len([p for p in patterns if p['pattern_severity'] == 'high']),
                        'most_frequent_error_type': patterns[0]['error_type'] if patterns else None,
                        'most_affected_region': max(patterns, key=lambda x: x['frequency'])['region'] if patterns else None
                    },
                    'parameters': {
                        'min_frequency': min_frequency
                    },
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error analyzing error patterns: {e}")
            return {
                'patterns': [],
                'correlations': [],
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }


def create_error_dashboard_api(db_path: str = "./data/automation_state.db") -> ErrorDashboardAPI:
    """
    Factory function to create an Error Dashboard API.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Configured ErrorDashboardAPI instance
    """
    return ErrorDashboardAPI(db_path)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Error Dashboard API')
    parser.add_argument('--test-summary', action='store_true',
                       help='Test error summary endpoint')
    parser.add_argument('--test-feed', action='store_true',
                       help='Test live error feed endpoint')
    parser.add_argument('--test-health', action='store_true',
                       help='Test regional error health endpoint')
    parser.add_argument('--test-trends', action='store_true',
                       help='Test error trends endpoint')
    parser.add_argument('--test-patterns', action='store_true',
                       help='Test error patterns endpoint')
    parser.add_argument('--db-path', default='./data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create error dashboard API
    api = create_error_dashboard_api(args.db_path)
    
    try:
        if args.test_summary:
            print("=== Testing Error Summary ===")
            summary = api.get_error_summary()
            print(json.dumps(summary, indent=2))
            
        elif args.test_feed:
            print("=== Testing Live Error Feed ===")
            feed = api.get_live_error_feed(limit=10)
            print(json.dumps(feed, indent=2))
            
        elif args.test_health:
            print("=== Testing Regional Error Health ===")
            health = api.get_regional_error_health()
            print(json.dumps(health, indent=2))
            
        elif args.test_trends:
            print("=== Testing Error Trends ===")
            trends = api.get_error_trends(hours_back=24)
            print(json.dumps(trends, indent=2))
            
        elif args.test_patterns:
            print("=== Testing Error Patterns ===")
            patterns = api.get_error_patterns()
            print(json.dumps(patterns, indent=2))
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")