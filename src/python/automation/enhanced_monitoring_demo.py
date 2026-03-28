#!/usr/bin/env python3
"""
Enhanced Monitoring System Demo

This script demonstrates how to integrate the enhanced request monitoring system
with the existing batch automation infrastructure. It shows the complete integration
process and provides examples of how the system works.

Usage:
    python automation/enhanced_monitoring_demo.py --demo-integration
    python automation/enhanced_monitoring_demo.py --show-capabilities
    python automation/enhanced_monitoring_demo.py --test-events
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any
from logger_utils import configure_root_logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import enhanced monitoring components
from automation.enhanced_request_monitor import create_enhanced_request_monitor
from automation.event_system import create_event_dispatcher, EventType, EventPriority
from automation.monitoring_config import create_default_monitoring_config
from automation.enhanced_monitoring_integration import (
    create_enhanced_monitoring_integration, integrate_with_batch_system
)

# Import existing components (with error handling for missing components)
try:
    from batch_automation import BatchAutomationSystem
    BATCH_SYSTEM_AVAILABLE = True
except ImportError:
    BATCH_SYSTEM_AVAILABLE = False
    print("⚠️ BatchAutomationSystem not available - using mock")

try:
    from automation.capacity_manager import create_capacity_manager
    CAPACITY_MANAGER_AVAILABLE = True
except ImportError:
    CAPACITY_MANAGER_AVAILABLE = False
    print("⚠️ CapacityManager not available - using mock")

try:
    from automation.status_monitor import create_status_monitor
    STATUS_MONITOR_AVAILABLE = True
except ImportError:
    STATUS_MONITOR_AVAILABLE = False
    print("⚠️ StatusMonitor not available - using mock")


class MockBatchSystem:
    """Mock batch system for demonstration when real one is not available."""
    
    def __init__(self):
        self.requests_state = {}
        self._current_count = 5  # Simulate 5 active requests
    
    def _get_current_request_count(self):
        return self._current_count
    
    def _auto_upload_new_files(self, available_slots):
        print(f"🔄 Mock: Auto-uploading files for {available_slots} slots")
        # Simulate adding requests
        self._current_count = min(10, self._current_count + available_slots)


class MockCapacityManager:
    """Mock capacity manager for demonstration."""
    
    def trigger_upload_automation(self):
        print("🚀 Mock: Upload automation triggered")
        return type('Result', (), {'success': True, 'message': 'Mock upload successful'})()
    
    def get_current_capacity_status(self):
        return type('Status', (), {'total_requests': 7, 'capacity_level': 'normal'})()
    
    def execute_capacity_strategy(self, status):
        print("⚡ Mock: Executing capacity strategy")
        return [type('Action', (), {'message': 'Mock capacity action executed'})()]
    
    def run_capacity_monitoring_cycle(self):
        return {'success': True, 'message': 'Mock capacity cycle completed'}


class MockStatusMonitor:
    """Mock status monitor for demonstration."""
    
    def run_single_monitoring_cycle(self):
        return {
            'cycle_completed': True,
            'processing_stats': {
                'completed': 2,
                'errors_detected': 1,
                'purged_confirmed': 1
            }
        }


def setup_logging():
    """Setup logging for the demo."""
    configure_root_logging(level=logging.INFO)


def demo_enhanced_monitoring_capabilities():
    """Demonstrate the capabilities of the enhanced monitoring system."""
    print("\n" + "="*80)
    print("🌟 ENHANCED REQUEST MONITORING SYSTEM CAPABILITIES")
    print("="*80)
    
    # 1. Configuration System
    print("\n1. 📋 CONFIGURATION SYSTEM")
    print("-" * 40)
    
    config = create_default_monitoring_config()
    print(f"   • Monitoring Mode: {config.monitoring_mode.value}")
    print(f"   • Adaptive Intervals: {config.adaptive_intervals.enabled}")
    print(f"   • Base Interval: {config.adaptive_intervals.base_interval}s")
    print(f"   • Event System: {config.event_system.enabled}")
    print(f"   • Active Thresholds: {len(config.get_active_thresholds())}")
    
    # Show adaptive interval calculation
    print("\n   📊 Adaptive Interval Examples:")
    for count in [2, 5, 8, 10, 12]:
        interval = config.calculate_monitoring_interval(count)
        print(f"      {count} requests → {interval}s interval")
    
    # 2. Event System
    print("\n2. 📡 EVENT SYSTEM")
    print("-" * 40)
    
    event_dispatcher = create_event_dispatcher()
    
    # Create sample events
    request_count_event = event_dispatcher.create_request_count_event(
        source_component="demo",
        previous_count=8,
        current_count=5,
        threshold_crossed="low_request_count"
    )
    
    trigger_event = event_dispatcher.create_processing_trigger_event(
        source_component="demo",
        trigger_type="low_request_count",
        trigger_reason="Request count dropped below threshold",
        suggested_action="trigger_upload_automation"
    )
    
    print(f"   • Request Count Event: {request_count_event.event_type.value}")
    print(f"   • Change Delta: {request_count_event.change_delta}")
    print(f"   • Threshold Crossed: {request_count_event.threshold_crossed}")
    print(f"   • Processing Trigger: {trigger_event.trigger_type}")
    print(f"   • Suggested Action: {trigger_event.suggested_action}")
    
    # 3. Enhanced Request Monitor
    print("\n3. 🔍 ENHANCED REQUEST MONITOR")
    print("-" * 40)
    
    monitor = create_enhanced_request_monitor(config=config, event_dispatcher=event_dispatcher)
    
    # Create a snapshot
    snapshot = monitor.create_snapshot()
    print(f"   • Current Requests: {snapshot.total_requests}")
    print(f"   • Status Level: {snapshot.status_level.value}")
    print(f"   • Timestamp: {snapshot.timestamp}")
    
    # Show monitoring statistics
    stats = monitor.statistics
    print(f"   • Monitoring Cycles: {stats.total_monitoring_cycles}")
    print(f"   • Average Request Count: {stats.average_request_count}")
    
    # Cleanup
    event_dispatcher.cleanup()
    monitor.cleanup()
    
    print("\n✅ Capabilities demonstration completed")


def demo_integration_with_existing_system():
    """Demonstrate integration with existing batch automation system."""
    print("\n" + "="*80)
    print("🔗 INTEGRATION WITH EXISTING BATCH AUTOMATION SYSTEM")
    print("="*80)
    
    # Create or mock existing components
    if BATCH_SYSTEM_AVAILABLE:
        try:
            batch_system = BatchAutomationSystem()
            print("✅ Real BatchAutomationSystem loaded")
        except Exception as e:
            print(f"⚠️ Using mock batch system due to error: {e}")
            batch_system = MockBatchSystem()
    else:
        batch_system = MockBatchSystem()
        print("🔄 Using MockBatchSystem for demonstration")
    
    if CAPACITY_MANAGER_AVAILABLE:
        try:
            capacity_manager = create_capacity_manager()
            print("✅ Real CapacityManager loaded")
        except Exception as e:
            print(f"⚠️ Using mock capacity manager due to error: {e}")
            capacity_manager = MockCapacityManager()
    else:
        capacity_manager = MockCapacityManager()
        print("🔄 Using MockCapacityManager for demonstration")
    
    if STATUS_MONITOR_AVAILABLE:
        try:
            status_monitor = create_status_monitor()
            print("✅ Real StatusMonitor loaded")
        except Exception as e:
            print(f"⚠️ Using mock status monitor due to error: {e}")
            status_monitor = MockStatusMonitor()
    else:
        status_monitor = MockStatusMonitor()
        print("🔄 Using MockStatusMonitor for demonstration")
    
    # Create enhanced monitoring integration
    print("\n📋 Creating Enhanced Monitoring Integration...")
    
    try:
        integration = integrate_with_batch_system(
            batch_system=batch_system,
            capacity_manager=capacity_manager,
            status_monitor=status_monitor
        )
        
        print("✅ Integration created successfully")
        
        # Show integration status
        print("\n📊 Integration Status:")
        status = integration.get_integration_status()
        
        integration_status = status.get('integration_status', {})
        print(f"   • Integration Active: {status.get('integration_active', False)}")
        print(f"   • Enhanced Monitor Active: {integration_status.get('enhanced_monitor_active', False)}")
        print(f"   • Event System Active: {integration_status.get('event_system_active', False)}")
        print(f"   • Batch System Connected: {integration_status.get('batch_system_connected', False)}")
        print(f"   • Capacity Manager Connected: {integration_status.get('capacity_manager_connected', False)}")
        print(f"   • Status Monitor Connected: {integration_status.get('status_monitor_connected', False)}")
        
        # Add demo callbacks
        print("\n🔔 Adding Integration Callbacks...")
        
        def demo_trigger_callback(trigger_type, reason, action, urgency):
            print(f"   🚀 TRIGGER: {trigger_type}")
            print(f"      Reason: {reason}")
            print(f"      Action: {action}")
            print(f"      Urgency: {urgency}")
        
        def demo_status_callback(current, previous, delta):
            print(f"   📊 STATUS CHANGE: {previous} → {current} (Δ{delta})")
        
        integration.add_processing_trigger_callback(demo_trigger_callback)
        integration.add_status_change_callback(demo_status_callback)
        
        print("✅ Callbacks registered")
        
        # Run for a short time to demonstrate
        print("\n⏱️ Running integration for 30 seconds to demonstrate functionality...")
        print("   (The system will automatically detect request count changes and trigger actions)")
        
        start_time = time.time()
        while time.time() - start_time < 30:
            time.sleep(1)
            
            # Simulate request count changes every 10 seconds
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                if hasattr(batch_system, '_current_count'):
                    # Simulate a request count change
                    old_count = batch_system._current_count
                    batch_system._current_count = max(1, old_count - 2)  # Simulate completion
                    print(f"\n🔄 Simulated request count change: {old_count} → {batch_system._current_count}")
        
        print("\n✅ Integration demonstration completed")
        
        # Cleanup
        integration.cleanup()
        
    except Exception as e:
        print(f"❌ Integration failed: {e}")
        import traceback
        traceback.print_exc()


def demo_event_system():
    """Demonstrate the event system functionality."""
    print("\n" + "="*80)
    print("📡 EVENT SYSTEM DEMONSTRATION")
    print("="*80)
    
    # Create event dispatcher
    event_dispatcher = create_event_dispatcher()
    
    # Create event callbacks
    events_received = []
    
    def request_count_callback(event):
        events_received.append(('request_count', event))
        print(f"   📊 Request Count Event: {event.previous_count} → {event.current_count}")
    
    def trigger_callback(event):
        events_received.append(('trigger', event))
        print(f"   🚀 Trigger Event: {event.trigger_type} - {event.trigger_reason}")
    
    # Subscribe to events
    print("\n🔔 Setting up event subscriptions...")
    
    from automation.event_system import create_request_count_filter, create_processing_trigger_filter
    
    sub1 = event_dispatcher.subscribe(
        callback=request_count_callback,
        event_filter=create_request_count_filter(),
        subscription_id="demo_request_count"
    )
    
    sub2 = event_dispatcher.subscribe(
        callback=trigger_callback,
        event_filter=create_processing_trigger_filter(),
        subscription_id="demo_triggers"
    )
    
    print(f"✅ Subscriptions created: {sub1}, {sub2}")
    
    # Dispatch sample events
    print("\n📤 Dispatching sample events...")
    
    # Request count change event
    count_event = event_dispatcher.create_request_count_event(
        source_component="demo",
        previous_count=10,
        current_count=7,
        threshold_crossed="low_request_count",
        priority=EventPriority.HIGH
    )
    
    event_dispatcher.dispatch_event(count_event, async_dispatch=False)
    
    # Processing trigger event
    trigger_event = event_dispatcher.create_processing_trigger_event(
        source_component="demo",
        trigger_type="low_request_count",
        trigger_reason="Request count dropped below 10",
        suggested_action="trigger_upload_automation",
        urgency_level="high",
        priority=EventPriority.HIGH
    )
    
    event_dispatcher.dispatch_event(trigger_event, async_dispatch=False)
    
    # Show statistics
    print("\n📈 Event System Statistics:")
    stats = event_dispatcher.get_statistics()
    dispatcher_stats = stats.get('dispatcher_stats', {})
    
    print(f"   • Total Events Dispatched: {dispatcher_stats.get('total_events_dispatched', 0)}")
    print(f"   • Active Subscriptions: {stats.get('active_subscriptions', 0)}")
    print(f"   • Events Received by Callbacks: {len(events_received)}")
    
    # Show event history
    history = event_dispatcher.get_event_history(limit=5)
    print(f"   • Event History Size: {len(history)}")
    
    for i, event_dict in enumerate(history):
        print(f"      {i+1}. {event_dict.get('event_type', 'unknown')} at {event_dict.get('timestamp', 'unknown')}")
    
    # Cleanup
    event_dispatcher.cleanup()
    
    print("\n✅ Event system demonstration completed")


def main():
    """Main function for the demo."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Monitoring System Demo')
    parser.add_argument('--demo-integration', action='store_true',
                       help='Demonstrate integration with existing system')
    parser.add_argument('--show-capabilities', action='store_true',
                       help='Show enhanced monitoring capabilities')
    parser.add_argument('--test-events', action='store_true',
                       help='Test event system functionality')
    parser.add_argument('--all', action='store_true',
                       help='Run all demonstrations')
    
    args = parser.parse_args()
    
    setup_logging()
    
    print("🌟 ENHANCED REQUEST MONITORING SYSTEM DEMO")
    print("=" * 80)
    print("This demo shows the capabilities and integration of the enhanced")
    print("request monitoring system with the existing RDA automation infrastructure.")
    print("=" * 80)
    
    try:
        if args.all or args.show_capabilities:
            demo_enhanced_monitoring_capabilities()
        
        if args.all or args.test_events:
            demo_event_system()
        
        if args.all or args.demo_integration:
            demo_integration_with_existing_system()
        
        if not any([args.demo_integration, args.show_capabilities, args.test_events, args.all]):
            parser.print_help()
            print("\n" + "="*60)
            print("DEMO EXAMPLES")
            print("="*60)
            print("# Show system capabilities:")
            print("python automation/enhanced_monitoring_demo.py --show-capabilities")
            print("\n# Test event system:")
            print("python automation/enhanced_monitoring_demo.py --test-events")
            print("\n# Demo integration:")
            print("python automation/enhanced_monitoring_demo.py --demo-integration")
            print("\n# Run all demos:")
            print("python automation/enhanced_monitoring_demo.py --all")
            print("="*60)
        
        print("\n🎉 Demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()