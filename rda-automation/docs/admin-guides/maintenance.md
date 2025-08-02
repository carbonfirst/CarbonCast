# Maintenance Guide

This guide covers ongoing maintenance tasks for the RDA Automation System, including updates, backups, performance optimization, and preventive maintenance.

## 🔄 Regular Maintenance Tasks

### Daily Tasks (Automated)

#### System Health Check
```bash
# Add to daily cron job (runs at 6 AM)
0 6 * * * /opt/rda-automation/scripts/health_check.py >> /opt/rda-automation/logs/health_check.log 2>&1
```

#### Log Rotation
```bash
# Logrotate configuration (automatic)
/opt/rda-automation/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 rdauser rdauser
}
```

#### Database Backup
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/opt/rda-automation/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/opt/rda-automation/data/database/automation_state.db"

# Create backup
sqlite3 $DB_PATH ".backup $BACKUP_DIR/automation_state_$DATE.db"

# Compress backup
gzip $BACKUP_DIR/automation_state_$DATE.db

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.db.gz" -mtime +30 -delete

echo "Backup completed: automation_state_$DATE.db.gz"
```

### Weekly Tasks

#### System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y  # Ubuntu
sudo yum update -y                      # CentOS

# Update Python packages
source /opt/rda-automation/venv/bin/activate
pip list --outdated
pip install --upgrade pip
# Review and update specific packages as needed
```

#### Performance Review
```bash
# Weekly performance report
python -c "
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')

print('=== Weekly Performance Report ===')
print(f'Generated: {datetime.now()}')

# Request statistics
cursor = conn.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
        AVG(CASE WHEN completed_at IS NOT NULL 
            THEN (julianday(completed_at) - julianday(created_at)) * 24 * 60 
            ELSE NULL END) as avg_processing_minutes
    FROM rda_requests 
    WHERE created_at > datetime('now', '-7 days')
''')

total, completed, failed, avg_time = cursor.fetchone()
success_rate = (completed / total * 100) if total > 0 else 0

print(f'Total Requests: {total}')
print(f'Completed: {completed}')
print(f'Failed: {failed}')
print(f'Success Rate: {success_rate:.1f}%')
print(f'Avg Processing Time: {avg_time:.1f} minutes')

# Top regions by activity
cursor = conn.execute('''
    SELECT region, COUNT(*) as count
    FROM rda_requests 
    WHERE created_at > datetime('now', '-7 days')
    GROUP BY region 
    ORDER BY count DESC 
    LIMIT 5
''')

print('\nTop Regions:')
for region, count in cursor.fetchall():
    print(f'  {region}: {count} requests')

conn.close()
"
```

#### Disk Cleanup
```bash
# Clean up old files
find /opt/rda-automation/logs -name "*.log.*" -mtime +30 -delete
find /opt/rda-automation/data/downloads -name "*.tmp" -delete
find /opt/rda-automation/backups -name "*.db.gz" -mtime +90 -delete

# Clean up system temp files
sudo find /tmp -name "*rda*" -mtime +7 -delete
```

### Monthly Tasks

#### Security Updates
```bash
# Security audit
sudo apt list --upgradable | grep -i security  # Ubuntu
sudo yum --security check-update               # CentOS

# Update SSL certificates if needed
sudo certbot renew --dry-run

# Review user access and permissions
sudo find /opt/rda-automation -type f -perm /o+w -ls
```

#### Database Maintenance
```bash
# Database optimization
python -c "
import sqlite3

db_path = '/opt/rda-automation/data/database/automation_state.db'
conn = sqlite3.connect(db_path)

print('=== Database Maintenance ===')

# Get database size before
import os
size_before = os.path.getsize(db_path) / (1024 * 1024)
print(f'Database size before: {size_before:.1f} MB')

# Vacuum database
conn.execute('VACUUM')

# Update statistics
conn.execute('ANALYZE')

# Optimize settings
conn.execute('PRAGMA optimize')

conn.close()

# Get size after
size_after = os.path.getsize(db_path) / (1024 * 1024)
print(f'Database size after: {size_after:.1f} MB')
print(f'Space saved: {size_before - size_after:.1f} MB')
"
```

#### Capacity Planning Review
```bash
# Monthly capacity analysis
python -c "
from automation.capacity_manager import create_capacity_manager
import sqlite3
from datetime import datetime, timedelta

print('=== Monthly Capacity Analysis ===')

# Historical capacity usage
conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')

# Request volume trends
for months in [1, 3, 6]:
    cursor = conn.execute('''
        SELECT COUNT(*) 
        FROM rda_requests 
        WHERE created_at > datetime('now', '-{} months')
    '''.format(months))
    count = cursor.fetchone()[0]
    print(f'Requests in last {months} month(s): {count}')

# Storage usage trends
cursor = conn.execute('''
    SELECT 
        SUM(file_size_bytes) / (1024*1024*1024) as total_gb,
        AVG(file_size_bytes) / (1024*1024) as avg_mb
    FROM rda_requests 
    WHERE file_size_bytes IS NOT NULL
    AND created_at > datetime('now', '-1 month')
''')
total_gb, avg_mb = cursor.fetchone()
print(f'Data processed last month: {total_gb:.1f} GB')
print(f'Average file size: {avg_mb:.1f} MB')

# Capacity recommendations
manager = create_capacity_manager()
analytics = manager.get_capacity_analytics()
print(f'Capacity recommendation: {analytics.get(\"recommendation\", \"No recommendation\")}')

conn.close()
"
```

## 🔧 System Updates

### Application Updates

#### Update Process
```bash
# 1. Backup current system
/opt/rda-automation/scripts/backup.sh

# 2. Stop services
sudo systemctl stop rda-automation rda-dashboard

# 3. Update code
cd /opt/rda-automation/app
git fetch origin
git checkout main
git pull origin main

# 4. Update dependencies
source /opt/rda-automation/venv/bin/activate
pip install -r requirements.txt --upgrade

# 5. Run database migrations (if any)
python scripts/migrate_database.py

# 6. Test configuration
python scripts/validate_config.py

# 7. Start services
sudo systemctl start rda-automation rda-dashboard

# 8. Verify operation
python scripts/health_check.py
```

#### Rollback Procedure
```bash
# If update fails, rollback
sudo systemctl stop rda-automation rda-dashboard

# Restore previous version
cd /opt/rda-automation/app
git checkout previous-version-tag

# Restore database backup
cp /opt/rda-automation/backups/automation_state_YYYYMMDD.db \
   /opt/rda-automation/data/database/automation_state.db

# Restart services
sudo systemctl start rda-automation rda-dashboard
```

### Configuration Updates

#### Safe Configuration Changes
```bash
# 1. Backup current configuration
cp /opt/rda-automation/config/production_config.json \
   /opt/rda-automation/config/production_config.json.backup.$(date +%Y%m%d)

# 2. Validate new configuration
python -c "
import json
with open('/opt/rda-automation/config/production_config.json') as f:
    config = json.load(f)
    print('Configuration is valid JSON')
"

# 3. Test configuration
python scripts/test_config.py /opt/rda-automation/config/production_config.json

# 4. Apply configuration (restart services)
sudo systemctl restart rda-automation rda-dashboard

# 5. Monitor for issues
tail -f /opt/rda-automation/logs/*.log
```

## 🗄️ Database Maintenance

### Regular Database Tasks

#### Database Health Check
```bash
# Check database integrity
sqlite3 /opt/rda-automation/data/database/automation_state.db "PRAGMA integrity_check;"

# Check database statistics
python -c "
import sqlite3

conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')

print('=== Database Statistics ===')

# Table sizes
tables = ['rda_requests', 'control_files_tracking', 'regional_progress']
for table in tables:
    cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
    count = cursor.fetchone()[0]
    print(f'{table}: {count} records')

# Database file size
import os
db_size = os.path.getsize('/opt/rda-automation/data/database/automation_state.db')
print(f'Database size: {db_size / (1024*1024):.1f} MB')

# Index usage
cursor = conn.execute('PRAGMA index_list(rda_requests)')
indexes = cursor.fetchall()
print(f'Indexes on rda_requests: {len(indexes)}')

conn.close()
"
```

#### Database Cleanup
```bash
# Clean old records (older than 1 year)
python -c "
import sqlite3

conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')

# Count old records
cursor = conn.execute('''
    SELECT COUNT(*) FROM rda_requests 
    WHERE created_at < datetime('now', '-1 year')
    AND status IN ('completed', 'failed')
''')
old_count = cursor.fetchone()[0]
print(f'Old records to clean: {old_count}')

if old_count > 0:
    # Archive old records (optional)
    cursor = conn.execute('''
        CREATE TABLE IF NOT EXISTS rda_requests_archive AS 
        SELECT * FROM rda_requests WHERE 1=0
    ''')
    
    cursor = conn.execute('''
        INSERT INTO rda_requests_archive 
        SELECT * FROM rda_requests 
        WHERE created_at < datetime('now', '-1 year')
        AND status IN ('completed', 'failed')
    ''')
    
    # Delete old records
    cursor = conn.execute('''
        DELETE FROM rda_requests 
        WHERE created_at < datetime('now', '-1 year')
        AND status IN ('completed', 'failed')
    ''')
    
    deleted = cursor.rowcount
    print(f'Archived and deleted {deleted} old records')
    
    conn.commit()

conn.close()
"
```

### Database Backup and Recovery

#### Automated Backup Script
```bash
cat > /opt/rda-automation/scripts/db_backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/rda-automation/backups/database"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/opt/rda-automation/data/database/automation_state.db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
echo "Starting database backup..."
sqlite3 $DB_PATH ".backup $BACKUP_DIR/automation_state_$DATE.db"

# Verify backup
if sqlite3 $BACKUP_DIR/automation_state_$DATE.db "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "Backup verified successfully"
    
    # Compress backup
    gzip $BACKUP_DIR/automation_state_$DATE.db
    echo "Backup compressed: automation_state_$DATE.db.gz"
    
    # Clean old backups (keep 30 days)
    find $BACKUP_DIR -name "*.db.gz" -mtime +30 -delete
    echo "Old backups cleaned"
else
    echo "Backup verification failed!"
    rm -f $BACKUP_DIR/automation_state_$DATE.db
    exit 1
fi

echo "Database backup completed successfully"
EOF

chmod +x /opt/rda-automation/scripts/db_backup.sh
```

#### Recovery Procedure
```bash
# Stop services
sudo systemctl stop rda-automation rda-dashboard

# Backup current database
cp /opt/rda-automation/data/database/automation_state.db \
   /opt/rda-automation/data/database/automation_state.db.before_recovery

# Restore from backup
gunzip -c /opt/rda-automation/backups/database/automation_state_YYYYMMDD_HHMMSS.db.gz > \
   /opt/rda-automation/data/database/automation_state.db

# Verify restored database
sqlite3 /opt/rda-automation/data/database/automation_state.db "PRAGMA integrity_check;"

# Start services
sudo systemctl start rda-automation rda-dashboard

# Verify system operation
python /opt/rda-automation/scripts/health_check.py
```

## 📊 Performance Optimization

### System Performance Tuning

#### Database Optimization
```bash
# Optimize database settings
python -c "
import sqlite3

conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')

# Enable WAL mode for better concurrency
conn.execute('PRAGMA journal_mode=WAL')

# Optimize performance settings
conn.execute('PRAGMA synchronous=NORMAL')
conn.execute('PRAGMA cache_size=10000')
conn.execute('PRAGMA temp_store=MEMORY')

# Update table statistics
conn.execute('ANALYZE')

print('Database optimized')
conn.close()
"
```

#### System Resource Optimization
```bash
# Optimize system settings for RDA automation
cat > /etc/sysctl.d/99-rda-automation.conf << 'EOF'
# Network optimizations
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 1024

# File system optimizations
fs.file-max = 65536
EOF

# Apply settings
sysctl -p /etc/sysctl.d/99-rda-automation.conf

# Optimize file limits
cat > /etc/security/limits.d/rda-automation.conf << 'EOF'
rdauser soft nofile 65536
rdauser hard nofile 65536
rdauser soft nproc 32768
rdauser hard nproc 32768
EOF
```

### Application Performance Tuning

#### Configuration Optimization
```json
{
  "automation": {
    "max_concurrent_requests": 8,
    "check_interval_seconds": 300,
    "download_timeout_seconds": 7200
  },
  "database": {
    "connection_pool_size": 10,
    "query_timeout": 30
  },
  "logging": {
    "level": "INFO",
    "max_log_size_mb": 100
  }
}
```

#### Memory Usage Optimization
```bash
# Monitor memory usage
python -c "
import psutil
import os

# Get RDA automation processes
for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
    if 'python' in proc.info['name'] and any('automation' in cmd for cmd in proc.cmdline()):
        memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
        print(f'PID {proc.info[\"pid\"]}: {memory_mb:.1f} MB')

# System memory
memory = psutil.virtual_memory()
print(f'System memory: {memory.percent}% used')
"
```

## 🚨 Troubleshooting Maintenance Issues

### Common Maintenance Problems

#### Service Won't Start After Update
```bash
# Check service status
sudo systemctl status rda-automation

# Check logs for errors
sudo journalctl -u rda-automation -n 50

# Check configuration
python scripts/validate_config.py

# Check dependencies
source /opt/rda-automation/venv/bin/activate
pip check
```

#### Database Corruption
```bash
# Check database integrity
sqlite3 /opt/rda-automation/data/database/automation_state.db "PRAGMA integrity_check;"

# If corrupted, restore from backup
sudo systemctl stop rda-automation rda-dashboard
cp /opt/rda-automation/backups/database/latest_good_backup.db.gz /tmp/
gunzip /tmp/latest_good_backup.db.gz
cp /tmp/latest_good_backup.db /opt/rda-automation/data/database/automation_state.db
sudo systemctl start rda-automation rda-dashboard
```

#### High Resource Usage
```bash
# Identify resource-heavy processes
top -p $(pgrep -f "python.*automation")

# Check for memory leaks
python -c "
import psutil
import time

# Monitor memory usage over time
for i in range(10):
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        if 'automation' in ' '.join(proc.cmdline()):
            memory_mb = proc.info['memory_info'].rss / (1024 * 1024)
            print(f'Time {i}: PID {proc.info[\"pid\"]} - {memory_mb:.1f} MB')
    time.sleep(60)
"

# Restart services if needed
sudo systemctl restart rda-automation rda-dashboard
```

## 📋 Maintenance Checklist

### Daily Checklist
- [ ] Check system health status
- [ ] Review error logs
- [ ] Verify backup completion
- [ ] Monitor disk space usage
- [ ] Check service status

### Weekly Checklist
- [ ] Review performance metrics
- [ ] Update system packages
- [ ] Clean temporary files
- [ ] Check SSL certificate expiry
- [ ] Review capacity utilization

### Monthly Checklist
- [ ] Database maintenance and optimization
- [ ] Security updates and audit
- [ ] Capacity planning review
- [ ] Update documentation
- [ ] Test backup and recovery procedures

### Quarterly Checklist
- [ ] Major system updates
- [ ] Performance benchmarking
- [ ] Security assessment
- [ ] Disaster recovery testing
- [ ] Configuration review and optimization

## 📚 Related Documentation

- **[Deployment Guide](deployment.md)** - Initial system setup
- **[Monitoring Guide](monitoring.md)** - System monitoring
- **[Troubleshooting Guide](../Troubleshooting_Guide.md)** - Common issues
- **[Configuration Guide](../Configuration_Reference.md)** - System configuration

---

*Regular maintenance ensures optimal performance and reliability of your RDA Automation System. Follow this guide to keep your system running smoothly.*