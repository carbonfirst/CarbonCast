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

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from batch_automation_integrated import IntegratedBatchSystem
    from automation.dashboard import create_dashboard
    from directory_utils import setup_directories
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
        """
        Setup logging for the starter.
        
        Configures a logger with appropriate formatting for startup operations.
        
        Returns:
            logging.Logger: Configured logger instance for the starter.
        """
        logger = logging.getLogger('rda_automation_starter')
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
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
        configuration files, and authentication tokens.
        
        The method checks for:
            - Control files directory and contents
            - RDA authentication token file
            - Required data and logs directories
        
        Returns:
            bool: True if all prerequisites are satisfied, False otherwise.
                When False, detailed guidance is provided to resolve issues.
        
        Note:
            This method will attempt to create missing directories automatically
            but requires manual intervention for missing files.
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
        
        if issues:
            print("\n❌ Prerequisites check failed:")
            for issue in issues:
                print(f"   {issue}")
            print("\n📋 To fix these issues:")
            print("   1. Ensure control files are in the 'control_files/' directory")
            print("   2. Create 'rdams_token.txt' with your RDA authentication token")
            print("   3. Run this script again")
            return False
        
        print("✅ All prerequisites satisfied!")
        return True
    
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
    
    def start_full_automation(self):
        """
        Start full automation with enhanced dashboard.
        
        Initializes and starts the complete RDA automation system including
        all processing components and the web dashboard. This is the primary
        operational mode for continuous automation.
        
        The method:
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
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            print("📊 Dashboard will start automatically with browser opening")
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
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            print("📊 Dashboard will start automatically")
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
        status, and system health.
        
        The method:
            - Initializes the system for status checking
            - Retrieves and displays current status information
            - Provides guidance for accessing detailed monitoring
        
        Note:
            This is a read-only operation that does not modify system state.
        """
        print("\n📈 Current system status...")
        print("="*60)
        
        try:
            # Initialize system
            self.system = IntegratedBatchSystem()
            
            # Show status
            self.system.show_status()
            
            print("\n💡 Tip: Use dashboard mode to see detailed real-time status")
            
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