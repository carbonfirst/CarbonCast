# Monitoring Guide

This guide covers monitoring the RDA Automation System in production environments, including system health, performance metrics, alerting, and troubleshooting.

## 📊 Monitoring Overview

### What to Monitor

| Component | Key Metrics | Alert Thresholds |
|-----------|-------------|------------------|
| **System Health** | CPU, Memory, Disk | CPU >80%, Memory >90%, Disk >85% |
| **RDA API** | Response time, Error rate | >5s response, >5% errors |
| **Request Processing** | Active requests, Success rate | >9 active, <90% success |
| **File Organization** | Organization rate, Disk usage | <95% organized, >90% disk |
| **Database** | Query time, Lock contention | >1s queries, >10 locks |

## 🖥️ Web Dashboard

### Accessing the Dashboard

```bash
# Start dashboard
python batch_automation_integrated.py --monitor-dashboard

# Or start with custom port
python batch_automation_integrated.py --monitor-dashboard --port 8080
```

Visit `http://localhost:5000` (or your configured port) to access the dashboard.

### Dashboard Sections

#### 1. System Overview
- **Total Requests**: All-time request count
- **Active Requests**: Currently processing
- **Success Rate**: Percentage of successful completions
- **System Uptime**: How long the system has been running

#### 2. Real-time Metrics
- **Request Status Distribution**: Pie chart of request statuses
- **Regional Progress**: Progress by geographic region
- **Processing Timeline**: Request processing over time
- **Error Trends**: Error rates and types

#### 3. Resource Monitoring
- **CPU Usage**: System CPU utilization
- **Memory Usage**: RAM consumption
- **Disk Usage**: Storage utilization
- **Network Activity**: API call frequency

#### 4. Queue Status
- **Pending Requests**: Requests waiting to be processed
- **Priority Distribution**: Queue priority breakdown
- **Processing Rate**: Requests processed per hour
- **Estimated Completion**: Time to complete queue

### Dashboard API Endpoints

#### GET `/api/summary`
System summary information.

```bash
curl http://localhost:5000/api/summary
```

**Response**:
```json
{
  "total_requests": 1250,
  "active_requests": 7,
  "completed_requests": 1180,
  "failed_requests": 63,
  "success_rate": 94.4,
  "regions_active": 15,
  "last_updated": "2025-08-02T00:30:00Z",
  "system_uptime": "2 days, 14:32:15"
}
```

#### GET `/api/current-requests`
List of current requests with status.

```bash
curl "http://localhost:5000/api/current-requests?limit=10"
```

#### POST `/api/trigger-sync`
Manually trigger data synchronization.

```bash
curl -X POST http://localhost:5000/api/trigger-sync
```

## 📈 System Metrics

### Command-Line Monitoring

#### System Status
```bash
# Comprehensive status check
python batch_automation_integrated.py --status

# Continuous monitoring
watch -n 30 'python batch_automation_integrated.py --status'
```

#### Detailed Component Status
```bash
# Capacity status
python -c "
from automation.capacity_manager import create_capacity_manager
manager = create_capacity_manager()
status = manager.get_current_capacity_status()
print(f'Capacity: {status.active_requests}/{status.max_requests} ({status.utilization_percentage:.1f}%)')
print(f'Crisis Level: {status.crisis_level.value}')
"

# Workflow status
python -c "
from automation.workflow_orchestrator import create_workflow_orchestrator
orchestrator = create_workflow_orchestrator()
status = orchestrator.get_workflow_status()
print(f'Workflow State: {status.current_state.value}')
print(f'Active Workflows: {status.active_workflows}')
"
```

### Performance Metrics

#### Request Processing Metrics
```bash
# Processing statistics
python -c "
from automation.comprehensive_tracker import create_comprehensive_tracker
tracker = create_comprehensive_tracker()
stats = tracker.get_tracking_statistics()
print(f'Total Control Files: {stats[\"total_control_files\"]}')
print(f'Completion Rate: {stats[\"completion_percentage\"]:.1f}%')
print(f'Active Regions: {stats[\"active_regions\"]}')
"
```

#### Database Performance
```bash
# Database statistics
python -c "
import sqlite3
import time

db_path = 'src/python/data/automation_state.db'
conn = sqlite3.connect(db_path)

# Query performance test
start_time = time.time()
cursor = conn.execute('SELECT COUNT(*) FROM rda_requests')
count = cursor.fetchone()[0]
query_time = time.time() - start_time

print(f'Total Requests: {count}')
print(f'Query Time: {query_time:.3f}s')

# Database size
import os
db_size = os.path.getsize(db_path) / (1024 * 1024)
print(f'Database Size: {db_size:.1f} MB')

conn.close()
"
```

## 🔍 Log Monitoring

### Log Locations

```bash
# Main application logs
tail -f logs/batch_automation_*.log

# Component-specific logs
tail -f logs/capacity_manager_*.log
tail -f logs/status_monitor_*.log
tail -f logs/workflow_orchestrator_*.log

# Error logs only
grep -i error logs/*.log | tail -20

# Real-time error monitoring
tail -f logs/*.log | grep -i error
```

### Log Analysis

#### Error Rate Analysis
```bash
# Count errors by type in last hour
grep "$(date -d '1 hour ago' '+%Y-%m-%d %H')" logs/*.log | grep -i error | sort | uniq -c

# Most common errors
grep -i error logs/*.log | awk '{print $NF}' | sort | uniq -c | sort -nr | head -10
```

#### Performance Analysis
```bash
# Processing times
grep "Processing completed" logs/*.log | awk '{print $(NF-1)}' | sort -n

# Request throughput per hour
grep "Request.*completed" logs/*.log | awk '{print $1" "$2}' | cut -d: -f1 | uniq -c
```

### Structured Logging

Enable structured logging for better analysis:

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "structured": true
  }
}
```

## 🚨 Alerting

### Basic Alerting Script

```bash
# Create alerting script
cat > /opt/rda-automation/scripts/alert_check.sh << 'EOF'
#!/bin/bash

ALERT_LOG="/opt/rda-automation/logs/alerts.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check system resources
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
DISK_USAGE=$(df /opt/rda-automation | awk 'NR==2 {print $5}' | sed 's/%//')

# Check service status
if ! systemctl is-active --quiet rda-automation; then
    echo "[$DATE] CRITICAL: RDA Automation service is down" >> $ALERT_LOG
    # Send notification (email, webhook, etc.)
fi

# Check resource thresholds
if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
    echo "[$DATE] WARNING: High CPU usage: ${CPU_USAGE}%" >> $ALERT_LOG
fi

if [ $MEM_USAGE -gt 90 ]; then
    echo "[$DATE] WARNING: High memory usage: ${MEM_USAGE}%" >> $ALERT_LOG
fi

if [ $DISK_USAGE -gt 85 ]; then
    echo "[$DATE] WARNING: High disk usage: ${DISK_USAGE}%" >> $ALERT_LOG
fi

# Check RDA API connectivity
if ! curl -s --max-time 10 https://rda.ucar.edu > /dev/null; then
    echo "[$DATE] CRITICAL: RDA API unreachable" >> $ALERT_LOG
fi

# Check request capacity
ACTIVE_REQUESTS=$(python3 -c "
from automation.capacity_manager import create_capacity_manager
manager = create_capacity_manager()
status = manager.get_current_capacity_status()
print(status.active_requests)
" 2>/dev/null)

if [ "$ACTIVE_REQUESTS" -ge 9 ]; then
    echo "[$DATE] WARNING: High request capacity: ${ACTIVE_REQUESTS}/10" >> $ALERT_LOG
fi
EOF

chmod +x /opt/rda-automation/scripts/alert_check.sh
```

### Cron-based Alerting

```bash
# Add to crontab
crontab -e

# Check every 5 minutes
*/5 * * * * /opt/rda-automation/scripts/alert_check.sh

# Daily summary report
0 8 * * * /opt/rda-automation/scripts/daily_report.sh
```

### Email Notifications

```bash
# Install mail utilities
sudo apt install mailutils  # Ubuntu
sudo yum install mailx      # CentOS

# Configure email alerts
cat > /opt/rda-automation/scripts/send_alert.sh << 'EOF'
#!/bin/bash

SUBJECT="$1"
MESSAGE="$2"
RECIPIENTS="admin@company.com,ops@company.com"

echo "$MESSAGE" | mail -s "$SUBJECT" "$RECIPIENTS"
EOF

chmod +x /opt/rda-automation/scripts/send_alert.sh
```

## 📊 Performance Monitoring

### System Resource Monitoring

#### CPU and Memory Monitoring
```bash
# Real-time resource monitoring
htop

# Historical resource usage
sar -u 1 60  # CPU usage for 60 seconds
sar -r 1 60  # Memory usage for 60 seconds

# Process-specific monitoring
ps aux | grep python | grep automation
```

#### Disk I/O Monitoring
```bash
# Disk I/O statistics
iostat -x 1 10

# Monitor specific directory
iotop -d 1 -P -o

# Disk usage by directory
du -sh /opt/rda-automation/*
```

#### Network Monitoring
```bash
# Network connections
netstat -tulpn | grep python

# Network traffic
nethogs

# API call monitoring
tcpdump -i any host rda.ucar.edu
```

### Application Performance

#### Request Processing Performance
```bash
# Processing time analysis
python -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('src/python/data/automation_state.db')

# Average processing time
cursor = conn.execute('''
    SELECT AVG(julianday(completed_at) - julianday(created_at)) * 24 * 60 as avg_minutes
    FROM rda_requests 
    WHERE completed_at IS NOT NULL 
    AND created_at > datetime('now', '-24 hours')
''')
avg_time = cursor.fetchone()[0]
print(f'Average processing time: {avg_time:.1f} minutes')

# Success rate
cursor = conn.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
    FROM rda_requests 
    WHERE created_at > datetime('now', '-24 hours')
''')
total, completed = cursor.fetchone()
success_rate = (completed / total * 100) if total > 0 else 0
print(f'Success rate: {success_rate:.1f}%')

conn.close()
"
```

#### Database Performance Monitoring
```bash
# Database query performance
python -c "
import sqlite3
import time

conn = sqlite3.connect('src/python/data/automation_state.db')

# Test common queries
queries = [
    'SELECT COUNT(*) FROM rda_requests',
    'SELECT * FROM rda_requests WHERE status = \"processing\" LIMIT 10',
    'SELECT region, COUNT(*) FROM rda_requests GROUP BY region'
]

for query in queries:
    start_time = time.time()
    cursor = conn.execute(query)
    results = cursor.fetchall()
    query_time = time.time() - start_time
    print(f'Query: {query[:50]}...')
    print(f'Time: {query_time:.3f}s, Results: {len(results)}')
    print()

conn.close()
"
```

## 🔧 Health Checks

### Automated Health Checks

```bash
# Create comprehensive health check
cat > /opt/rda-automation/scripts/health_check.py << 'EOF'
#!/usr/bin/env python3

import sys
import requests
import sqlite3
import os
import subprocess
from datetime import datetime

def check_service_status():
    """Check if systemd services are running."""
    services = ['rda-automation', 'rda-dashboard']
    results = {}
    
    for service in services:
        try:
            result = subprocess.run(['systemctl', 'is-active', service], 
                                  capture_output=True, text=True)
            results[service] = result.stdout.strip() == 'active'
        except:
            results[service] = False
    
    return results

def check_database():
    """Check database connectivity and integrity."""
    try:
        conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')
        cursor = conn.execute('SELECT COUNT(*) FROM rda_requests')
        count = cursor.fetchone()[0]
        conn.close()
        return {'status': True, 'request_count': count}
    except Exception as e:
        return {'status': False, 'error': str(e)}

def check_api_connectivity():
    """Check RDA API connectivity."""
    try:
        response = requests.get('https://rda.ucar.edu', timeout=10)
        return {'status': response.status_code == 200, 'status_code': response.status_code}
    except Exception as e:
        return {'status': False, 'error': str(e)}

def check_disk_space():
    """Check available disk space."""
    try:
        stat = os.statvfs('/opt/rda-automation')
        free_space_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        total_space_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
        usage_percent = ((total_space_gb - free_space_gb) / total_space_gb) * 100
        
        return {
            'status': usage_percent < 90,
            'free_gb': free_space_gb,
            'usage_percent': usage_percent
        }
    except Exception as e:
        return {'status': False, 'error': str(e)}

def check_dashboard():
    """Check dashboard accessibility."""
    try:
        response = requests.get('http://localhost:5000/api/summary', timeout=5)
        return {'status': response.status_code == 200}
    except Exception as e:
        return {'status': False, 'error': str(e)}

def main():
    print(f"=== RDA Automation Health Check - {datetime.now()} ===")
    
    checks = {
        'Services': check_service_status(),
        'Database': check_database(),
        'RDA API': check_api_connectivity(),
        'Disk Space': check_disk_space(),
        'Dashboard': check_dashboard()
    }
    
    all_healthy = True
    
    for check_name, result in checks.items():
        if isinstance(result, dict) and 'status' in result:
            status = "✓ PASS" if result['status'] else "✗ FAIL"
            print(f"{check_name}: {status}")
            if not result['status']:
                all_healthy = False
                if 'error' in result:
                    print(f"  Error: {result['error']}")
        else:
            print(f"{check_name}: {result}")
    
    print(f"\nOverall Health: {'✓ HEALTHY' if all_healthy else '✗ UNHEALTHY'}")
    return 0 if all_healthy else 1

if __name__ == '__main__':
    sys.exit(main())
EOF

chmod +x /opt/rda-automation/scripts/health_check.py
```

### Load Balancer Health Check

For load balancer integration:

```bash
# Create simple health endpoint
cat > /opt/rda-automation/scripts/lb_health_check.py << 'EOF'
#!/usr/bin/env python3

import sys
import requests

try:
    response = requests.get('http://localhost:5000/api/summary', timeout=2)
    if response.status_code == 200:
        print("OK")
        sys.exit(0)
    else:
        print(f"ERROR: Status {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
EOF

chmod +x /opt/rda-automation/scripts/lb_health_check.py
```

## 📈 Capacity Planning

### Capacity Monitoring

```bash
# Monitor capacity trends
python -c "
from automation.capacity_manager import create_capacity_manager
import time

manager = create_capacity_manager()

# Get capacity analytics
analytics = manager.get_capacity_analytics()
print('=== Capacity Analytics ===')
print(f'Average Utilization: {analytics.get(\"avg_utilization\", 0):.1f}%')
print(f'Peak Utilization: {analytics.get(\"peak_utilization\", 0):.1f}%')
print(f'Crisis Events: {analytics.get(\"crisis_events\", 0)}')
print(f'Recommendation: {analytics.get(\"recommendation\", \"N/A\")}')
"
```

### Growth Planning

```bash
# Analyze growth trends
python -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('src/python/data/automation_state.db')

# Request volume trends
for days in [1, 7, 30]:
    cursor = conn.execute('''
        SELECT COUNT(*) 
        FROM rda_requests 
        WHERE created_at > datetime('now', '-{} days')
    '''.format(days))
    count = cursor.fetchone()[0]
    print(f'Requests in last {days} days: {count}')

# Storage growth
cursor = conn.execute('''
    SELECT SUM(file_size_bytes) / (1024*1024*1024) as total_gb
    FROM rda_requests 
    WHERE file_size_bytes IS NOT NULL
''')
total_gb = cursor.fetchone()[0] or 0
print(f'Total data processed: {total_gb:.1f} GB')

conn.close()
"
```

## 🔗 Integration with External Monitoring

### Prometheus Integration

```python
# Add to your monitoring setup
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Metrics
request_counter = Counter('rda_requests_total', 'Total RDA requests')
processing_time = Histogram('rda_processing_seconds', 'Request processing time')
active_requests = Gauge('rda_active_requests', 'Currently active requests')

# Start metrics server
start_http_server(8000)
```

### Grafana Dashboard

Create Grafana dashboard with panels for:
- Request processing rate
- Success/failure rates
- System resource utilization
- Queue depth over time
- Regional processing distribution

## 📚 Related Documentation

- **[Deployment Guide](deployment.md)** - Production deployment setup
- **[Maintenance Guide](maintenance.md)** - Ongoing operations
- **[Troubleshooting Guide](../Troubleshooting_Guide.md)** - Common issues
- **[Configuration Guide](../Configuration_Reference.md)** - System configuration

---

*Effective monitoring ensures reliable operation of your RDA Automation System. Set up alerts early and monitor trends to prevent issues before they impact operations.*