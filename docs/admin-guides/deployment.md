# Deployment Guide

This guide covers deploying the RDA Automation System in production environments. It includes system requirements, installation procedures, security considerations, and operational best practices.

## 🎯 Deployment Overview

### Deployment Types

| Type | Use Case | Complexity | Scalability |
|------|----------|------------|-------------|
| **Single Server** | Small research groups, testing | Low | Limited |
| **Multi-Service** | Production environments | Medium | Good |
| **Containerized** | Cloud deployments, scaling | High | Excellent |
| **High Availability** | Critical operations | High | Excellent |

## 📋 System Requirements

### Minimum Requirements

- **OS**: Linux (Ubuntu 18.04+, CentOS 7+, RHEL 7+), macOS 10.14+, Windows 10
- **Python**: 3.7 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 50GB minimum, 500GB+ recommended for large datasets
- **Network**: Stable internet connection, 10 Mbps+ recommended

### Recommended Production Requirements

- **OS**: Linux (Ubuntu 20.04 LTS or CentOS 8)
- **CPU**: 4+ cores, 2.5GHz+
- **RAM**: 16GB+ for large-scale processing
- **Storage**: 1TB+ SSD for downloads, separate disk for logs
- **Network**: Dedicated connection, 100 Mbps+
- **Monitoring**: System monitoring tools (Prometheus, Grafana)

### Storage Planning

```bash
# Estimate storage needs
# Average request: 1-5GB
# Large request: 10-50GB
# Control files: ~1KB each
# Logs: 10-100MB per day
# Database: 10-100MB

# Example calculation for 1000 requests:
# Data: 1000 × 3GB = 3TB
# Logs: 365 × 50MB = 18GB
# Total: ~3.1TB recommended
```

## 🚀 Production Installation

### Step 1: System Preparation

#### Create Dedicated User
```bash
# Create RDA automation user
sudo useradd -m -s /bin/bash rdauser
sudo usermod -aG sudo rdauser

# Switch to RDA user
sudo su - rdauser
```

#### Setup Directory Structure
```bash
# Create application directories
mkdir -p /opt/rda-automation/{app,data,logs,config,backups}
mkdir -p /opt/rda-automation/data/{downloads,reports,database}

# Set permissions
sudo chown -R rdauser:rdauser /opt/rda-automation
chmod -R 755 /opt/rda-automation
```

#### Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl wget

# CentOS/RHEL
sudo yum update
sudo yum install -y python3 python3-pip git curl wget

# Install additional tools
sudo apt install -y htop iotop nethogs sqlite3  # Ubuntu
sudo yum install -y htop iotop sqlite3          # CentOS
```

### Step 2: Application Installation

#### Clone and Setup Application
```bash
cd /opt/rda-automation/app
git clone <repository-url> .

# Create production virtual environment
python3 -m venv /opt/rda-automation/venv
source /opt/rda-automation/venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Production Configuration
```bash
# Copy configuration template
cp config/automation_config.json /opt/rda-automation/config/production_config.json

# Edit production configuration
nano /opt/rda-automation/config/production_config.json
```

**Production Configuration Example:**
```json
{
  "automation": {
    "max_concurrent_requests": 8,
    "check_interval_seconds": 300,
    "retry_attempts": 3,
    "request_limit_safety_margin": 2,
    "download_timeout_seconds": 7200
  },
  "directories": {
    "base_download_dir": "/opt/rda-automation/data/downloads",
    "logs_dir": "/opt/rda-automation/logs",
    "control_files_dir": "/opt/rda-automation/config/control_files"
  },
  "dashboard": {
    "port": 5000,
    "auto_refresh_seconds": 30
  },
  "logging": {
    "level": "INFO",
    "max_log_size_mb": 50,
    "backup_count": 10
  },
  "safety": {
    "require_confirmation": false,
    "dry_run_mode": false,
    "max_files_per_download": 5000
  }
}
```

#### Setup Authentication
```bash
# Create secure token file
echo "your_production_rda_token" > /opt/rda-automation/config/rdams_token.txt
chmod 600 /opt/rda-automation/config/rdams_token.txt

# Create symbolic link for application
ln -s /opt/rda-automation/config/rdams_token.txt /opt/rda-automation/app/rdams_token.txt
```

### Step 3: Service Configuration

#### Create Systemd Services

**Main Automation Service** (`/etc/systemd/system/rda-automation.service`):
```ini
[Unit]
Description=RDA Automation System
After=network.target
Wants=network.target

[Service]
Type=simple
User=rdauser
Group=rdauser
WorkingDirectory=/opt/rda-automation/app/src/python
Environment=PATH=/opt/rda-automation/venv/bin
ExecStart=/opt/rda-automation/venv/bin/python batch_automation_integrated.py --process-all-control-files --config /opt/rda-automation/config/production_config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Dashboard Service** (`/etc/systemd/system/rda-dashboard.service`):
```ini
[Unit]
Description=RDA Automation Dashboard
After=network.target
Wants=network.target

[Service]
Type=simple
User=rdauser
Group=rdauser
WorkingDirectory=/opt/rda-automation/app/src/python
Environment=PATH=/opt/rda-automation/venv/bin
ExecStart=/opt/rda-automation/venv/bin/python -c "from automation.dashboard import create_dashboard; create_dashboard('/opt/rda-automation/config/production_config.json').start_dashboard()"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable rda-automation
sudo systemctl enable rda-dashboard

# Start services
sudo systemctl start rda-automation
sudo systemctl start rda-dashboard

# Check status
sudo systemctl status rda-automation
sudo systemctl status rda-dashboard
```

## 🔒 Security Configuration

### Firewall Setup

```bash
# Ubuntu (UFW)
sudo ufw allow ssh
sudo ufw allow 5000/tcp  # Dashboard port
sudo ufw enable

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

### SSL/TLS Configuration

#### Using Nginx Reverse Proxy
```bash
# Install Nginx
sudo apt install nginx  # Ubuntu
sudo yum install nginx  # CentOS

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/rda-automation
```

**Nginx Configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/rda-automation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### File Permissions

```bash
# Set secure permissions
sudo chown -R rdauser:rdauser /opt/rda-automation
chmod -R 755 /opt/rda-automation
chmod 600 /opt/rda-automation/config/rdams_token.txt
chmod 644 /opt/rda-automation/config/production_config.json

# Secure log directory
chmod 755 /opt/rda-automation/logs
```

## 📊 Monitoring Setup

### Log Management

#### Logrotate Configuration
```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/rda-automation
```

```
/opt/rda-automation/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 rdauser rdauser
    postrotate
        systemctl reload rda-automation
        systemctl reload rda-dashboard
    endscript
}
```

#### Centralized Logging (Optional)
```bash
# Install rsyslog configuration for centralized logging
sudo nano /etc/rsyslog.d/50-rda-automation.conf
```

```
# RDA Automation logs
$template RDAFormat,"%timegenerated% %HOSTNAME% %syslogtag% %msg%\n"
if $programname == 'rda-automation' then /var/log/rda-automation.log;RDAFormat
& stop
```

### System Monitoring

#### Basic Monitoring Script
```bash
# Create monitoring script
cat > /opt/rda-automation/scripts/monitor.sh << 'EOF'
#!/bin/bash

# RDA Automation System Monitor
LOG_FILE="/opt/rda-automation/logs/monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting system check" >> $LOG_FILE

# Check services
for service in rda-automation rda-dashboard; do
    if systemctl is-active --quiet $service; then
        echo "[$DATE] $service: OK" >> $LOG_FILE
    else
        echo "[$DATE] $service: FAILED" >> $LOG_FILE
        # Restart failed service
        systemctl restart $service
    fi
done

# Check disk space
DISK_USAGE=$(df /opt/rda-automation | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 90 ]; then
    echo "[$DATE] WARNING: Disk usage at ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEM_USAGE -gt 90 ]; then
    echo "[$DATE] WARNING: Memory usage at ${MEM_USAGE}%" >> $LOG_FILE
fi

# Check RDA API connectivity
if curl -s --max-time 10 https://rda.ucar.edu > /dev/null; then
    echo "[$DATE] RDA API: OK" >> $LOG_FILE
else
    echo "[$DATE] RDA API: FAILED" >> $LOG_FILE
fi

echo "[$DATE] System check completed" >> $LOG_FILE
EOF

chmod +x /opt/rda-automation/scripts/monitor.sh
```

#### Cron Job for Monitoring
```bash
# Add monitoring cron job
crontab -e

# Add this line to run every 5 minutes
*/5 * * * * /opt/rda-automation/scripts/monitor.sh
```

### Health Check Endpoint

Create a health check script for load balancers:

```bash
cat > /opt/rda-automation/scripts/health_check.py << 'EOF'
#!/usr/bin/env python3
import sys
import requests
import sqlite3
import os

def check_dashboard():
    try:
        response = requests.get('http://localhost:5000/api/summary', timeout=5)
        return response.status_code == 200
    except:
        return False

def check_database():
    try:
        conn = sqlite3.connect('/opt/rda-automation/data/database/automation_state.db')
        conn.execute('SELECT 1')
        conn.close()
        return True
    except:
        return False

def check_disk_space():
    stat = os.statvfs('/opt/rda-automation')
    free_space = stat.f_bavail * stat.f_frsize
    return free_space > 1024 * 1024 * 1024  # 1GB minimum

if __name__ == '__main__':
    checks = [
        ('Dashboard', check_dashboard()),
        ('Database', check_database()),
        ('Disk Space', check_disk_space())
    ]
    
    all_ok = all(result for _, result in checks)
    
    for name, result in checks:
        status = 'OK' if result else 'FAIL'
        print(f'{name}: {status}')
    
    sys.exit(0 if all_ok else 1)
EOF

chmod +x /opt/rda-automation/scripts/health_check.py
```

## 🔄 Backup and Recovery

### Database Backup

```bash
# Create backup script
cat > /opt/rda-automation/scripts/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/rda-automation/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/opt/rda-automation/data/database/automation_state.db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
if [ -f "$DB_PATH" ]; then
    sqlite3 $DB_PATH ".backup $BACKUP_DIR/automation_state_$DATE.db"
    echo "Database backup created: automation_state_$DATE.db"
fi

# Backup configuration
tar -czf $BACKUP_DIR/config_$DATE.tar.gz -C /opt/rda-automation config/

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "config_*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
EOF

chmod +x /opt/rda-automation/scripts/backup.sh
```

#### Automated Backups
```bash
# Add backup cron job
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/rda-automation/scripts/backup.sh >> /opt/rda-automation/logs/backup.log 2>&1
```

### Recovery Procedures

#### Database Recovery
```bash
# Stop services
sudo systemctl stop rda-automation rda-dashboard

# Restore database from backup
cp /opt/rda-automation/backups/automation_state_YYYYMMDD_HHMMSS.db \
   /opt/rda-automation/data/database/automation_state.db

# Restore configuration
cd /opt/rda-automation
tar -xzf backups/config_YYYYMMDD_HHMMSS.tar.gz

# Start services
sudo systemctl start rda-automation rda-dashboard
```

## 🔧 Performance Tuning

### System Optimization

#### Kernel Parameters
```bash
# Add to /etc/sysctl.conf
echo "net.core.somaxconn = 1024" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 1024" >> /etc/sysctl.conf
sysctl -p
```

#### File Limits
```bash
# Add to /etc/security/limits.conf
echo "rdauser soft nofile 65536" >> /etc/security/limits.conf
echo "rdauser hard nofile 65536" >> /etc/security/limits.conf
```

### Application Tuning

#### High-Performance Configuration
```json
{
  "automation": {
    "max_concurrent_requests": 10,
    "check_interval_seconds": 600,
    "download_timeout_seconds": 10800,
    "request_limit_safety_margin": 1
  },
  "logging": {
    "level": "WARNING",
    "max_log_size_mb": 100
  }
}
```

#### Database Optimization
```bash
# SQLite optimization
cat > /opt/rda-automation/scripts/optimize_db.py << 'EOF'
#!/usr/bin/env python3
import sqlite3

db_path = '/opt/rda-automation/data/database/automation_state.db'
conn = sqlite3.connect(db_path)

# Enable WAL mode for better concurrency
conn.execute('PRAGMA journal_mode=WAL')

# Optimize performance
conn.execute('PRAGMA synchronous=NORMAL')
conn.execute('PRAGMA cache_size=10000')
conn.execute('PRAGMA temp_store=MEMORY')

# Vacuum database
conn.execute('VACUUM')

conn.close()
print("Database optimized")
EOF

chmod +x /opt/rda-automation/scripts/optimize_db.py
```

## 🐳 Container Deployment

### Docker Setup

#### Dockerfile
```dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd -m -s /bin/bash rdauser

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/downloads /app/logs /app/config

# Set ownership
RUN chown -R rdauser:rdauser /app

# Switch to application user
USER rdauser

# Expose dashboard port
EXPOSE 5000

# Default command
CMD ["python", "src/python/batch_automation_integrated.py", "--process-all-control-files"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  rda-automation:
    build: .
    container_name: rda-automation
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - RDA_TOKEN_FILE=/app/config/rdams_token.txt
    ports:
      - "5000:5000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/summary"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    container_name: rda-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - rda-automation
```

## 📈 Scaling Considerations

### Horizontal Scaling

For large-scale deployments:

1. **Load Balancer**: Use Nginx or HAProxy to distribute requests
2. **Multiple Workers**: Run multiple automation instances with different control file sets
3. **Shared Storage**: Use NFS or similar for shared file storage
4. **Database Clustering**: Consider PostgreSQL for multi-instance deployments

### Vertical Scaling

- **CPU**: More cores help with concurrent processing
- **RAM**: More memory for larger batches and caching
- **Storage**: Fast SSD storage for downloads and database
- **Network**: Higher bandwidth for faster downloads

## 🚨 Troubleshooting Deployment

### Common Issues

#### Service Won't Start
```bash
# Check service logs
sudo journalctl -u rda-automation -f

# Check configuration
python3 -c "import json; json.load(open('/opt/rda-automation/config/production_config.json'))"

# Check permissions
ls -la /opt/rda-automation/config/rdams_token.txt
```

#### Performance Issues
```bash
# Monitor system resources
htop
iotop
nethogs

# Check application logs
tail -f /opt/rda-automation/logs/*.log

# Monitor database
sqlite3 /opt/rda-automation/data/database/automation_state.db "SELECT COUNT(*) FROM rda_requests;"
```

#### Network Issues
```bash
# Test RDA connectivity
curl -I https://rda.ucar.edu

# Check firewall
sudo ufw status
sudo iptables -L
```

## 📚 Related Documentation

- **[Configuration Guide](../Configuration_Reference.md)** - Detailed configuration options
- **[Monitoring Guide](monitoring.md)** - System monitoring and alerting
- **[Maintenance Guide](maintenance.md)** - Ongoing operations
- **[Troubleshooting](../Troubleshooting_Guide.md)** - Common issues and solutions

---

*Need help with deployment? Check our [Troubleshooting Guide](../Troubleshooting_Guide.md) or open an issue on GitHub.*