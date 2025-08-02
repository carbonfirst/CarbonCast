#!/usr/bin/env python3
"""
Sequential File Processor Runner Script

This script provides a simple command-line interface for the Sequential File Processor
that can be executed directly without module path issues.

Usage:
    python3 run_sequential_processor.py --discover
    python3 run_sequential_processor.py --start
    python3 run_sequential_processor.py --status
    python3 run_sequential_processor.py --stop
    python3 run_sequential_processor.py --resume SESSION_ID
"""

import sys
import os
import argparse
import json
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from automation.sequential_file_processor import (
        SequentialFileProcessor, ProcessingConfig, create_sequential_file_processor
    )
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you're running this script from the src/python directory")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Sequential File Processor for RDA Automation')
    parser.add_argument('--start', action='store_true',
                       help='Start sequential file processing')
    parser.add_argument('--resume', type=str,
                       help='Resume processing from session ID')
    parser.add_argument('--status', action='store_true',
                       help='Show current processing status')
    parser.add_argument('--stop', action='store_true',
                       help='Stop current processing')
    parser.add_argument('--discover', action='store_true',
                       help='Discover control files only')
    parser.add_argument('--config-file', type=str,
                       help='Path to configuration file')
    parser.add_argument('--control-files-dir', default='control_files',
                       help='Control files directory')
    parser.add_argument('--processing-order', choices=['alphabetical', 'priority', 'region', 'variable'],
                       default='alphabetical', help='File processing order')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum retries per file')
    parser.add_argument('--submission-delay', type=float, default=5.0,
                       help='Delay between file submissions (seconds)')
    
    args = parser.parse_args()
    
    # Create configuration
    config = ProcessingConfig()
    config.control_files_dir = args.control_files_dir
    config.processing_order = args.processing_order
    config.max_retries_per_file = args.max_retries
    config.file_submission_delay = args.submission_delay
    
    # Load configuration file if provided
    if args.config_file and os.path.exists(args.config_file):
        try:
            with open(args.config_file, 'r') as f:
                config_data = json.load(f)
                # Update config with loaded data
                for key, value in config_data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except Exception as e:
            print(f"Error loading configuration: {e}")
    
    # Create sequential processor
    try:
        processor = create_sequential_file_processor(config)
    except Exception as e:
        print(f"❌ Error creating processor: {e}")
        return 1
    
    try:
        if args.start:
            print("=" * 80)
            print("🚀 SEQUENTIAL FILE PROCESSOR - STARTING")
            print("=" * 80)
            print(f"Control Files Directory: {config.control_files_dir}")
            print(f"Processing Order: {config.processing_order}")
            print(f"Max Retries: {config.max_retries_per_file}")
            print(f"Submission Delay: {config.file_submission_delay}s")
            print("=" * 80)
            
            success = processor.start_processing()
            if success:
                print("✅ Sequential processing started successfully")
                print("Press Ctrl+C to stop gracefully")
                
                # Keep running until processing completes or is interrupted
                try:
                    while processor.processing_active:
                        time.sleep(1)
                    
                    # Get final result
                    result = processor.get_processing_result()
                    print("\n" + "=" * 80)
                    print("🎉 SEQUENTIAL PROCESSING COMPLETED")
                    print("=" * 80)
                    print(f"Session ID: {result.session_id}")
                    print(f"Success: {result.success}")
                    print(f"Total Files: {result.total_files}")
                    print(f"Completed: {result.completed_files}")
                    print(f"Failed: {result.failed_files}")
                    print(f"Processing Time: {result.processing_time_hours:.2f} hours")
                    print("=" * 80)
                    
                except KeyboardInterrupt:
                    print("\nShutdown requested...")
                    processor.stop_processing()
            else:
                print("❌ Failed to start sequential processing")
                return 1
        
        elif args.resume:
            print(f"=== Resuming Sequential Processing: {args.resume} ===")
            success = processor.start_processing(resume_session_id=args.resume)
            if success:
                print("✅ Processing resumed successfully")
                try:
                    while processor.processing_active:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nShutdown requested...")
                    processor.stop_processing()
            else:
                print("❌ Failed to resume processing")
                return 1
        
        elif args.status:
            print("=== Current Processing Status ===")
            status = processor.get_processing_status()
            print(json.dumps(status, indent=2, default=str))
        
        elif args.stop:
            print("=== Stopping Sequential Processing ===")
            processor.stop_processing()
            print("✅ Processing stopped")
        
        elif args.discover:
            print("=== Discovering Control Files ===")
            success, file_list, discovery_info = processor.discover_files()
            
            if success:
                print(f"✅ Discovered {len(file_list)} files:")
                for i, filename in enumerate(file_list, 1):
                    print(f"  {i:3d}. {filename}")
                
                print(f"\nDiscovery Statistics:")
                print(json.dumps(discovery_info, indent=2, default=str))
            else:
                print(f"❌ File discovery failed: {discovery_info.get('error', 'Unknown error')}")
                return 1
        
        else:
            parser.print_help()
            print("\n" + "="*80)
            print("SEQUENTIAL FILE PROCESSOR EXAMPLES")
            print("="*80)
            print("# Start sequential processing:")
            print("python3 run_sequential_processor.py --start")
            print("\n# Resume processing from session:")
            print("python3 run_sequential_processor.py --resume SESSION_ID")
            print("\n# Check processing status:")
            print("python3 run_sequential_processor.py --status")
            print("\n# Stop current processing:")
            print("python3 run_sequential_processor.py --stop")
            print("\n# Discover control files:")
            print("python3 run_sequential_processor.py --discover")
            print("\n# Custom configuration:")
            print("python3 run_sequential_processor.py --start --control-files-dir custom_files --submission-delay 2.0")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())