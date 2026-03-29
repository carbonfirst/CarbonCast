"""
RDA Automation System - Report Generator

This module generates comprehensive reports for the RDA automation system,
including performance metrics, error analysis, and system health status.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
from jinja2 import Environment, FileSystemLoader, Template
import psutil
from logger_utils import get_logger

# Configure logging
logger = get_logger(__name__, level=logging.INFO)

class ReportGenerator:
    """
    Generates comprehensive reports for the RDA automation system.
    """
    
    def __init__(self, config_path: str = "src/python/config"):
        """
        Initialize the report generator.
        
        Args:
            config_path: Path to configuration files
        """
        self.config_path = Path(config_path)
        self.template_path = Path("src/python/templates")
        self.db_path = Path("src/python/data/automation_state.db")
        self.reports_path = Path("data/reports")
        
        # Ensure reports directory exists
        self.reports_path.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.regions_config = self._load_regions_config()
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_path)),
            autoescape=True
        )
        
        logger.info("Report generator initialized")
    
    def _load_regions_config(self) -> Dict[str, Any]:
        """Load regions configuration from YAML file."""
        config_file = self.config_path / "regions_config.yaml"
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Regions config file not found: {config_file}")
            return {"regions": {}, "data_types": {}}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing regions config: {e}")
            return {"regions": {}, "data_types": {}}
    
    def _get_db_connection(self) -> Optional[sqlite3.Connection]:
        """Get database connection."""
        try:
            if self.db_path.exists():
                return sqlite3.connect(str(self.db_path))
            else:
                logger.warning(f"Database file not found: {self.db_path}")
                return None
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get current system health metrics."""
        try:
            return {
                "cpu_usage": round(psutil.cpu_percent(interval=1), 1),
                "memory_usage": round(psutil.virtual_memory().percent, 1),
                "disk_usage": round(psutil.disk_usage('/').percent, 1),
                "active_connections": len(psutil.net_connections()),
                "network_throughput": {
                    "incoming_mbps": 0.0,  # Placeholder
                    "outgoing_mbps": 0.0   # Placeholder
                }
            }
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                "cpu_usage": 0,
                "memory_usage": 0,
                "disk_usage": 0,
                "active_connections": 0
            }
    
    def _get_regional_data(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Get performance data for each region."""
        regional_data = []
        
        for region_code, region_info in self.regions_config.get("regions", {}).items():
            try:
                # Query database for region statistics
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as total_files,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_files,
                           MAX(updated_at) as last_update
                    FROM file_status 
                    WHERE region = ?
                """, (region_code,))
                
                result = cursor.fetchone()
                total_files = result[0] if result[0] else 0
                successful_files = result[1] if result[1] else 0
                last_update = result[2] if result[2] else "Never"
                
                success_rate = (successful_files / total_files * 100) if total_files > 0 else 0
                
                # Determine status
                if success_rate >= 95:
                    status = "active"
                    status_class = "success"
                elif success_rate >= 80:
                    status = "warning"
                    status_class = "warning"
                else:
                    status = "error"
                    status_class = "error"
                
                regional_data.append({
                    "region_code": region_code,
                    "name": region_info.get("name", region_code),
                    "files_processed": total_files,
                    "success_rate": round(success_rate, 1),
                    "last_update": last_update,
                    "status": status,
                    "status_class": status_class,
                    "data_types": region_info.get("data_types", [])
                })
                
            except sqlite3.Error as e:
                logger.error(f"Error querying region data for {region_code}: {e}")
                regional_data.append({
                    "region_code": region_code,
                    "name": region_info.get("name", region_code),
                    "files_processed": 0,
                    "success_rate": 0,
                    "last_update": "Error",
                    "status": "error",
                    "status_class": "error",
                    "data_types": region_info.get("data_types", [])
                })
        
        return regional_data
    
    def _get_data_type_stats(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Get statistics for each data type."""
        data_type_stats = []
        
        for data_type, type_info in self.regions_config.get("data_types", {}).items():
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful
                    FROM file_status 
                    WHERE data_type = ?
                """, (data_type,))
                
                result = cursor.fetchone()
                count = result[0] if result[0] else 0
                successful = result[1] if result[1] else 0
                success_rate = (successful / count * 100) if count > 0 else 0
                
                data_type_stats.append({
                    "type": data_type,
                    "name": type_info.get("name", data_type),
                    "count": count,
                    "description": type_info.get("description", ""),
                    "unit": type_info.get("unit", ""),
                    "success_rate": round(success_rate, 1)
                })
                
            except sqlite3.Error as e:
                logger.error(f"Error querying data type stats for {data_type}: {e}")
                data_type_stats.append({
                    "type": data_type,
                    "name": type_info.get("name", data_type),
                    "count": 0,
                    "description": type_info.get("description", ""),
                    "unit": type_info.get("unit", ""),
                    "success_rate": 0
                })
        
        return data_type_stats
    
    def _get_error_summary(self, conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Get error summary from the database."""
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT error_type, COUNT(*) as count, MAX(created_at) as last_occurrence
                FROM error_log 
                WHERE created_at >= datetime('now', '-24 hours')
                GROUP BY error_type
                ORDER BY count DESC
            """)
            
            error_summary = []
            for row in cursor.fetchall():
                error_type, count, last_occurrence = row
                
                # Determine severity based on error type and count
                if count > 100:
                    severity = "critical"
                    severity_class = "error"
                elif count > 50:
                    severity = "high"
                    severity_class = "error"
                elif count > 10:
                    severity = "medium"
                    severity_class = "warning"
                else:
                    severity = "low"
                    severity_class = "info"
                
                error_summary.append({
                    "type": error_type,
                    "count": count,
                    "last_occurrence": last_occurrence,
                    "severity": severity,
                    "severity_class": severity_class
                })
            
            return error_summary
            
        except sqlite3.Error as e:
            logger.error(f"Error querying error summary: {e}")
            return []
    
    def _get_executive_summary(self, regional_data: List[Dict], conn: sqlite3.Connection) -> Dict[str, Any]:
        """Generate executive summary statistics."""
        total_regions = len(regional_data)
        total_files = sum(region["files_processed"] for region in regional_data)
        
        # Calculate overall success rate
        if total_files > 0:
            total_successful = sum(
                region["files_processed"] * region["success_rate"] / 100 
                for region in regional_data
            )
            success_rate = round(total_successful / total_files * 100, 1)
        else:
            success_rate = 0
        
        # Get system uptime (placeholder)
        try:
            uptime_seconds = psutil.boot_time()
            uptime = datetime.now() - datetime.fromtimestamp(uptime_seconds)
            system_uptime = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
        except:
            system_uptime = "Unknown"
        
        return {
            "total_regions": total_regions,
            "total_files_processed": total_files,
            "success_rate": success_rate,
            "system_uptime": system_uptime,
            "avg_processing_time": 1250,  # Placeholder
            "peak_processing_rate": 450   # Placeholder
        }
    
    def generate_report(self, report_type: str = "daily") -> Dict[str, Any]:
        """
        Generate a comprehensive system report.
        
        Args:
            report_type: Type of report to generate (daily, weekly, monthly)
            
        Returns:
            Dictionary containing report data
        """
        logger.info(f"Generating {report_type} report")
        
        # Get database connection
        conn = self._get_db_connection()
        if not conn:
            logger.error("Cannot generate report without database connection")
            return self._generate_fallback_report()
        
        try:
            # Gather all report data
            regional_data = self._get_regional_data(conn)
            data_type_stats = self._get_data_type_stats(conn)
            error_summary = self._get_error_summary(conn)
            executive_summary = self._get_executive_summary(regional_data, conn)
            system_health = self._get_system_health()
            
            # Create report data structure
            report_data = {
                "report_metadata": {
                    "report_id": f"rda_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "report_date": datetime.now().isoformat(),
                    "report_period": {
                        "start_date": (datetime.now() - timedelta(days=1)).isoformat(),
                        "end_date": datetime.now().isoformat()
                    },
                    "version": "1.0.0",
                    "next_report_time": (datetime.now() + timedelta(days=1)).isoformat()
                },
                "executive_summary": executive_summary,
                "regional_data": regional_data,
                "data_type_stats": data_type_stats,
                "error_summary": error_summary,
                "system_health": system_health
            }
            
            logger.info("Report data generated successfully")
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return self._generate_fallback_report()
        finally:
            conn.close()
    
    def _generate_fallback_report(self) -> Dict[str, Any]:
        """Generate a basic fallback report when database is unavailable."""
        return {
            "report_metadata": {
                "report_id": f"rda_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "report_date": datetime.now().isoformat(),
                "report_period": {
                    "start_date": (datetime.now() - timedelta(days=1)).isoformat(),
                    "end_date": datetime.now().isoformat()
                },
                "version": "1.0.0",
                "next_report_time": (datetime.now() + timedelta(days=1)).isoformat()
            },
            "executive_summary": {
                "total_regions": len(self.regions_config.get("regions", {})),
                "total_files_processed": 0,
                "success_rate": 0,
                "system_uptime": "Unknown",
                "avg_processing_time": 0,
                "peak_processing_rate": 0
            },
            "regional_data": [],
            "data_type_stats": [],
            "error_summary": [],
            "system_health": self._get_system_health()
        }
    
    def generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate HTML report from report data.
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            HTML report string
        """
        try:
            template = self.jinja_env.get_template("report_template.html")
            
            # Prepare template variables
            template_vars = {
                "report_date": datetime.fromisoformat(
                    report_data["report_metadata"]["report_date"].replace('Z', '+00:00')
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "report_period": "Last 24 hours",
                "version": report_data["report_metadata"]["version"],
                "next_report_time": datetime.fromisoformat(
                    report_data["report_metadata"]["next_report_time"].replace('Z', '+00:00')
                ).strftime("%Y-%m-%d %H:%M:%S"),
                **report_data["executive_summary"],
                **report_data["system_health"],
                "regional_data": report_data["regional_data"],
                "data_type_stats": report_data["data_type_stats"],
                "error_summary": report_data["error_summary"]
            }
            
            html_content = template.render(**template_vars)
            logger.info("HTML report generated successfully")
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return f"<html><body><h1>Error generating report: {e}</h1></body></html>"
    
    def save_report(self, report_data: Dict[str, Any], format_type: str = "both") -> Dict[str, str]:
        """
        Save report to file(s).
        
        Args:
            report_data: Report data dictionary
            format_type: Format to save ("json", "html", "both")
            
        Returns:
            Dictionary with file paths of saved reports
        """
        report_id = report_data["report_metadata"]["report_id"]
        saved_files = {}
        
        try:
            if format_type in ["json", "both"]:
                json_path = self.reports_path / f"{report_id}.json"
                with open(json_path, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
                saved_files["json"] = str(json_path)
                logger.info(f"JSON report saved: {json_path}")
            
            if format_type in ["html", "both"]:
                html_content = self.generate_html_report(report_data)
                html_path = self.reports_path / f"{report_id}.html"
                with open(html_path, 'w') as f:
                    f.write(html_content)
                saved_files["html"] = str(html_path)
                logger.info(f"HTML report saved: {html_path}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return {}
    
    def generate_and_save_report(self, report_type: str = "daily", format_type: str = "both") -> Dict[str, str]:
        """
        Generate and save a complete report.
        
        Args:
            report_type: Type of report to generate
            format_type: Format to save ("json", "html", "both")
            
        Returns:
            Dictionary with file paths of saved reports
        """
        logger.info(f"Generating and saving {report_type} report")
        
        # Generate report data
        report_data = self.generate_report(report_type)
        
        # Save report
        saved_files = self.save_report(report_data, format_type)
        
        logger.info(f"Report generation complete. Files saved: {list(saved_files.values())}")
        return saved_files


def main():
    """Main function for standalone execution."""
    generator = ReportGenerator()
    
    # Generate and save daily report
    saved_files = generator.generate_and_save_report("daily", "both")
    
    print("Report generation complete!")
    for format_type, file_path in saved_files.items():
        print(f"{format_type.upper()} report: {file_path}")


if __name__ == "__main__":
    main()