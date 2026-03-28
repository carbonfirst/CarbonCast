#!/usr/bin/env python3
"""
RDA Automation System - User-Friendly Startup Script.

This script provides a simple, user-friendly entry point for the RDA automation system
with automatic dashboard integration, comprehensive error handling, and clear user feedback.

The startup script serves as the main interface for users to interact with the RDA
automation system, offering multiple operational modes and guided setup assistance.

Key Features:
    - Interactive menu-driven interface for ease of use
    - Automatic dashboard startup with browser integration
    - Prerequisites checking and setup guidance
    - Clear progress feedback and status reporting
    - Error handling and recovery guidance
    - Multiple startup modes for different use cases
    - Graceful shutdown handling

Classes:
    RDAAutomationStarter: Main startup controller class

Functions:
    main: Entry point function with argument parsing

Usage Examples:
    Interactive mode (recommended for new users):
        python start_automation.py
    
    Direct command modes:
        python start_automation.py --start            # Start full automation
        python start_automation.py --dashboard        # Dashboard only
        python start_automation.py --resume           # Resume processing
        python start_automation.py --status           # Show status

Prerequisites:
    - Control files in 'control_files/' directory
    - RDA authentication token in 'rdams_token.txt'
    - Required Python dependencies installed
"""

import os
import sys
import time
import logging
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logger_utils import get_logger

try:
    from batch_automation_integrated import IntegratedBatchSystem
    from automation.dashboard import create_dashboard
    from automation.date_manager import DateManager, DateValidationError, create_date_manager
    from directory_utils import setup_directories
    from setup_database import UnifiedDatabaseSetup
    from check_database import DatabaseHealthChecker
    from bulletproof_database_init import create_bulletproof_initializer
except ImportError as e:
    print(f"❌ Error importing required modules: {e}")
    print("Please ensure you're running from the correct directory and all dependencies are installed.")
    sys.exit(1)


class RDAAutomationStarter:
    """
    User-friendly starter for the RDA Automation System.
    
    This class provides a comprehensive interface for starting and managing
    the RDA automation system with user-friendly features including interactive
    menus, prerequisites checking, and multiple operational modes.
    
    The starter handles system initialization, prerequisites validation,
    and provides clear feedback to users throughout the startup process.
    
    Attributes:
        logger (logging.Logger): Logger instance for startup operations
        system (Optional[IntegratedBatchSystem]): The automation system instance
    
    Methods:
        print_welcome_banner: Display welcome information
        check_prerequisites: Validate system prerequisites
        show_interactive_menu: Display interactive menu options
        start_full_automation: Start complete automation with dashboard
        start_dashboard_only: Start dashboard in monitoring mode
        resume_processing: Resume interrupted processing
        show_status: Display current system status
        run_interactive: Run in interactive menu mode
        run_with_args: Run with command line arguments
    """
    
    def __init__(self):
        """
        Initialize the automation starter.
        
        Sets up logging and initializes the starter state for operation.
        """
        self.logger = self._setup_logging()
        self.system = None
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation_starter', level=logging.INFO)
    
    def print_welcome_banner(self):
        """
        Print welcome banner with system information.
        
        Displays an attractive welcome banner with system features and
        capabilities to orient users to the RDA automation system.
        """
        print("\n" + "="*90)
        print("🌦️  RDA AUTOMATION SYSTEM - ENHANCED DASHBOARD INTEGRATION")
        print("="*90)
        print("📊 Automated weather data processing with real-time monitoring")
        print("🌐 Enhanced web dashboard with regional and variable insights")
        print("⚡ Intelligent queuing and error recovery system")
        print("="*90)
        print()
    
    def check_prerequisites(self) -> bool:
        """
        Check system prerequisites and provide guidance.
        
        Validates that all required components are available for the
        automation system to operate properly, including directories,
        configuration files, authentication tokens, and database setup.
        
        The method checks for:
            - Control files directory and contents
            - RDA authentication token file
            - Required data and logs directories
            - Database setup and health
        
        Returns:
            bool: True if all prerequisites are satisfied, False otherwise.
                When False, detailed guidance is provided to resolve issues.
        
        Note:
            This method will attempt to create missing directories and
            set up the database automatically.
        """
        print("🔍 Checking system prerequisites...")
        
        # First, ensure all required directories exist
        print("   🔧 Setting up required directories...")
        try:
            setup_success = setup_directories(logger=self.logger)
            if setup_success:
                print("   ✅ All required directories are ready")
            else:
                print("   ⚠️  Some directory setup issues occurred (check logs)")
        except Exception as e:
            print(f"   ⚠️  Directory setup error: {e}")
            self.logger.warning(f"Directory setup error: {e}")
        
        issues = []
        
        # Check for control files directory
        control_files_dir = Path("control_files")
        if not control_files_dir.exists():
            issues.append("❌ Control files directory not found")
            print(f"   Missing: {control_files_dir.absolute()}")
        else:
            control_files = list(control_files_dir.glob("*.ctl"))
            if not control_files:
                issues.append("❌ No control files found in control_files directory")
            else:
                print(f"   ✅ Found {len(control_files)} control files")
        
        # Check for RDA token
        token_file = Path("rdams_token.txt")
        if not token_file.exists():
            issues.append("❌ RDA token file not found (rdams_token.txt)")
        else:
            print("   ✅ RDA token file found")
        
        # Check for data directory
        data_dir = Path("data")
        if not data_dir.exists():
            print("   ⚠️  Data directory not found, will be created automatically")
            data_dir.mkdir(exist_ok=True)
        else:
            print("   ✅ Data directory exists")
        
        # Check for logs directory
        logs_dir = Path("logs")
        if not logs_dir.exists():
            print("   ⚠️  Logs directory not found, will be created automatically")
            logs_dir.mkdir(exist_ok=True)
        else:
            print("   ✅ Logs directory exists")
        
        # Database setup and health check
        print("   🗄️  Checking database setup...")
        if not self._setup_and_check_database():
            issues.append("❌ Database setup or health check failed")
        
        if issues:
            print("\n❌ Prerequisites check failed:")
            for issue in issues:
                print(f"   {issue}")
            print("\n📋 To fix these issues:")
            print("   1. Ensure control files are in the 'control_files/' directory")
            print("   2. Create 'rdams_token.txt' with your RDA authentication token")
            print("   3. Check database setup logs for specific issues")
            print("   4. Run this script again")
            return False
        
        print("✅ All prerequisites satisfied!")
        return True
    
    def _setup_and_check_database(self) -> bool:
        """
        Set up and check database health using bulletproof initialization.
        
        This method uses the bulletproof database initializer to ensure absolute
        reliability and prevent any database-related startup failures.
        
        Returns:
            bool: True if database setup and health check passed, False otherwise.
        """
        try:
            print("      🛡️  Initializing bulletproof database system...")
            
            # Create bulletproof initializer
            bulletproof_initializer = create_bulletproof_initializer(
                enable_enhanced_schema=True
            )
            
            # Run bulletproof initialization
            print("      🔧 Running comprehensive database initialization...")
            initialization_report = bulletproof_initializer.initialize_bulletproof_database()
            
            # Check initialization results
            if initialization_report.status == "success":
                print("      ✅ Bulletproof database initialization completed successfully")
                
                # Show summary
                validation_summary = {}
                for result in initialization_report.validation_results:
                    validation_summary[result.status] = validation_summary.get(result.status, 0) + 1
                
                print(f"      📊 Validation Summary:")
                for status, count in validation_summary.items():
                    icon = {"pass": "✅", "fail": "❌", "warning": "⚠️", "critical": "🚨", "info": "ℹ️"}.get(status, "❓")
                    print(f"        {icon} {status.title()}: {count}")
                
                # Show operations performed
                if initialization_report.operations_performed:
                    print(f"      🔧 Operations: {len(initialization_report.operations_performed)} completed")
                
                # Show recovery actions if any
                if initialization_report.recovery_actions:
                    print(f"      🔄 Recovery Actions: {len(initialization_report.recovery_actions)} applied")
                    for action in initialization_report.recovery_actions:
                        print(f"        - {action}")
                
                # Show final health status
                if initialization_report.final_health_check:
                    health_status = initialization_report.final_health_check.get('overall_status', 'unknown')
                    print(f"      🏥 Final Health Status: {health_status.upper()}")
                
                print(f"      📁 Database location: {initialization_report.database_path}")
                print("      ✅ Database is bulletproof and ready for production use")
                
                return True
                
            else:
                print("      ❌ CRITICAL: Bulletproof database initialization failed")
                print("      💡 This is a fatal error that prevents system startup")
                
                # Log detailed error information
                self.logger.error("FATAL: Bulletproof database initialization failed")
                self.logger.error(f"Initialization ID: {initialization_report.initialization_id}")
                
                # Show errors encountered
                if initialization_report.errors_encountered:
                    print("      📋 Critical errors encountered:")
                    for error in initialization_report.errors_encountered:
                        print(f"        - {error}")
                        self.logger.error(f"  Database Error: {error}")
                
                # Show validation failures
                critical_failures = [r for r in initialization_report.validation_results if r.status == "critical"]
                failures = [r for r in initialization_report.validation_results if r.status == "fail"]
                
                if critical_failures or failures:
                    print("      📋 Validation failures:")
                    for failure in critical_failures + failures:
                        print(f"        - {failure.check_name}: {failure.message}")
                        self.logger.error(f"  Validation Failure: {failure.check_name} - {failure.message}")
                
                # Show recommendations
                if initialization_report.recommendations:
                    print("      💡 Recommendations to fix issues:")
                    for i, rec in enumerate(initialization_report.recommendations[:5], 1):  # Show top 5
                        print(f"        {i}. {rec}")
                
                # Log full report for debugging
                self.logger.error("Full initialization report logged for debugging")
                bulletproof_initializer.print_initialization_report(initialization_report)
                
                return False
                
        except Exception as e:
            print(f"      ❌ CRITICAL: Bulletproof database initialization error - {e}")
            print("      💡 This is a fatal error that prevents system startup")
            self.logger.error(f"FATAL: Bulletproof database initialization error: {e}")
            self.logger.error("System cannot start due to database initialization failure")
            return False
    
    def _verify_critical_tables(self, db_setup: 'UnifiedDatabaseSetup') -> bool:
        """
        Verify that all critical database tables exist.
        
        Args:
            db_setup: The database setup instance
            
        Returns:
            bool: True if all critical tables exist, False otherwise
        """
        try:
            db_info = db_setup.get_database_info()
            tables = db_info.get('tables', {})
            
            # Critical tables that must exist
            critical_tables = [
                'rda_requests',
                'control_files_tracking'
            ]
            
            missing_tables = []
            for table in critical_tables:
                if table not in tables:
                    missing_tables.append(table)
            
            if missing_tables:
                self.logger.error(f"Critical tables missing: {missing_tables}")
                print(f"        ❌ Missing critical tables: {', '.join(missing_tables)}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying critical tables: {e}")
            return False
    
    def _verify_data_sync_requirements(self, db_setup: 'UnifiedDatabaseSetup') -> bool:
        """
        Verify that the database meets data sync requirements.
        
        This specifically checks for the tables and columns that data_sync.py needs.
        
        Args:
            db_setup: The database setup instance
            
        Returns:
            bool: True if data sync requirements are met, False otherwise
        """
        try:
            with db_setup._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check rda_requests table has required columns
                cursor.execute("PRAGMA table_info(rda_requests)")
                rda_columns = {row['name'] for row in cursor.fetchall()}
                
                required_rda_columns = {
                    'request_index', 'request_id', 'control_file_path', 'region',
                    'variable_type', 'dsid', 'status', 'date_rqst', 'date_ready',
                    'date_purge', 'location', 'ncar_contact', 'rinfo', 'subset_note',
                    'raw_response'
                }
                
                missing_rda_columns = required_rda_columns - rda_columns
                if missing_rda_columns:
                    self.logger.error(f"rda_requests table missing columns: {missing_rda_columns}")
                    print(f"        ❌ rda_requests missing columns: {', '.join(missing_rda_columns)}")
                    return False
                
                # Check control_files_tracking table has required columns
                cursor.execute("PRAGMA table_info(control_files_tracking)")
                control_columns = {row['name'] for row in cursor.fetchall()}
                
                required_control_columns = {
                    'file_path', 'filename', 'region', 'variable_type', 'discovered_at',
                    'request_index', 'request_id'
                }
                
                missing_control_columns = required_control_columns - control_columns
                if missing_control_columns:
                    self.logger.error(f"control_files_tracking table missing columns: {missing_control_columns}")
                    print(f"        ❌ control_files_tracking missing columns: {', '.join(missing_control_columns)}")
                    return False
                
                print("      ✅ Data sync requirements verified")
                return True
                
        except Exception as e:
            self.logger.error(f"Error verifying data sync requirements: {e}")
            print(f"        ❌ Error checking data sync requirements: {e}")
            return False
    
    def show_interactive_menu(self):
        """
        Show interactive menu for user selection.
        
        Displays a user-friendly menu with available options and handles
        user input validation with clear error messages.
        
        Returns:
            str: User's menu choice ('1'-'5') representing the selected option.
        
        Note:
            This method loops until a valid choice is made or the user
            interrupts with Ctrl+C.
        """
        print("\n📋 Select an option:")
        print("   1. 🚀 Start full automation with dashboard")
        print("   2. 📊 Dashboard only (monitor existing processing)")
        print("   3. ⏯️  Resume interrupted processing")
        print("   4. 📈 Show current status")
        print("   5. ❌ Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-5): ").strip()
                if choice in ['1', '2', '3', '4', '5']:
                    return choice
                else:
                    print("❌ Invalid choice. Please enter 1, 2, 3, 4, or 5.")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    def _get_control_files(self) -> List[str]:
        """Get list of control files."""
        control_files_dir = Path("control_files")
        if not control_files_dir.exists():
            return []
        
        return [str(f) for f in control_files_dir.glob("*.ctl")]
    
    def _get_current_date_range(self) -> str:
        """Get current date range from control files."""
        try:
            date_manager = create_date_manager()
            control_files = self._get_control_files()
            
            if not control_files:
                return "No control files found"
            
            # Check first control file for current date
            current_date = date_manager.extract_date_from_ctl(control_files[0])
            if current_date:
                # Try to parse and format nicely
                try:
                    date_range = date_manager.parse_date_range_string(current_date)
                    return date_range.to_readable_format()
                except:
                    return current_date
            else:
                return "No date found in control files"
                
        except Exception as e:
            self.logger.warning(f"Error getting current date range: {e}")
            return "Unable to determine current date range"
    
    def _should_prompt_for_dates(self) -> bool:
        """Check if we should prompt for date selection."""
        # Always prompt for date selection in automation modes
        # This can be made configurable later
        return True
    
    def _prompt_yes_no(self, message: str) -> bool:
        """Prompt user for yes/no response."""
        while True:
            try:
                response = input(message).strip().lower()
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no', '']:
                    return False
                else:
                    print("Please enter 'y' for yes or 'n' for no.")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    def _prompt_date_selection(self, date_manager: DateManager) -> Optional['DateRange']:
        """
        Interactive date selection prompt.
        
        Args:
            date_manager: DateManager instance
            
        Returns:
            DateRange object or None if user chooses to keep current dates
        """
        # Show current date range
        current_dates = self._get_current_date_range()
        print(f"\n📅 Current date range: {current_dates}")
        
        print("\n🗓️  Date Range Selection")
        print("=" * 50)
        print("Choose how to specify your date range:")
        print("  1. 📝 Enter custom date range")
        print("  2. 📋 Use preset options")
        print("  3. ⏭️  Keep current dates (skip update)")
        
        while True:
            try:
                choice = input("\nYour choice (1-3): ").strip()
                
                if choice == "1":
                    return self._prompt_custom_date_range(date_manager)
                elif choice == "2":
                    return self._prompt_preset_dates(date_manager)
                elif choice == "3":
                    print("📅 Keeping current date ranges")
                    return None
                else:
                    print("❌ Invalid choice. Please enter 1, 2, or 3.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    def _prompt_custom_date_range(self, date_manager: DateManager) -> Optional['DateRange']:
        """
        Prompt for custom date range with validation.
        
        Args:
            date_manager: DateManager instance
            
        Returns:
            DateRange object or None if user cancels
        """
        print("\n📝 Custom Date Range Entry")
        print("=" * 40)
        print("Enter your date range in any of these formats:")
        print("  • 2023-01-01 to 2023-12-31  (ISO format)")
        print("  • January 2023 to December 2023  (Natural language)")
        print("  • 2023  (Full year)")
        print("  • Q1 2024  (Quarter)")
        print("  • 2023-06  (Single month)")
        print("  • last 6 months  (Relative)")
        print("  • last 30 days  (Relative)")
        print("\n💡 Tip: Type 'help' for more examples or 'cancel' to go back")
        
        while True:
            try:
                user_input = input("\n📅 Date range: ").strip()
                
                if user_input.lower() == 'cancel':
                    return None
                elif user_input.lower() == 'help':
                    self._show_date_format_help()
                    continue
                elif not user_input:
                    print("❌ Please enter a date range or 'cancel' to go back.")
                    continue
                
                try:
                    # Parse the date range
                    date_range = date_manager.parse_date_range_string(user_input)
                    
                    # Validate the date range
                    validation_result = date_manager.get_validation_result(date_range)
                    
                    # Show parsed result
                    print(f"\n✅ Parsed successfully:")
                    print(f"   📅 Date range: {date_range.to_readable_format()}")
                    print(f"   📊 Duration: {date_range.duration_days()} days")
                    print(f"   🔧 CTL format: {date_range.to_ctl_format()}")
                    print(f"   📝 Format used: {date_range.format_used.value}")
                    
                    # Show validation issues
                    if not validation_result.is_valid:
                        print(f"\n❌ Validation issues:")
                        for issue in validation_result.issues:
                            print(f"   • {issue}")
                        
                        if not self._prompt_yes_no("Continue anyway? (y/N): "):
                            continue
                    
                    # Show warnings
                    if validation_result.warnings:
                        print(f"\n⚠️  Warnings:")
                        for warning in validation_result.warnings:
                            print(f"   • {warning}")
                    
                    # Confirm with user
                    if self._prompt_yes_no(f"\nConfirm this date range? (Y/n): "):
                        return date_range
                    else:
                        print("Please try again with a different date range.")
                        
                except DateValidationError as e:
                    print(f"\n❌ Error parsing date range: {e}")
                    print("Please try again with a different format.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    def _prompt_preset_dates(self, date_manager: DateManager) -> Optional['DateRange']:
        """
        Prompt for preset date options.
        
        Args:
            date_manager: DateManager instance
            
        Returns:
            DateRange object or None if user cancels
        """
        print("\n📋 Preset Date Options")
        print("=" * 30)
        
        suggestions = date_manager.get_date_suggestions()
        
        # Display options
        options = list(suggestions.items())
        for i, (name, date_str) in enumerate(options, 1):
            display_name = name.replace('_', ' ').title()
            print(f"  {i:2d}. {display_name}: {date_str}")
        
        print(f"  {len(options) + 1:2d}. ⏭️  Cancel (go back)")
        
        while True:
            try:
                choice = input(f"\nSelect option (1-{len(options) + 1}): ").strip()
                
                try:
                    choice_num = int(choice)
                    if choice_num == len(options) + 1:
                        return None
                    elif 1 <= choice_num <= len(options):
                        selected_name, selected_date_str = options[choice_num - 1]
                        
                        try:
                            # Parse the selected preset
                            date_range = date_manager.parse_date_range_string(selected_date_str)
                            
                            print(f"\n✅ Selected: {selected_name.replace('_', ' ').title()}")
                            print(f"   📅 Date range: {date_range.to_readable_format()}")
                            print(f"   📊 Duration: {date_range.duration_days()} days")
                            
                            # Validate
                            validation_result = date_manager.get_validation_result(date_range)
                            if validation_result.warnings:
                                print(f"\n⚠️  Warnings:")
                                for warning in validation_result.warnings:
                                    print(f"   • {warning}")
                            
                            if self._prompt_yes_no(f"\nConfirm this selection? (Y/n): "):
                                return date_range
                            else:
                                print("Please make another selection.")
                                
                        except DateValidationError as e:
                            print(f"❌ Error with preset '{selected_name}': {e}")
                            print("Please select a different option.")
                    else:
                        print(f"❌ Invalid choice. Please enter 1-{len(options) + 1}.")
                        
                except ValueError:
                    print(f"❌ Invalid input. Please enter a number 1-{len(options) + 1}.")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)
    
    def _show_date_format_help(self):
        """Show detailed help for date formats."""
        print("\n📚 Date Format Help")
        print("=" * 50)
        print("Supported date range formats:")
        print()
        print("📅 ISO Date Ranges:")
        print("   • 2023-01-01 to 2023-12-31")
        print("   • 2024-06-15 to 2024-08-30")
        print()
        print("📝 Natural Language:")
        print("   • January 2023 to December 2023")
        print("   • June 2024 to August 2024")
        print()
        print("🗓️  Shorthand Formats:")
        print("   • 2023  (entire year 2023)")
        print("   • Q1 2024  (first quarter of 2024)")
        print("   • Q4 2023  (fourth quarter of 2023)")
        print("   • 2023-06  (entire month of June 2023)")
        print("   • June 2023  (entire month of June 2023)")
        print()
        print("⏰ Relative Dates:")
        print("   • last 30 days")
        print("   • last 6 months")
        print("   • last 1 year")
        print()
        print("🔧 Technical Format (CTL):")
        print("   • 202301010000/to/202312310000")
        print()
    
    def _update_control_file_dates(self, date_manager: DateManager, date_range: 'DateRange') -> bool:
        """
        Update control files with new date range.
        
        Args:
            date_manager: DateManager instance
            date_range: New date range to apply
            
        Returns:
            True if successful, False otherwise
        """
        try:
            control_files = self._get_control_files()
            
            if not control_files:
                print("❌ No control files found to update")
                return False
            
            print(f"\n🔄 Updating {len(control_files)} control files...")
            print(f"   📅 New date range: {date_range.to_readable_format()}")
            print(f"   🔧 CTL format: {date_range.to_ctl_format()}")
            
            # Perform batch update
            result = date_manager.batch_modify_ctl_files(control_files, date_range)
            
            if result.success:
                print(f"✅ Successfully updated {result.files_updated} control files")
                
                # Show any warnings from individual file updates
                failed_files = [fr for fr in result.file_results if not fr.success]
                if failed_files:
                    print(f"⚠️  {len(failed_files)} files had issues:")
                    for file_result in failed_files[:5]:  # Show first 5 failures
                        print(f"   • {Path(file_result.file_path).name}: {file_result.error_message}")
                    if len(failed_files) > 5:
                        print(f"   • ... and {len(failed_files) - 5} more files")
                
                return True
            else:
                print(f"❌ Update failed: {result.error_message}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating control files: {e}")
            self.logger.error(f"Error updating control files: {e}")
            return False
    
    def start_full_automation(self):
        """
        Start full automation with enhanced dashboard.
        
        Initializes and starts the complete RDA automation system including
        all processing components and the web dashboard. This is the primary
        operational mode for continuous automation.
        
        The method:
            - Prompts for date range selection
            - Updates control files with new dates
            - Initializes the IntegratedBatchSystem
            - Starts the dashboard with automatic browser opening
            - Begins continuous request processing
            - Handles graceful shutdown on interruption
        
        Note:
            This method blocks until the system is stopped via Ctrl+C or
            system shutdown signal.
        """
        print("\n🚀 Starting full automation with enhanced dashboard...")
        print("="*60)
        
        try:
            # NEW: Date range selection step
            if self._should_prompt_for_dates():
                date_manager = create_date_manager()
                date_range = self._prompt_date_selection(date_manager)
                
                if date_range:
                    print(f"\n📅 Updating control files with date range: {date_range.original_input}")
                    
                    if self._update_control_file_dates(date_manager, date_range):
                        print("✅ Control files updated successfully")
                    else:
                        print("❌ Date update failed, aborting automation")
                        return
                else:
                    print("📅 Using existing date ranges in control files")
            
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            print("\n📊 Dashboard will start automatically with browser opening")
            print("🔄 Processing will begin after dashboard initialization")
            print("⏹️  Press Ctrl+C to stop gracefully")
            print("="*60)
            
            # Start processing (includes dashboard)
            self.system.process_all_control_files()
            
        except KeyboardInterrupt:
            print("\n⏹️  Processing stopped by user")
            if self.system:
                self.system.shutdown()
        except Exception as e:
            print(f"❌ Error during processing: {e}")
            self.logger.error(f"Error in full automation: {e}")
            if self.system:
                self.system.shutdown()
    
    def start_dashboard_only(self):
        """
        Start dashboard only mode.
        
        Starts the web dashboard in monitoring mode without initiating
        new request processing. This mode is useful for monitoring
        existing requests and system status.
        
        The method:
            - Initializes the system in monitoring mode
            - Starts the dashboard with browser opening
            - Displays existing request status without processing new requests
            - Handles graceful shutdown on interruption
        
        Note:
            This mode does not submit new requests but provides full
            visibility into current system state.
        """
        print("\n📊 Starting dashboard-only mode...")
        print("="*60)
        
        try:
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            print("🔍 Monitor mode: No new processing will start")
            print("📈 Dashboard will show existing request status")
            print("🌐 Browser will open automatically")
            print("⏹️  Press Ctrl+C to stop")
            print("="*60)
            
            # Start dashboard only
            self.system.monitor_dashboard_only()
            
        except KeyboardInterrupt:
            print("\n⏹️  Dashboard stopped by user")
            if self.system:
                self.system.shutdown()
        except Exception as e:
            print(f"❌ Error starting dashboard: {e}")
            self.logger.error(f"Error in dashboard mode: {e}")
            if self.system:
                self.system.shutdown()
    
    def resume_processing(self):
        """
        Resume interrupted processing.
        
        Resumes automation processing from a previously saved state,
        continuing where the system left off after an interruption.
        
        The method:
            - Optionally prompts for date range updates
            - Initializes the system with state recovery
            - Starts the dashboard for monitoring
            - Resumes processing from the saved state
            - Handles graceful shutdown on interruption
        
        Note:
            This mode attempts to recover and continue processing
            from the last known good state.
        """
        print("\n⏯️  Resuming interrupted processing...")
        print("="*60)
        
        try:
            # NEW: Optional date update prompt
            if self._prompt_yes_no("📅 Update date ranges before resuming? (y/N): "):
                date_manager = create_date_manager()
                date_range = self._prompt_date_selection(date_manager)
                
                if date_range:
                    print(f"\n📅 Updating control files with date range: {date_range.original_input}")
                    
                    if self._update_control_file_dates(date_manager, date_range):
                        print("✅ Control files updated successfully")
                    else:
                        print("❌ Date update failed, continuing with existing dates")
                else:
                    print("📅 Keeping existing date ranges")
            
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            print("\n📊 Dashboard will start automatically")
            print("🔄 Processing will resume from saved state")
            print("⏹️  Press Ctrl+C to stop gracefully")
            print("="*60)
            
            # Resume processing
            self.system.resume_processing()
            
        except KeyboardInterrupt:
            print("\n⏹️  Processing stopped by user")
            if self.system:
                self.system.shutdown()
        except Exception as e:
            print(f"❌ Error resuming processing: {e}")
            self.logger.error(f"Error resuming: {e}")
            if self.system:
                self.system.shutdown()
    
    def show_status(self):
        """
        Show current system status.
        
        Displays comprehensive information about the current state of
        the RDA automation system including request counts, processing
        status, system health, and current date ranges.
        
        The method:
            - Shows current date ranges in control files
            - Initializes the system for status checking
            - Retrieves and displays current status information
            - Provides guidance for accessing detailed monitoring
        
        Note:
            This is a read-only operation that does not modify system state.
        """
        print("\n📈 Current system status...")
        print("="*60)
        
        try:
            # Show current date range information
            print("📅 Current Date Range Information:")
            current_dates = self._get_current_date_range()
            print(f"   {current_dates}")
            
            control_files = self._get_control_files()
            if control_files:
                print(f"   📁 Control files: {len(control_files)} files found")
                
                # Sample a few files to show date consistency
                date_manager = create_date_manager()
                sample_files = control_files[:3]  # Check first 3 files
                dates_found = set()
                
                for file_path in sample_files:
                    date_str = date_manager.extract_date_from_ctl(file_path)
                    if date_str:
                        dates_found.add(date_str)
                
                if len(dates_found) == 1:
                    print("   ✅ All sampled files have consistent dates")
                elif len(dates_found) > 1:
                    print(f"   ⚠️  Found {len(dates_found)} different date ranges in files")
                    print("   💡 Consider updating dates for consistency")
            else:
                print("   ❌ No control files found")
            
            print()
            
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            # Show status
            self.system.show_status()
            
            print("\n💡 Tips:")
            print("   • Use dashboard mode to see detailed real-time status")
            print("   • Use 'Start full automation' to update dates and begin processing")
            
        except Exception as e:
            print(f"❌ Error getting status: {e}")
            self.logger.error(f"Error getting status: {e}")
    
    def run_interactive(self):
        """Run in interactive mode."""
        self.print_welcome_banner()
        
        if not self.check_prerequisites():
            return
        
        while True:
            choice = self.show_interactive_menu()
            
            if choice == '1':
                self.start_full_automation()
                break
            elif choice == '2':
                self.start_dashboard_only()
                break
            elif choice == '3':
                self.resume_processing()
                break
            elif choice == '4':
                self.show_status()
                input("\nPress Enter to continue...")
            elif choice == '5':
                print("👋 Goodbye!")
                break
    
    def run_with_args(self, args):
        """Run with command line arguments."""
        self.print_welcome_banner()
        
        if not self.check_prerequisites():
            return
        
        if args.start:
            self.start_full_automation()
        elif args.dashboard:
            self.start_dashboard_only()
        elif args.resume:
            self.resume_processing()
        elif args.status:
            self.show_status()


def main():
    """Main function for the startup script."""
    parser = argparse.ArgumentParser(
        description='RDA Automation System - User-Friendly Startup Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Interactive mode
  %(prog)s --start            # Start full automation
  %(prog)s --dashboard        # Dashboard only
  %(prog)s --resume           # Resume processing
  %(prog)s --status           # Show status

Features:
  • Automatic dashboard startup with browser opening
  • Enhanced user feedback and progress monitoring
  • Error handling and recovery guidance
  • Prerequisites checking and setup guidance
        """
    )
    
    parser.add_argument('--start', action='store_true',
                       help='Start full automation with dashboard')
    parser.add_argument('--dashboard', action='store_true',
                       help='Start dashboard only (monitor mode)')
    parser.add_argument('--resume', action='store_true',
                       help='Resume interrupted processing')
    parser.add_argument('--status', action='store_true',
                       help='Show current system status')
    
    args = parser.parse_args()
    
    # Create starter instance
    starter = RDAAutomationStarter()
    
    try:
        # Check if any arguments provided
        if any([args.start, args.dashboard, args.resume, args.status]):
            starter.run_with_args(args)
        else:
            # Run in interactive mode
            starter.run_interactive()
    
    except KeyboardInterrupt:
        print("\n👋 Startup interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()