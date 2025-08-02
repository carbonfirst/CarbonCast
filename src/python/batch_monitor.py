#!/usr/bin/env python3
"""
Comprehensive Monitoring and Dashboard System for Batch Automation

This module provides real-time monitoring, progress tracking, and a web-based
dashboard for the batch automation system.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import threading
from flask import Flask, render_template, jsonify, request
import webbrowser

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_automation import BatchAutomationSystem, RequestStatus
from batch_queue_manager import IntelligentQueueManager


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: str
    total_requests: int
    pending_requests: int
    processing_requests: int
    completed_requests: int
    failed_requests: int
    downloaded_requests: int
    success_rate: float
    average_processing_time: float
    estimated_completion_time: Optional[str]
    system_load: float
    memory_usage_mb: float
    disk_usage_gb: float


class BatchMonitor:
    """Comprehensive monitoring system for batch automation."""
    
    def __init__(self, batch_system: BatchAutomationSystem, queue_manager: IntelligentQueueManager):
        self.batch_system = batch_system
        self.queue_manager = queue_manager
        self.logger = logging.getLogger('batch_monitor')
        
        # Metrics storage
        self.metrics_history: List[SystemMetrics] = []
        self.max_history_size = 1000
        
        # Performance tracking
        self.start_time = datetime.now()
        self.last_update_time = datetime.now()
        
        # Web dashboard
        self.app = Flask(__name__)
        self.setup_web_routes()
        
        # Monitoring thread
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Load historical metrics
        self._load_metrics_history()
    
    def _load_metrics_history(self):
        """Load historical metrics from file."""
        metrics_file = Path("metrics_history.json")
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    metrics_data = json.load(f)
                
                self.metrics_history = [
                    SystemMetrics(**metric) for metric in metrics_data[-self.max_history_size:]
                ]
                
                self.logger.info(f"Loaded {len(self.metrics_history)} historical metrics")
            except Exception as e:
                self.logger.error(f"Error loading metrics history: {e}")
    
    def _save_metrics_history(self):
        """Save metrics history to file."""
        try:
            metrics_data = [asdict(metric) for metric in self.metrics_history[-self.max_history_size:]]
            
            with open("metrics_history.json", 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            self.logger.debug("Metrics history saved")
        except Exception as e:
            self.logger.error(f"Error saving metrics history: {e}")
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        try:
            # Get request statistics
            status_counts = {}
            processing_times = []
            
            for status in self.batch_system.requests_state.values():
                status_counts[status.status] = status_counts.get(status.status, 0) + 1
                
                # Calculate processing time for completed requests
                if (status.status in ["completed", "downloaded"] and 
                    status.submission_time and status.completion_time):
                    try:
                        start = datetime.fromisoformat(status.submission_time)
                        end = datetime.fromisoformat(status.completion_time)
                        processing_times.append((end - start).total_seconds() / 3600)  # Hours
                    except:
                        pass
            
            total_requests = len(self.batch_system.requests_state)
            completed_requests = status_counts.get("completed", 0) + status_counts.get("downloaded", 0)
            failed_requests = status_counts.get("failed", 0)
            
            # Calculate success rate
            total_finished = completed_requests + failed_requests
            success_rate = (completed_requests / total_finished * 100) if total_finished > 0 else 0
            
            # Calculate average processing time
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # Estimate completion time
            pending_and_processing = (
                status_counts.get("pending", 0) + 
                status_counts.get("submitted", 0) + 
                status_counts.get("processing", 0)
            )
            
            estimated_completion = None
            if pending_and_processing > 0 and avg_processing_time > 0:
                remaining_hours = pending_and_processing * avg_processing_time
                estimated_completion = (datetime.now() + timedelta(hours=remaining_hours)).isoformat()
            
            # System resource metrics (simplified)
            try:
                import psutil
                system_load = psutil.cpu_percent()
                memory_usage = psutil.virtual_memory().used / (1024 * 1024)  # MB
                disk_usage = psutil.disk_usage('.').used / (1024 * 1024 * 1024)  # GB
            except ImportError:
                self.logger.warning("psutil not available, using default system metrics")
                system_load = 0.0
                memory_usage = 0.0
                disk_usage = 0.0
            except Exception as e:
                self.logger.warning(f"Error collecting system metrics with psutil: {e}")
                system_load = 0.0
                memory_usage = 0.0
                disk_usage = 0.0
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                total_requests=total_requests,
                pending_requests=status_counts.get("pending", 0),
                processing_requests=status_counts.get("processing", 0) + status_counts.get("submitted", 0),
                completed_requests=status_counts.get("completed", 0),
                failed_requests=failed_requests,
                downloaded_requests=status_counts.get("downloaded", 0),
                success_rate=success_rate,
                average_processing_time=avg_processing_time,
                estimated_completion_time=estimated_completion,
                system_load=system_load,
                memory_usage_mb=memory_usage,
                disk_usage_gb=disk_usage
            )
        
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                total_requests=0, pending_requests=0, processing_requests=0,
                completed_requests=0, failed_requests=0, downloaded_requests=0,
                success_rate=0, average_processing_time=0, estimated_completion_time=None,
                system_load=0, memory_usage_mb=0, disk_usage_gb=0
            )
    
    def update_metrics(self):
        """Update metrics and add to history."""
        metrics = self.collect_system_metrics()
        self.metrics_history.append(metrics)
        
        # Keep only recent metrics
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
        
        self.last_update_time = datetime.now()
        self._save_metrics_history()
        
        return metrics
    
    def get_progress_summary(self) -> Dict:
        """Get comprehensive progress summary."""
        if not self.metrics_history:
            self.update_metrics()
        
        latest_metrics = self.metrics_history[-1]
        
        # Calculate progress percentage
        total = latest_metrics.total_requests
        downloaded = latest_metrics.downloaded_requests
        progress_percentage = (downloaded / total * 100) if total > 0 else 0
        
        # Calculate rates
        runtime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        completion_rate = downloaded / runtime_hours if runtime_hours > 0 else 0
        
        # Get queue statistics
        queue_stats = self.queue_manager.get_queue_statistics()
        
        return {
            'overall_progress': {
                'total_requests': total,
                'downloaded_requests': downloaded,
                'progress_percentage': progress_percentage,
                'completion_rate_per_hour': completion_rate,
                'estimated_completion': latest_metrics.estimated_completion_time
            },
            'current_status': {
                'pending': latest_metrics.pending_requests,
                'processing': latest_metrics.processing_requests,
                'completed': latest_metrics.completed_requests,
                'failed': latest_metrics.failed_requests,
                'downloaded': downloaded
            },
            'performance_metrics': {
                'success_rate': latest_metrics.success_rate,
                'average_processing_time_hours': latest_metrics.average_processing_time,
                'system_load': latest_metrics.system_load,
                'memory_usage_mb': latest_metrics.memory_usage_mb
            },
            'queue_statistics': queue_stats,
            'runtime_info': {
                'start_time': self.start_time.isoformat(),
                'runtime_hours': runtime_hours,
                'last_update': self.last_update_time.isoformat()
            }
        }
    
    def print_progress_report(self):
        """Print detailed progress report to console."""
        summary = self.get_progress_summary()
        
        print("\n" + "="*80)
        print("BATCH AUTOMATION PROGRESS REPORT")
        print("="*80)
        
        # Overall progress
        overall = summary['overall_progress']
        print(f"Overall Progress: {overall['downloaded_requests']}/{overall['total_requests']} "
              f"({overall['progress_percentage']:.1f}%)")
        
        if overall['estimated_completion']:
            est_time = datetime.fromisoformat(overall['estimated_completion'])
            print(f"Estimated Completion: {est_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"Completion Rate: {overall['completion_rate_per_hour']:.2f} requests/hour")
        
        # Current status
        status = summary['current_status']
        print(f"\nCurrent Status:")
        print(f"  Pending: {status['pending']}")
        print(f"  Processing: {status['processing']}")
        print(f"  Completed: {status['completed']}")
        print(f"  Downloaded: {status['downloaded']}")
        print(f"  Failed: {status['failed']}")
        
        # Performance metrics
        perf = summary['performance_metrics']
        print(f"\nPerformance Metrics:")
        print(f"  Success Rate: {perf['success_rate']:.1f}%")
        print(f"  Avg Processing Time: {perf['average_processing_time_hours']:.2f} hours")
        print(f"  System Load: {perf['system_load']:.1f}%")
        print(f"  Memory Usage: {perf['memory_usage_mb']:.1f} MB")
        
        # Runtime info
        runtime = summary['runtime_info']
        print(f"\nRuntime Information:")
        print(f"  Started: {datetime.fromisoformat(runtime['start_time']).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Runtime: {runtime['runtime_hours']:.2f} hours")
        print(f"  Last Update: {datetime.fromisoformat(runtime['last_update']).strftime('%H:%M:%S')}")
        
        print("="*80)
    
    def get_live_status(self) -> Dict:
        """Get live status data from batch_automation_state.json."""
        try:
            state_file = Path("batch_automation_state.json")
            if not state_file.exists():
                return self._get_empty_status()
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            # Count statuses
            status_counts = {}
            region_counts = {}
            variable_counts = {}
            
            for request_data in state_data.values():
                status = request_data.get('status', 'unknown')
                region = request_data.get('region', 'UNKNOWN')
                variable = request_data.get('variable_type', 'unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                if region != 'UNKNOWN':
                    region_counts[region] = region_counts.get(region, 0) + 1
                if variable != 'unknown':
                    variable_counts[variable] = variable_counts.get(variable, 0) + 1
            
            total_requests = len(state_data)
            completed = status_counts.get('downloaded', 0)
            failed = status_counts.get('failed', 0)
            pending = status_counts.get('pending', 0)
            processing = status_counts.get('processing', 0) + status_counts.get('submitted', 0)
            
            progress_percentage = (completed / total_requests * 100) if total_requests > 0 else 0
            success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0
            
            return {
                'overall_progress': {
                    'total_requests': total_requests,
                    'completed_requests': completed,
                    'progress_percentage': progress_percentage,
                    'success_rate': success_rate,
                    'completion_rate_per_hour': 0  # Will be calculated if needed
                },
                'current_status': {
                    'pending': pending,
                    'processing': processing,
                    'completed': status_counts.get('completed', 0),
                    'failed': failed,
                    'downloaded': completed
                },
                'performance_metrics': {
                    'success_rate': success_rate,
                    'average_processing_time_hours': 0,
                    'system_load': 0,
                    'memory_usage_mb': 0
                },
                'regions': region_counts,
                'variables': variable_counts,
                'last_updated': datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting live status: {e}")
            return self._get_empty_status()
    
    def get_live_requests_data(self) -> List[Dict]:
        """Get live requests data from batch_automation_state.json."""
        try:
            state_file = Path("batch_automation_state.json")
            if not state_file.exists():
                return []
            
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            
            requests_data = []
            for control_file, request_data in state_data.items():
                requests_data.append({
                    'control_file': Path(control_file).name,
                    'status': request_data.get('status', 'unknown'),
                    'region': request_data.get('region', 'UNKNOWN'),
                    'variable_type': request_data.get('variable_type', 'unknown'),
                    'request_id': request_data.get('request_id'),
                    'submission_time': request_data.get('submission_time'),
                    'completion_time': request_data.get('completion_time'),
                    'download_time': request_data.get('download_time'),
                    'error_message': request_data.get('error_message'),
                    'retry_count': request_data.get('retry_count', 0)
                })
            
            return requests_data
        
        except Exception as e:
            self.logger.error(f"Error getting live requests data: {e}")
            return []
    
    def get_live_queue_data(self) -> Dict:
        """Get live queue data from queue_state.json."""
        try:
            queue_file = Path("queue_state.json")
            if not queue_file.exists():
                return self._get_empty_queue_data()
            
            with open(queue_file, 'r') as f:
                queue_data = json.load(f)
            
            return {
                'priority_queue_size': len(queue_data.get('priority_queue', [])),
                'processing_queue_size': len(queue_data.get('processing_queue', [])),
                'completed_queue_size': len(queue_data.get('completed_queue', [])),
                'failed_queue_size': len(queue_data.get('failed_queue', [])),
                'metadata': queue_data.get('queue_metadata', {}),
                'last_updated': datetime.now().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting live queue data: {e}")
            return self._get_empty_queue_data()
    
    def _get_empty_status(self) -> Dict:
        """Return empty status structure."""
        return {
            'overall_progress': {
                'total_requests': 0,
                'completed_requests': 0,
                'progress_percentage': 0,
                'success_rate': 0,
                'completion_rate_per_hour': 0
            },
            'current_status': {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0,
                'downloaded': 0
            },
            'performance_metrics': {
                'success_rate': 0,
                'average_processing_time_hours': 0,
                'system_load': 0,
                'memory_usage_mb': 0
            },
            'regions': {},
            'variables': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def _get_empty_queue_data(self) -> Dict:
        """Return empty queue data structure."""
        return {
            'priority_queue_size': 0,
            'processing_queue_size': 0,
            'completed_queue_size': 0,
            'failed_queue_size': 0,
            'metadata': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def start_monitoring(self, update_interval: int = 60):
        """Start continuous monitoring in background thread."""
        if self.monitoring_active:
            self.logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    self.update_metrics()
                    self.print_progress_report()
                    time.sleep(update_interval)
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Short delay before retry
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.logger.info(f"Started monitoring with {update_interval}s update interval")
    
    def stop_monitoring(self):
        """Stop continuous monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        self.logger.info("Stopped monitoring")
    
    def setup_web_routes(self):
        """Setup Flask web routes for dashboard."""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            """API endpoint for current status."""
            return jsonify(self.get_live_status())
        
        @self.app.route('/api/metrics')
        def api_metrics():
            """API endpoint for metrics history."""
            # Return last 100 metrics for chart
            recent_metrics = self.metrics_history[-100:]
            return jsonify([asdict(m) for m in recent_metrics])
        
        @self.app.route('/api/requests')
        def api_requests():
            """API endpoint for detailed request information."""
            return jsonify(self.get_live_requests_data())
        
        @self.app.route('/api/queue')
        def api_queue():
            """API endpoint for queue information."""
            return jsonify(self.get_live_queue_data())
        
        @self.app.route('/api/live-data')
        def api_live_data():
            """API endpoint for complete live data refresh."""
            return jsonify({
                'status': self.get_live_status(),
                'requests': self.get_live_requests_data(),
                'queue': self.get_live_queue_data(),
                'timestamp': datetime.now().isoformat()
            })
    
    def create_dashboard_template(self):
        """Create HTML template for web dashboard."""
        template_dir = Path("templates")
        template_dir.mkdir(exist_ok=True)
        
        dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batch Automation Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 2em; font-weight: bold; color: #2196F3; }
        .metric-label { color: #666; margin-top: 5px; }
        .progress-bar { width: 100%; height: 20px; background-color: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background-color: #4CAF50; transition: width 0.3s ease; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .status-item { text-align: center; padding: 10px; border-radius: 4px; }
        .status-pending { background-color: #FFF3E0; color: #F57C00; }
        .status-processing { background-color: #E3F2FD; color: #1976D2; }
        .status-completed { background-color: #E8F5E8; color: #388E3C; }
        .status-failed { background-color: #FFEBEE; color: #D32F2F; }
        .refresh-btn { background-color: #2196F3; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
        .refresh-btn:hover { background-color: #1976D2; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Batch Automation Dashboard</h1>
            <button class="refresh-btn" onclick="refreshData()">Refresh Data</button>
            <p>Last updated: <span id="lastUpdate">Loading...</span></p>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="totalRequests">-</div>
                <div class="metric-label">Total Requests</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="completedRequests">-</div>
                <div class="metric-label">Completed</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressBar" style="width: 0%"></div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="successRate">-</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="completionRate">-</div>
                <div class="metric-label">Requests/Hour</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Progress Over Time</h3>
            <canvas id="progressChart" width="400" height="200"></canvas>
        </div>
        
        <div class="chart-container">
            <h3>Current Status Distribution</h3>
            <div class="status-grid" id="statusGrid">
                <!-- Status items will be populated by JavaScript -->
            </div>
        </div>
        
        <div class="chart-container">
            <h3>System Performance</h3>
            <canvas id="performanceChart" width="400" height="200"></canvas>
        </div>
    </div>
    
    <script>
        let progressChart, performanceChart;
        
        function initCharts() {
            // Progress chart
            const progressCtx = document.getElementById('progressChart').getContext('2d');
            progressChart = new Chart(progressCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Completed Requests',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
            
            // Performance chart
            const performanceCtx = document.getElementById('performanceChart').getContext('2d');
            performanceChart = new Chart(performanceCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'System Load (%)',
                            data: [],
                            borderColor: '#FF9800',
                            backgroundColor: 'rgba(255, 152, 0, 0.1)',
                            yAxisID: 'y'
                        },
                        {
                            label: 'Memory Usage (MB)',
                            data: [],
                            borderColor: '#9C27B0',
                            backgroundColor: 'rgba(156, 39, 176, 0.1)',
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { type: 'linear', display: true, position: 'left' },
                        y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false } }
                    }
                }
            });
        }
        
        async function refreshData() {
            try {
                // Fetch current status
                const statusResponse = await fetch('/api/status');
                const statusData = await statusResponse.json();
                
                // Update metrics
                updateMetrics(statusData);
                
                // Fetch and update charts
                const metricsResponse = await fetch('/api/metrics');
                const metricsData = await metricsResponse.json();
                updateCharts(metricsData);
                
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }
        
        function updateMetrics(data) {
            const overall = data.overall_progress;
            const status = data.current_status;
            const performance = data.performance_metrics;
            
            document.getElementById('totalRequests').textContent = overall.total_requests;
            document.getElementById('completedRequests').textContent = overall.downloaded_requests;
            document.getElementById('successRate').textContent = performance.success_rate.toFixed(1) + '%';
            document.getElementById('completionRate').textContent = overall.completion_rate_per_hour.toFixed(2);
            
            // Update progress bar
            const progressPercent = overall.progress_percentage;
            document.getElementById('progressBar').style.width = progressPercent + '%';
            
            // Update status grid
            const statusGrid = document.getElementById('statusGrid');
            statusGrid.innerHTML = `
                <div class="status-item status-pending">
                    <div style="font-size: 1.5em; font-weight: bold;">${status.pending}</div>
                    <div>Pending</div>
                </div>
                <div class="status-item status-processing">
                    <div style="font-size: 1.5em; font-weight: bold;">${status.processing}</div>
                    <div>Processing</div>
                </div>
                <div class="status-item status-completed">
                    <div style="font-size: 1.5em; font-weight: bold;">${status.completed}</div>
                    <div>Completed</div>
                </div>
                <div class="status-item status-failed">
                    <div style="font-size: 1.5em; font-weight: bold;">${status.failed}</div>
                    <div>Failed</div>
                </div>
            `;
        }
        
        function updateCharts(metricsData) {
            const labels = metricsData.map(m => new Date(m.timestamp).toLocaleTimeString());
            const completedData = metricsData.map(m => m.downloaded_requests);
            const systemLoadData = metricsData.map(m => m.system_load);
            const memoryData = metricsData.map(m => m.memory_usage_mb);
            
            // Update progress chart
            progressChart.data.labels = labels;
            progressChart.data.datasets[0].data = completedData;
            progressChart.update();
            
            // Update performance chart
            performanceChart.data.labels = labels;
            performanceChart.data.datasets[0].data = systemLoadData;
            performanceChart.data.datasets[1].data = memoryData;
            performanceChart.update();
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initCharts();
            refreshData();
            
            // Auto-refresh every 30 seconds
            setInterval(refreshData, 30000);
        });
    </script>
</body>
</html>
        """
        
        with open(template_dir / "dashboard.html", 'w') as f:
            f.write(dashboard_html)
        
        self.logger.info("Created dashboard template")
    
    def start_web_dashboard(self, port: int = 5001, debug: bool = False):
        """Start web dashboard server."""
        self.create_dashboard_template()
        
        # Start monitoring in background
        self.start_monitoring(update_interval=30)
        
        self.logger.info(f"Starting web dashboard on port {port}")
        
        # Open browser automatically
        if not debug:
            threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{port}')).start()
        
        try:
            self.app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False, threaded=True)
        except OSError as e:
            if "Address already in use" in str(e):
                self.logger.warning(f"Port {port} is in use, trying port {port + 1}")
                self.app.run(host='0.0.0.0', port=port + 1, debug=debug, use_reloader=False, threaded=True)
            else:
                raise


def main():
    """Main function for testing monitor."""
    # Initialize systems
    batch_system = BatchAutomationSystem()
    queue_manager = IntelligentQueueManager(batch_system)
    monitor = BatchMonitor(batch_system, queue_manager)
    
    # Print initial report
    monitor.print_progress_report()
    
    # Start web dashboard
    print("\nStarting web dashboard...")
    print("Dashboard will be available at: http://localhost:5000")
    monitor.start_web_dashboard()


if __name__ == '__main__':
    main()