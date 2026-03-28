#!/usr/bin/env python3
"""
Completion Notifier for Sequential File Processing

This module provides comprehensive completion messaging and reporting for the
sequential file processing system. It generates detailed completion reports,
sends notifications, and provides final statistics when all files are processed.

Key Features:
- Automatic completion detection when all files are processed
- Comprehensive completion reports with detailed statistics
- Integration with dashboard system for real-time notifications
- Final processing summary with success/failure breakdown
- Database cleanup and optimization after completion
- Email and dashboard notifications (configurable)
- Performance analysis and recommendations
"""

import os
import sys
import json
import logging
import sqlite3
import smtplib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger


@dataclass
class CompletionStatistics:
    """Statistics for completed processing session."""
    session_id: str
    total_files: int
    completed_files: int
    failed_files: int
    skipped_files: int
    success_rate: float
    total_processing_time_hours: float
    average_processing_time_hours: float
    total_downloaded_files: int
    unique_regions_processed: int
    unique_variables_processed: int
    start_time: str
    end_time: str
    duration_hours: float


@dataclass
class RegionalCompletionSummary:
    """Completion summary for a specific region."""
    region: str
    region_name: str
    total_files: int
    completed_files: int
    failed_files: int
    success_rate: float
    downloaded_files: int
    processing_time_hours: float
    variable_breakdown: Dict[str, int]
    completion_status: str  # 'completed', 'partial', 'failed'


@dataclass
class CompletionReport:
    """Comprehensive completion report."""
    session_id: str
    completion_time: str
    overall_statistics: CompletionStatistics
    regional_summaries: List[RegionalCompletionSummary]
    performance_analysis: Dict[str, Any]
    recommendations: List[str]
    file_details: List[Dict[str, Any]]
    system_health: Dict[str, Any]
    next_steps: List[str]


@dataclass
class NotificationConfig:
    """Configuration for completion notifications."""
    enable_email: bool = False
    email_recipients: List[str] = None
    smtp_server: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    enable_dashboard: bool = True
    enable_console: bool = True
    enable_file_report: bool = True
    report_directory: str = "reports"


class CompletionNotifier:
    """
    Comprehensive completion notifier for sequential file processing.
    
    This class provides completion detection, report generation, and
    notification capabilities for the sequential file processing system.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db",
                 config: Optional[NotificationConfig] = None):
        """
        Initialize the Completion Notifier.
        
        Args:
            db_path: Path to the SQLite database file
            config: Notification configuration
        """
        self.db_path = db_path
        self.config = config or NotificationConfig()
        self.logger = self._setup_logging()
        
        # Ensure report directory exists
        if self.config.enable_file_report:
            Path(self.config.report_directory).mkdir(parents=True, exist_ok=True)
        
        self.logger.info("Completion Notifier initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.completion_notifier', level=logging.INFO)
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def check_completion_status(self, session_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if processing session is complete.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            Tuple of (is_complete, completion_info)
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get session information
                cursor.execute("""
                    SELECT * FROM sequential_processing_sessions
                    WHERE session_id = ?
                """, (session_id,))
                session = cursor.fetchone()
                
                if not session:
                    return False, {'error': f'Session not found: {session_id}'}
                
                # Get file processing status
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_files,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_files,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_files,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_files,
                        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_files
                    FROM file_processing_progress
                    WHERE session_id = ?
                """, (session_id,))
                file_stats = cursor.fetchone()
                
                total_files = file_stats['total_files']
                pending_files = file_stats['pending_files']
                processing_files = file_stats['processing_files']
                completed_files = file_stats['completed_files']
                failed_files = file_stats['failed_files']
                
                # Check if all files are processed (completed or failed)
                is_complete = (pending_files == 0 and processing_files == 0)
                
                completion_info = {
                    'session_id': session_id,
                    'is_complete': is_complete,
                    'total_files': total_files,
                    'completed_files': completed_files,
                    'failed_files': failed_files,
                    'pending_files': pending_files,
                    'processing_files': processing_files,
                    'completion_percentage': (completed_files + failed_files) / total_files * 100 if total_files > 0 else 0,
                    'success_rate': completed_files / (completed_files + failed_files) * 100 if (completed_files + failed_files) > 0 else 0
                }
                
                return is_complete, completion_info
        
        except Exception as e:
            self.logger.error(f"Error checking completion status: {e}")
            return False, {'error': str(e)}
    
    def generate_completion_report(self, session_id: str) -> CompletionReport:
        """
        Generate comprehensive completion report.
        
        Args:
            session_id: Session ID to generate report for
            
        Returns:
            CompletionReport with detailed statistics and analysis
        """
        try:
            completion_time = datetime.now()
            
            # Get overall statistics
            overall_stats = self._get_overall_statistics(session_id)
            
            # Get regional summaries
            regional_summaries = self._get_regional_summaries(session_id)
            
            # Get performance analysis
            performance_analysis = self._analyze_performance(session_id)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(overall_stats, regional_summaries, performance_analysis)
            
            # Get file details
            file_details = self._get_file_details(session_id)
            
            # Get system health
            system_health = self._get_system_health()
            
            # Generate next steps
            next_steps = self._generate_next_steps(overall_stats, regional_summaries)
            
            report = CompletionReport(
                session_id=session_id,
                completion_time=completion_time.isoformat(),
                overall_statistics=overall_stats,
                regional_summaries=regional_summaries,
                performance_analysis=performance_analysis,
                recommendations=recommendations,
                file_details=file_details,
                system_health=system_health,
                next_steps=next_steps
            )
            
            self.logger.info(f"Completion report generated for session: {session_id}")
            return report
        
        except Exception as e:
            self.logger.error(f"Error generating completion report: {e}")
            # Return minimal report with error
            return CompletionReport(
                session_id=session_id,
                completion_time=datetime.now().isoformat(),
                overall_statistics=CompletionStatistics(
                    session_id=session_id,
                    total_files=0, completed_files=0, failed_files=0, skipped_files=0,
                    success_rate=0.0, total_processing_time_hours=0.0,
                    average_processing_time_hours=0.0, total_downloaded_files=0,
                    unique_regions_processed=0, unique_variables_processed=0,
                    start_time="", end_time="", duration_hours=0.0
                ),
                regional_summaries=[],
                performance_analysis={'error': str(e)},
                recommendations=[f"Error generating report: {str(e)}"],
                file_details=[],
                system_health={'status': 'error'},
                next_steps=["Review system logs for errors"]
            )
    
    def _get_overall_statistics(self, session_id: str) -> CompletionStatistics:
        """Get overall processing statistics."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get session info
                cursor.execute("""
                    SELECT start_time, end_time FROM sequential_processing_sessions
                    WHERE session_id = ?
                """, (session_id,))
                session = cursor.fetchone()
                
                # Get file statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_files,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_files,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_files,
                        COUNT(CASE WHEN status = 'skipped' THEN 1 END) as skipped_files,
                        SUM(COALESCE(processing_duration, 0)) as total_processing_time,
                        AVG(COALESCE(processing_duration, 0)) as avg_processing_time,
                        SUM(COALESCE(downloaded_files, 0)) as total_downloaded_files,
                        COUNT(DISTINCT region) as unique_regions,
                        COUNT(DISTINCT variable_type) as unique_variables
                    FROM file_processing_progress
                    WHERE session_id = ?
                """, (session_id,))
                stats = cursor.fetchone()
                
                # Calculate duration
                start_time = session['start_time'] if session else datetime.now().isoformat()
                end_time = session['end_time'] if session and session['end_time'] else datetime.now().isoformat()
                
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    end_dt = datetime.fromisoformat(end_time)
                    duration_hours = (end_dt - start_dt).total_seconds() / 3600
                except:
                    duration_hours = 0.0
                
                # Calculate success rate
                total = stats['total_files']
                completed = stats['completed_files']
                failed = stats['failed_files']
                success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
                
                return CompletionStatistics(
                    session_id=session_id,
                    total_files=total,
                    completed_files=completed,
                    failed_files=failed,
                    skipped_files=stats['skipped_files'],
                    success_rate=success_rate,
                    total_processing_time_hours=stats['total_processing_time'] or 0.0,
                    average_processing_time_hours=stats['avg_processing_time'] or 0.0,
                    total_downloaded_files=stats['total_downloaded_files'] or 0,
                    unique_regions_processed=stats['unique_regions'] or 0,
                    unique_variables_processed=stats['unique_variables'] or 0,
                    start_time=start_time,
                    end_time=end_time,
                    duration_hours=duration_hours
                )
        
        except Exception as e:
            self.logger.error(f"Error getting overall statistics: {e}")
            return CompletionStatistics(
                session_id=session_id,
                total_files=0, completed_files=0, failed_files=0, skipped_files=0,
                success_rate=0.0, total_processing_time_hours=0.0,
                average_processing_time_hours=0.0, total_downloaded_files=0,
                unique_regions_processed=0, unique_variables_processed=0,
                start_time="", end_time="", duration_hours=0.0
            )
    
    def _get_regional_summaries(self, session_id: str) -> List[RegionalCompletionSummary]:
        """Get regional completion summaries."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        region,
                        COUNT(*) as total_files,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_files,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_files,
                        SUM(COALESCE(processing_duration, 0)) as processing_time,
                        SUM(COALESCE(downloaded_files, 0)) as downloaded_files,
                        variable_type
                    FROM file_processing_progress
                    WHERE session_id = ?
                    GROUP BY region, variable_type
                    ORDER BY region
                """, (session_id,))
                
                # Group by region
                regional_data = {}
                for row in cursor.fetchall():
                    region = row['region']
                    if region not in regional_data:
                        regional_data[region] = {
                            'total_files': 0,
                            'completed_files': 0,
                            'failed_files': 0,
                            'processing_time': 0.0,
                            'downloaded_files': 0,
                            'variables': {}
                        }
                    
                    data = regional_data[region]
                    data['total_files'] += row['total_files']
                    data['completed_files'] += row['completed_files']
                    data['failed_files'] += row['failed_files']
                    data['processing_time'] += row['processing_time'] or 0.0
                    data['downloaded_files'] += row['downloaded_files'] or 0
                    data['variables'][row['variable_type']] = row['total_files']
                
                # Create regional summaries
                summaries = []
                for region, data in regional_data.items():
                    total = data['total_files']
                    completed = data['completed_files']
                    failed = data['failed_files']
                    
                    success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
                    
                    # Determine completion status
                    if failed == 0 and completed == total:
                        completion_status = 'completed'
                    elif completed > 0:
                        completion_status = 'partial'
                    else:
                        completion_status = 'failed'
                    
                    summary = RegionalCompletionSummary(
                        region=region,
                        region_name=region.replace('_', ' ').title(),
                        total_files=total,
                        completed_files=completed,
                        failed_files=failed,
                        success_rate=success_rate,
                        downloaded_files=data['downloaded_files'],
                        processing_time_hours=data['processing_time'],
                        variable_breakdown=data['variables'],
                        completion_status=completion_status
                    )
                    summaries.append(summary)
                
                return summaries
        
        except Exception as e:
            self.logger.error(f"Error getting regional summaries: {e}")
            return []
    
    def _analyze_performance(self, session_id: str) -> Dict[str, Any]:
        """Analyze processing performance."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get processing times
                cursor.execute("""
                    SELECT processing_duration, region, variable_type
                    FROM file_processing_progress
                    WHERE session_id = ? AND processing_duration IS NOT NULL
                """, (session_id,))
                
                processing_times = []
                region_times = {}
                variable_times = {}
                
                for row in cursor.fetchall():
                    duration = row['processing_duration']
                    region = row['region']
                    variable = row['variable_type']
                    
                    processing_times.append(duration)
                    
                    if region not in region_times:
                        region_times[region] = []
                    region_times[region].append(duration)
                    
                    if variable not in variable_times:
                        variable_times[variable] = []
                    variable_times[variable].append(duration)
                
                if not processing_times:
                    return {'message': 'No processing time data available'}
                
                # Calculate statistics
                avg_time = sum(processing_times) / len(processing_times)
                min_time = min(processing_times)
                max_time = max(processing_times)
                
                # Regional performance
                regional_performance = {}
                for region, times in region_times.items():
                    regional_performance[region] = {
                        'average_time': sum(times) / len(times),
                        'file_count': len(times),
                        'total_time': sum(times)
                    }
                
                # Variable performance
                variable_performance = {}
                for variable, times in variable_times.items():
                    variable_performance[variable] = {
                        'average_time': sum(times) / len(times),
                        'file_count': len(times),
                        'total_time': sum(times)
                    }
                
                return {
                    'overall_performance': {
                        'average_processing_time_hours': avg_time,
                        'fastest_processing_time_hours': min_time,
                        'slowest_processing_time_hours': max_time,
                        'total_files_with_timing': len(processing_times)
                    },
                    'regional_performance': regional_performance,
                    'variable_performance': variable_performance,
                    'performance_insights': self._generate_performance_insights(
                        avg_time, min_time, max_time, regional_performance, variable_performance
                    )
                }
        
        except Exception as e:
            self.logger.error(f"Error analyzing performance: {e}")
            return {'error': str(e)}
    
    def _generate_performance_insights(self, avg_time: float, min_time: float, max_time: float,
                                     regional_perf: Dict, variable_perf: Dict) -> List[str]:
        """Generate performance insights."""
        insights = []
        
        # Overall performance insights
        if max_time > avg_time * 2:
            insights.append(f"Some files took significantly longer than average ({max_time:.2f}h vs {avg_time:.2f}h avg)")
        
        if min_time < avg_time * 0.5:
            insights.append(f"Some files processed very quickly ({min_time:.2f}h vs {avg_time:.2f}h avg)")
        
        # Regional insights
        if regional_perf:
            fastest_region = min(regional_perf.items(), key=lambda x: x[1]['average_time'])
            slowest_region = max(regional_perf.items(), key=lambda x: x[1]['average_time'])
            
            if fastest_region[1]['average_time'] * 1.5 < slowest_region[1]['average_time']:
                insights.append(f"Region {fastest_region[0]} processed fastest ({fastest_region[1]['average_time']:.2f}h avg)")
                insights.append(f"Region {slowest_region[0]} processed slowest ({slowest_region[1]['average_time']:.2f}h avg)")
        
        # Variable insights
        if variable_perf:
            fastest_var = min(variable_perf.items(), key=lambda x: x[1]['average_time'])
            slowest_var = max(variable_perf.items(), key=lambda x: x[1]['average_time'])
            
            insights.append(f"Variable type '{fastest_var[0]}' processed fastest ({fastest_var[1]['average_time']:.2f}h avg)")
            insights.append(f"Variable type '{slowest_var[0]}' processed slowest ({slowest_var[1]['average_time']:.2f}h avg)")
        
        return insights
    
    def _generate_recommendations(self, overall_stats: CompletionStatistics,
                                regional_summaries: List[RegionalCompletionSummary],
                                performance_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on completion analysis."""
        recommendations = []
        
        # Success rate recommendations
        if overall_stats.success_rate < 90:
            recommendations.append(f"Success rate is {overall_stats.success_rate:.1f}% - investigate failed requests for common issues")
        elif overall_stats.success_rate >= 95:
            recommendations.append("Excellent success rate achieved - current process is working well")
        
        # Performance recommendations
        if overall_stats.average_processing_time_hours > 3:
            recommendations.append("Average processing time is high - consider optimizing request parameters or system resources")
        
        # Regional recommendations
        failed_regions = [r for r in regional_summaries if r.completion_status == 'failed']
        if failed_regions:
            recommendations.append(f"Regions with failures: {', '.join([r.region for r in failed_regions])} - review region-specific issues")
        
        partial_regions = [r for r in regional_summaries if r.completion_status == 'partial']
        if partial_regions:
            recommendations.append(f"Regions with partial completion: {', '.join([r.region for r in partial_regions])} - consider retry processing")
        
        # Download recommendations
        if overall_stats.total_downloaded_files == 0:
            recommendations.append("No files were downloaded - verify download automation is working correctly")
        elif overall_stats.total_downloaded_files < overall_stats.completed_files * 0.8:
            recommendations.append("Download count is lower than expected - some completed requests may not have downloaded files")
        
        # System recommendations
        if overall_stats.duration_hours > 24:
            recommendations.append("Processing took over 24 hours - consider parallel processing or system optimization")
        
        if not recommendations:
            recommendations.append("Processing completed successfully with no major issues identified")
        
        return recommendations
    
    def _get_file_details(self, session_id: str) -> List[Dict[str, Any]]:
        """Get detailed file processing information."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT filename, region, variable_type, status, request_id,
                           submission_time, completion_time, processing_duration,
                           error_message, retry_count, downloaded_files
                    FROM file_processing_progress
                    WHERE session_id = ?
                    ORDER BY filename
                """, (session_id,))
                
                file_details = []
                for row in cursor.fetchall():
                    file_details.append({
                        'filename': row['filename'],
                        'region': row['region'],
                        'variable_type': row['variable_type'],
                        'status': row['status'],
                        'request_id': row['request_id'],
                        'submission_time': row['submission_time'],
                        'completion_time': row['completion_time'],
                        'processing_duration_hours': row['processing_duration'],
                        'error_message': row['error_message'],
                        'retry_count': row['retry_count'],
                        'downloaded_files': row['downloaded_files']
                    })
                
                return file_details
        
        except Exception as e:
            self.logger.error(f"Error getting file details: {e}")
            return []
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get system health information."""
        try:
            # Basic system health check
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check database connectivity
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # Check recent activity
                cursor.execute("""
                    SELECT COUNT(*) FROM rda_requests 
                    WHERE date_rqst > datetime('now', '-24 hours')
                """)
                recent_requests = cursor.fetchone()[0]
                
                return {
                    'database_status': 'healthy',
                    'database_tables': table_count,
                    'recent_requests_24h': recent_requests,
                    'check_time': datetime.now().isoformat()
                }
        
        except Exception as e:
            self.logger.error(f"Error getting system health: {e}")
            return {
                'database_status': 'error',
                'error': str(e),
                'check_time': datetime.now().isoformat()
            }
    
    def _generate_next_steps(self, overall_stats: CompletionStatistics,
                           regional_summaries: List[RegionalCompletionSummary]) -> List[str]:
        """Generate next steps based on completion results."""
        next_steps = []
        
        # Based on success rate
        if overall_stats.success_rate < 100:
            next_steps.append("Review failed requests and consider retry processing")
            next_steps.append("Analyze error patterns to prevent future failures")
        
        # Based on regional results
        incomplete_regions = [r for r in regional_summaries if r.completion_status != 'completed']
        if incomplete_regions:
            next_steps.append(f"Focus on incomplete regions: {', '.join([r.region for r in incomplete_regions])}")
        
        # General next steps
        next_steps.extend([
            "Verify downloaded files are properly organized",
            "Update regional progress tracking in dashboard",
            "Archive processing logs and reports",
            "Plan next processing cycle if needed"
        ])
        
        return next_steps
    
    def send_completion_notification(self, report: CompletionReport) -> Dict[str, bool]:
        """
        Send completion notifications through configured channels.
        
        Args:
            report: Completion report to send
            
        Returns:
            Dictionary with notification results
        """
        results = {}
        
        # Console notification
        if self.config.enable_console:
            results['console'] = self._send_console_notification(report)
        
        # File report
        if self.config.enable_file_report:
            results['file_report'] = self._save_file_report(report)
        
        # Email notification
        if self.config.enable_email and self.config.email_recipients:
            results['email'] = self._send_email_notification(report)
        
        # Dashboard notification
        if self.config.enable_dashboard:
            results['dashboard'] = self._send_dashboard_notification(report)
        
        return results
    
    def _send_console_notification(self, report: CompletionReport) -> bool:
        """Send console notification."""
        try:
            print("\n" + "="*80)
            print("🎉 SEQUENTIAL FILE PROCESSING COMPLETED")
            print("="*80)
            print(f"Session ID: {report.session_id}")
            print(f"Completion Time: {report.completion_time}")
            print(f"Total Files: {report.overall_statistics.total_files}")
            print(f"Completed: {report.overall_statistics.completed_files}")
            print(f"Failed: {report.overall_statistics.failed_files}")
            print(f"Success Rate: {report.overall_statistics.success_rate:.1f}%")
            print(f"Duration: {report.overall_statistics.duration_hours:.2f} hours")
            print(f"Downloaded Files: {report.overall_statistics.total_downloaded_files}")
            
            if report.regional_summaries:
                print(f"\nRegional Summary:")
                for region in report.regional_summaries:
                    status_icon = "✅" if region.completion_status == "completed" else "⚠️" if region.completion_status == "partial" else "❌"
                    print(f"  {status_icon} {region.region}: {region.completed_files}/{region.total_files} files ({region.success_rate:.1f}%)")
            
            if report.recommendations:
                print(f"\nRecommendations:")
                for rec in report.recommendations:
                    print(f"  • {rec}")
            
            print("="*80)
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending console notification: {e}")
            return False
    
    def _save_file_report(self, report: CompletionReport) -> bool:
        """Save completion report to file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_filename = f"completion_report_{report.session_id}_{timestamp}.json"
            report_path = Path(self.config.report_directory) / report_filename
            
            # Convert report to JSON-serializable format
            report_data = asdict(report)
            
            with open(report_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            self.logger.info(f"Completion report saved: {report_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving file report: {e}")
            return False
    
    def _send_email_notification(self, report: CompletionReport) -> bool:
        """Send email notification."""
        try:
            if not self.config.email_recipients:
                return False
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.config.smtp_username
            msg['To'] = ', '.join(self.config.email_recipients)
            msg['Subject'] = f"RDA Sequential Processing Complete - {report.session_id}"
            
            # Create email body
            body = self._create_email_body(report)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                if self.config.smtp_username and self.config.smtp_password:
                    server.starttls()
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                server.send_message(msg)
            
            self.logger.info(f"Email notification sent to {len(self.config.email_recipients)} recipients")
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending email notification: {e}")
            return False
    
    def _create_email_body(self, report: CompletionReport) -> str:
        """Create HTML email body."""
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .stats {{ background-color: #f5f5f5; padding: 15px; margin: 10px 0; }}
                .success {{ color: #4CAF50; }}
                .warning {{ color: #FF9800; }}
                .error {{ color: #f44336; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Sequential File Processing Complete</h1>
                <p>Session: {report.session_id}</p>
            </div>
            
            <div class="content">
                <div class="stats">
                    <h2>Overall Statistics</h2>
                    <p><strong>Total Files:</strong> {report.overall_statistics.total_files}</p>
                    <p><strong>Completed:</strong> <span class="success">{report.overall_statistics.completed_files}</span></p>
                    <p><strong>Failed:</strong> <span class="error">{report.overall_statistics.failed_files}</span></p>
                    <p><strong>Success Rate:</strong> {report.overall_statistics.success_rate:.1f}%</p>
                    <p><strong>Duration:</strong> {report.overall_statistics.duration_hours:.2f} hours</p>
                    <p><strong>Downloaded Files:</strong> {report.overall_statistics.total_downloaded_files}</p>
                </div>
                
                <h2>Regional Summary</h2>
                <table>
                    <tr>
                        <th>Region</th>
                        <th>Status</th>
                        <th>Files</th>
                        <th>Success Rate</th>
                        <th>Downloaded</th>
                    </tr>
        """
        
        for region in report.regional_summaries:
            status_class = "success" if region.completion_status == "completed" else "warning" if region.completion_status == "partial" else "error"
            html += f"""
                    <tr>
                        <td>{region.region}</td>
                        <td><span class="{status_class}">{region.completion_status.title()}</span></td>
                        <td>{region.completed_files}/{region.total_files}</td>
                        <td>{region.success_rate:.1f}%</td>
                        <td>{region.downloaded_files}</td>
                    </tr>
            """
        
        html += """
                </table>
                
                <h2>Recommendations</h2>
                <ul>
        """
        
        for rec in report.recommendations:
            html += f"<li>{rec}</li>"
        
        html += """
                </ul>
                
                <h2>Next Steps</h2>
                <ul>
        """
        
        for step in report.next_steps:
            html += f"<li>{step}</li>"
        
        html += f"""
                </ul>
                
                <p><em>Report generated at: {report.completion_time}</em></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _send_dashboard_notification(self, report: CompletionReport) -> bool:
        """Send dashboard notification."""
        try:
            # This would integrate with the dashboard system
            # For now, just log the completion
            self.logger.info(f"Dashboard notification: Sequential processing completed for session {report.session_id}")
            
            # In a real implementation, this might:
            # 1. Update dashboard database with completion status
            # 2. Send real-time notification to dashboard users
            # 3. Update progress indicators
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending dashboard notification: {e}")
            return False
    
    def cleanup_completed_session(self, session_id: str) -> bool:
        """
        Clean up completed session data and optimize database.
        
        Args:
            session_id: Session ID to clean up
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Archive session data (optional - could move to archive tables)
                # For now, just mark as archived
                cursor.execute("""
                    UPDATE sequential_processing_sessions
                    SET status = 'archived', updated_at = ?
                    WHERE session_id = ?
                """, (datetime.now().isoformat(), session_id))
                
                # Clean up old snapshots (keep only last 10)
                cursor.execute("""
                    DELETE FROM progress_snapshots
                    WHERE session_id = ? AND id NOT IN (
                        SELECT id FROM progress_snapshots
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT 10
                    )
                """, (session_id, session_id))
                
                # Optimize database
                cursor.execute("VACUUM")
                cursor.execute("ANALYZE")
                
                conn.commit()
            
            self.logger.info(f"Session cleanup completed: {session_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error cleaning up session: {e}")
            return False


def create_completion_notifier(db_path: str = "src/python/data/automation_state.db",
                             config: Optional[NotificationConfig] = None) -> CompletionNotifier:
    """
    Factory function to create a Completion Notifier.
    
    Args:
        db_path: Path to the SQLite database file
        config: Notification configuration
        
    Returns:
        Configured CompletionNotifier instance
    """
    return CompletionNotifier(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Completion Notifier')
    parser.add_argument('--session-id', type=str, required=True,
                       help='Session ID to check/notify')
    parser.add_argument('--check-completion', action='store_true',
                       help='Check if session is complete')
    parser.add_argument('--generate-report', action='store_true',
                       help='Generate completion report')
    parser.add_argument('--send-notifications', action='store_true',
                       help='Send completion notifications')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up completed session')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    parser.add_argument('--email-recipients', nargs='+',
                       help='Email recipients for notifications')
    
    args = parser.parse_args()
    
    # Create notification config
    config = NotificationConfig()
    if args.email_recipients:
        config.enable_email = True
        config.email_recipients = args.email_recipients
    
    # Create completion notifier
    notifier = create_completion_notifier(args.db_path, config)
    
    try:
        if args.check_completion:
            print(f"=== Checking Completion Status: {args.session_id} ===")
            is_complete, info = notifier.check_completion_status(args.session_id)
            
            print(f"Complete: {is_complete}")
            print(f"Total Files: {info.get('total_files', 0)}")
            print(f"Completed: {info.get('completed_files', 0)}")
            print(f"Failed: {info.get('failed_files', 0)}")
            print(f"Pending: {info.get('pending_files', 0)}")
            print(f"Processing: {info.get('processing_files', 0)}")
            print(f"Progress: {info.get('completion_percentage', 0):.1f}%")
            print(f"Success Rate: {info.get('success_rate', 0):.1f}%")
        
        elif args.generate_report:
            print(f"=== Generating Completion Report: {args.session_id} ===")
            report = notifier.generate_completion_report(args.session_id)
            print(json.dumps(asdict(report), indent=2, default=str))
        
        elif args.send_notifications:
            print(f"=== Sending Completion Notifications: {args.session_id} ===")
            report = notifier.generate_completion_report(args.session_id)
            results = notifier.send_completion_notification(report)
            
            for channel, success in results.items():
                status = "✅ Success" if success else "❌ Failed"
                print(f"{channel}: {status}")
        
        elif args.cleanup:
            print(f"=== Cleaning Up Session: {args.session_id} ===")
            success = notifier.cleanup_completed_session(args.session_id)
            print(f"Cleanup: {'✅ Success' if success else '❌ Failed'}")
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("COMPLETION NOTIFIER EXAMPLES")
            print("="*60)
            print("# Check completion status:")
            print("python automation/completion_notifier.py --session-id SESSION_ID --check-completion")
            print("\n# Generate completion report:")
            print("python automation/completion_notifier.py --session-id SESSION_ID --generate-report")
            print("\n# Send notifications:")
            print("python automation/completion_notifier.py --session-id SESSION_ID --send-notifications")
            print("\n# Clean up session:")
            print("python automation/completion_notifier.py --session-id SESSION_ID --cleanup")
            print("="*60)
    
    except Exception as e:
        print(f"Error: {e}")