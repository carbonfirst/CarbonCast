#!/usr/bin/env python3
"""
Enhanced Monitoring Integration for RDA Automation System

This module provides integration between the enhanced request monitoring system
and existing automation components, ensuring backward compatibility and seamless
operation with the current batch automation infrastructure.

Key Features:
- Integration with batch_automation_integrated.py
- Backward compatibility with existing monitoring
- Event-driven communication between components
- Dynamic processing triggers based on request count changes
- Unified monitoring dashboard integration
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

from automation.enhanced_request_monitor import (
    EnhancedRequestMonitor, create_enhanced_request_monitor
)
from automation.event_system import (
    EventDispatcher, EventType, EventPriority, BaseEvent,
    create_event_dispatcher, create_request_count_filter, create_processing_trigger_filter
)
from automation.monitoring_config import (
    EnhancedMonitoringConfig, create_default_monitoring_config,
    create_monitoring_config_manager
)


@dataclass
class IntegrationStatus:
    """Status of the enhanced monitoring integration."""
    enhanced_monitor_active: bool
    event_system_active: bool
    integration_callbacks_registered: int
    batch_system_connected: bool
    capacity_manager_connected: bool
    status_monitor_connected: bool
    last_integration_update: str
    integration_errors: int = 0


class EnhancedMonitoringIntegration:
    """
    Integration layer for enhanced monitoring with existing automation components.
    
    This class provides seamless integration between the new enhanced monitoring
    system and the existing batch automation infrastructure.
    """
    
    def __init__(self, 
                 config: Optional[EnhancedMonitoringConfig] = None,
                 enable_backward_compatibility: bool = True):
        """
        Initialize the enhanced monitoring integration.
        
        Args:
            config: Enhanced monitoring configuration
            enable_backward_compatibility: Whether to maintain backward compatibility
        """
        self.logger = self._setup_logging()
        self.config = config or create_default_monitoring_config()
        self.enable_backward_compatibility = enable_backward_compatibility
        
        # Core components
        self.event_dispatcher = create_event_dispatcher()
        self.enhanced_monitor = create_enhanced_request_monitor(
            config=self.config,
            event_dispatcher=self.event_dispatcher
        )
        
        # Integration state
        self.integration_active = False
        self.integration_status = IntegrationStatus(
            enhanced_monitor_active=False,
            event_system_active=False,
            integration_callbacks_registered=0,
            batch_system_connected=False,
            capacity_manager_connected=False,
            status_monitor_connected=False,
            last_integration_update=datetime.now().isoformat()
        )
        
        # Connected components
        self.batch_system = None
        self.capacity_manager = None
        self.status_monitor = None
        self.queue_manager = None
        
        # Integration callbacks
        self.processing_triggers: List[Callable] = []
        self.status_change_callbacks: List[Callable] = []
        
        # Setup event subscriptions
        self._setup_event_subscriptions()
        
        self.logger.info("EnhancedMonitoringIntegration initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.enhanced_monitoring_integration', level=logging.INFO)
    
    def _setup_event_subscriptions(self):
        """Set up event subscriptions for integration."""
        try:
            # Subscribe to request count changes
            self.event_dispatcher.subscribe(
                callback=self._handle_request_count_change,
                event_filter=create_request_count_filter(),
                subscription_id="integration_request_count"
            )
            
            # Subscribe to processing triggers
            self.event_dispatcher.subscribe(
                callback=self._handle_processing_trigger,
                event_filter=create_processing_trigger_filter(),
                subscription_id="integration_processing_trigger"
            )
            
            self.integration_status.integration_callbacks_registered = 2
            self.logger.info("✅ Event subscriptions configured")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup event subscriptions: {e}")
            self.integration_status.integration_errors += 1
    
    def connect_batch_system(self, batch_system):
        """
        Connect to the batch automation system.
        
        Args:
            batch_system: BatchAutomationSystem instance
        """
        try:
            self.batch_system = batch_system
            
            # Set integration components in enhanced monitor
            self.enhanced_monitor.set_integration_components(
                batch_system=batch_system,
                capacity_manager=self.capacity_manager,
                status_monitor=self.status_monitor
            )
            
            self.integration_status.batch_system_connected = True
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("✅ Batch system connected to enhanced monitoring")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect batch system: {e}")
            self.integration_status.integration_errors += 1
    
    def connect_capacity_manager(self, capacity_manager):
        """
        Connect to the capacity manager.
        
        Args:
            capacity_manager: CapacityManager instance
        """
        try:
            self.capacity_manager = capacity_manager
            
            # Update enhanced monitor integration
            self.enhanced_monitor.set_integration_components(
                batch_system=self.batch_system,
                capacity_manager=capacity_manager,
                status_monitor=self.status_monitor
            )
            
            self.integration_status.capacity_manager_connected = True
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("✅ Capacity manager connected to enhanced monitoring")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect capacity manager: {e}")
            self.integration_status.integration_errors += 1
    
    def connect_status_monitor(self, status_monitor):
        """
        Connect to the status monitor.
        
        Args:
            status_monitor: StatusMonitor instance
        """
        try:
            self.status_monitor = status_monitor
            
            # Update enhanced monitor integration
            self.enhanced_monitor.set_integration_components(
                batch_system=self.batch_system,
                capacity_manager=self.capacity_manager,
                status_monitor=status_monitor
            )
            
            self.integration_status.status_monitor_connected = True
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("✅ Status monitor connected to enhanced monitoring")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect status monitor: {e}")
            self.integration_status.integration_errors += 1
    
    def connect_queue_manager(self, queue_manager):
        """
        Connect to the queue manager.
        
        Args:
            queue_manager: IntelligentQueueManager instance
        """
        try:
            self.queue_manager = queue_manager
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("✅ Queue manager connected to enhanced monitoring")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect queue manager: {e}")
            self.integration_status.integration_errors += 1
    
    def _handle_request_count_change(self, event: BaseEvent):
        """
        Handle request count change events.
        
        Args:
            event: Request count change event
        """
        try:
            if hasattr(event, 'current_count') and hasattr(event, 'previous_count'):
                current_count = event.current_count
                previous_count = event.previous_count
                change_delta = event.change_delta
                
                self.logger.info(f"🔄 Processing request count change: {previous_count} → {current_count} (Δ{change_delta})")
                
                # Notify status change callbacks
                for callback in self.status_change_callbacks:
                    try:
                        callback(current_count, previous_count, change_delta)
                    except Exception as e:
                        self.logger.error(f"❌ Error in status change callback: {e}")
                
                # Update integration status
                self.integration_status.last_integration_update = datetime.now().isoformat()
                
        except Exception as e:
            self.logger.error(f"❌ Error handling request count change: {e}")
            self.integration_status.integration_errors += 1
    
    def _handle_processing_trigger(self, event: BaseEvent):
        """
        Handle processing trigger events.
        
        Args:
            event: Processing trigger event
        """
        try:
            if hasattr(event, 'data'):
                trigger_type = event.data.get('trigger_type', 'unknown')
                trigger_reason = event.data.get('trigger_reason', '')
                suggested_action = event.data.get('suggested_action', '')
                urgency_level = event.data.get('urgency_level', 'normal')
                
                self.logger.info(f"🚀 Processing trigger: {trigger_type} - {trigger_reason}")
                
                # Execute appropriate actions based on trigger type
                if trigger_type == "low_request_count":
                    self._handle_low_request_count_trigger(event)
                elif trigger_type == "approaching_capacity":
                    self._handle_approaching_capacity_trigger(event)
                elif trigger_type == "at_capacity":
                    self._handle_at_capacity_trigger(event)
                elif trigger_type == "significant_drop":
                    self._handle_significant_drop_trigger(event)
                
                # Notify processing trigger callbacks
                for callback in self.processing_triggers:
                    try:
                        callback(trigger_type, trigger_reason, suggested_action, urgency_level)
                    except Exception as e:
                        self.logger.error(f"❌ Error in processing trigger callback: {e}")
                
                # Update integration status
                self.integration_status.last_integration_update = datetime.now().isoformat()
                
        except Exception as e:
            self.logger.error(f"❌ Error handling processing trigger: {e}")
            self.integration_status.integration_errors += 1
    
    def _handle_low_request_count_trigger(self, event: BaseEvent):
        """Handle low request count trigger."""
        try:
            self.logger.info("🔥 TRIGGER: Low request count - activating upload automation")
            
            # Trigger capacity manager upload automation if available
            if self.capacity_manager:
                try:
                    upload_result = self.capacity_manager.trigger_upload_automation()
                    if upload_result.success:
                        self.logger.info(f"✅ Upload automation triggered successfully: {upload_result.message}")
                    else:
                        self.logger.warning(f"⚠️ Upload automation failed: {upload_result.message}")
                except Exception as e:
                    self.logger.error(f"❌ Error triggering upload automation: {e}")
            
            # Notify batch system to check for new files
            if self.batch_system and hasattr(self.batch_system, '_auto_upload_new_files'):
                try:
                    current_count = event.data.get('current_count', 0)
                    available_slots = max(0, 10 - current_count)
                    self.batch_system._auto_upload_new_files(available_slots)
                    self.logger.info(f"✅ Batch system auto-upload triggered for {available_slots} slots")
                except Exception as e:
                    self.logger.error(f"❌ Error in batch system auto-upload: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling low request count trigger: {e}")
    
    def _handle_approaching_capacity_trigger(self, event: BaseEvent):
        """Handle approaching capacity trigger."""
        try:
            self.logger.info("⚠️ TRIGGER: Approaching capacity - increasing monitoring frequency")
            
            # Increase monitoring frequency in enhanced monitor
            if self.enhanced_monitor:
                # The enhanced monitor will automatically adjust intervals based on request count
                self.logger.info("📊 Enhanced monitor will automatically adjust intervals")
            
            # Notify capacity manager to prepare for capacity management
            if self.capacity_manager:
                try:
                    # Run a capacity monitoring cycle to prepare for potential crisis
                    cycle_result = self.capacity_manager.run_capacity_monitoring_cycle()
                    if cycle_result.get('success', False):
                        self.logger.info("✅ Capacity manager cycle completed successfully")
                    else:
                        self.logger.warning(f"⚠️ Capacity manager cycle issues: {cycle_result.get('error', 'Unknown')}")
                except Exception as e:
                    self.logger.error(f"❌ Error in capacity manager cycle: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling approaching capacity trigger: {e}")
    
    def _handle_at_capacity_trigger(self, event: BaseEvent):
        """Handle at capacity trigger."""
        try:
            self.logger.warning("🚨 TRIGGER: At capacity - activating emergency actions")
            
            # Activate capacity manager crisis mode
            if self.capacity_manager:
                try:
                    # Get current capacity status and execute crisis strategy
                    capacity_status = self.capacity_manager.get_current_capacity_status()
                    actions = self.capacity_manager.execute_capacity_strategy(capacity_status)
                    
                    self.logger.info(f"🔥 Capacity crisis actions executed: {len(actions)} actions taken")
                    for action in actions:
                        if hasattr(action, 'message'):
                            self.logger.info(f"   - {action.message}")
                        
                except Exception as e:
                    self.logger.error(f"❌ Error in capacity crisis management: {e}")
            
            # Trigger status monitor to process completed/error requests
            if self.status_monitor:
                try:
                    cycle_result = self.status_monitor.run_single_monitoring_cycle()
                    if cycle_result.get('cycle_completed', False):
                        stats = cycle_result.get('processing_stats', {})
                        self.logger.info(f"✅ Status monitor cycle: {stats.get('completed', 0)} completed, "
                                       f"{stats.get('errors_detected', 0)} errors processed")
                    else:
                        self.logger.warning(f"⚠️ Status monitor cycle failed: {cycle_result.get('error', 'Unknown')}")
                except Exception as e:
                    self.logger.error(f"❌ Error in status monitor cycle: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling at capacity trigger: {e}")
    
    def _handle_significant_drop_trigger(self, event: BaseEvent):
        """Handle significant drop trigger."""
        try:
            self.logger.info("📉 TRIGGER: Significant drop - investigating and maintaining capacity")
            
            # This could indicate completed requests or errors
            # Trigger upload automation to maintain target capacity
            if self.capacity_manager:
                try:
                    upload_result = self.capacity_manager.trigger_upload_automation()
                    if upload_result.success:
                        self.logger.info(f"✅ Capacity maintenance upload triggered: {upload_result.message}")
                    else:
                        self.logger.info(f"ℹ️ Upload not needed: {upload_result.message}")
                except Exception as e:
                    self.logger.error(f"❌ Error in capacity maintenance: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error handling significant drop trigger: {e}")
    
    def add_processing_trigger_callback(self, callback: Callable):
        """
        Add a callback for processing triggers.
        
        Args:
            callback: Function to call with (trigger_type, reason, action, urgency)
        """
        self.processing_triggers.append(callback)
        self.logger.info("✅ Processing trigger callback added")
    
    def add_status_change_callback(self, callback: Callable):
        """
        Add a callback for status changes.
        
        Args:
            callback: Function to call with (current_count, previous_count, delta)
        """
        self.status_change_callbacks.append(callback)
        self.logger.info("✅ Status change callback added")
    
    def start_integration(self):
        """Start the enhanced monitoring integration."""
        try:
            if self.integration_active:
                self.logger.warning("⚠️ Integration is already active")
                return
            
            # Start event system
            self.integration_status.event_system_active = True
            
            # Start enhanced monitor
            self.enhanced_monitor.start_monitoring()
            self.integration_status.enhanced_monitor_active = True
            
            self.integration_active = True
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("🚀 Enhanced monitoring integration started")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start integration: {e}")
            self.integration_status.integration_errors += 1
    
    def stop_integration(self):
        """Stop the enhanced monitoring integration."""
        try:
            if not self.integration_active:
                return
            
            # Stop enhanced monitor
            self.enhanced_monitor.stop_monitoring()
            self.integration_status.enhanced_monitor_active = False
            
            # Stop event system
            self.event_dispatcher.stop_async_dispatch()
            self.integration_status.event_system_active = False
            
            self.integration_active = False
            self.integration_status.last_integration_update = datetime.now().isoformat()
            
            self.logger.info("🛑 Enhanced monitoring integration stopped")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping integration: {e}")
            self.integration_status.integration_errors += 1
    
    def get_integration_status(self) -> Dict[str, Any]:
        """
        Get current integration status.
        
        Returns:
            Dictionary with integration status information
        """
        try:
            # Get enhanced monitor status
            monitor_status = self.enhanced_monitor.get_current_status()
            
            # Get event dispatcher statistics
            event_stats = self.event_dispatcher.get_statistics()
            
            return {
                "integration_active": self.integration_active,
                "integration_status": asdict(self.integration_status),
                "enhanced_monitor_status": monitor_status,
                "event_system_statistics": event_stats,
                "configuration": {
                    "monitoring_mode": self.config.monitoring_mode.value,
                    "backward_compatibility": self.enable_backward_compatibility,
                    "adaptive_intervals_enabled": self.config.adaptive_intervals.enabled
                },
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error getting integration status: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}
    
    def cleanup(self):
        """Clean up the integration."""
        self.logger.info("🧹 Cleaning up EnhancedMonitoringIntegration...")
        
        # Stop integration
        self.stop_integration()
        
        # Clean up components
        if self.enhanced_monitor:
            self.enhanced_monitor.cleanup()
        
        if self.event_dispatcher:
            self.event_dispatcher.cleanup()
        
        # Clear callbacks
        self.processing_triggers.clear()
        self.status_change_callbacks.clear()
        
        self.logger.info("✅ EnhancedMonitoringIntegration cleanup completed")


def create_enhanced_monitoring_integration(config: Optional[EnhancedMonitoringConfig] = None,
                                         enable_backward_compatibility: bool = True) -> EnhancedMonitoringIntegration:
    """
    Factory function to create an EnhancedMonitoringIntegration.
    
    Args:
        config: Enhanced monitoring configuration
        enable_backward_compatibility: Whether to maintain backward compatibility
        
    Returns:
        EnhancedMonitoringIntegration instance
    """
    return EnhancedMonitoringIntegration(
        config=config,
        enable_backward_compatibility=enable_backward_compatibility
    )


def integrate_with_batch_system(batch_system, 
                               capacity_manager=None, 
                               status_monitor=None,
                               queue_manager=None,
                               config: Optional[EnhancedMonitoringConfig] = None) -> EnhancedMonitoringIntegration:
    """
    Convenience function to integrate enhanced monitoring with existing batch system.
    
    Args:
        batch_system: BatchAutomationSystem instance
        capacity_manager: Optional CapacityManager instance
        status_monitor: Optional StatusMonitor instance
        queue_manager: Optional IntelligentQueueManager instance
        config: Optional enhanced monitoring configuration
        
    Returns:
        Configured and connected EnhancedMonitoringIntegration instance
    """
    try:
        # Create integration
        integration = create_enhanced_monitoring_integration(config=config)
        
        # Connect components
        integration.connect_batch_system(batch_system)
        
        if capacity_manager:
            integration.connect_capacity_manager(capacity_manager)
        
        if status_monitor:
            integration.connect_status_monitor(status_monitor)
        
        if queue_manager:
            integration.connect_queue_manager(queue_manager)
        
        # Start integration
        integration.start_integration()
        
        logging.getLogger('rda_automation.integration').info(
            "✅ Enhanced monitoring successfully integrated with batch system"
        )
        
        return integration
        
    except Exception as e:
        logging.getLogger('rda_automation.integration').error(
            f"❌ Failed to integrate enhanced monitoring: {e}"
        )
        raise


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Monitoring Integration')
    parser.add_argument('--test-integration', action='store_true',
                       help='Test integration functionality')
    parser.add_argument('--status', action='store_true',
                       help='Show integration status')
    
    args = parser.parse_args()
    
    if args.test_integration:
        print("=== Testing Enhanced Monitoring Integration ===")
        
        # Create integration
        integration = create_enhanced_monitoring_integration()
        
        # Add test callbacks
        def test_trigger_callback(trigger_type, reason, action, urgency):
            print(f"🚀 Trigger: {trigger_type} - {reason} (urgency: {urgency})")
        
        def test_status_callback(current, previous, delta):
            print(f"📊 Status: {previous} → {current} (Δ{delta})")
        
        integration.add_processing_trigger_callback(test_trigger_callback)
        integration.add_status_change_callback(test_status_callback)
        
        # Start integration
        integration.start_integration()
        
        try:
            print("Integration running... Press Ctrl+C to stop")
            while integration.integration_active:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping integration...")
        finally:
            integration.cleanup()
    
    elif args.status:
        print("=== Integration Status ===")
        integration = create_enhanced_monitoring_integration()
        status = integration.get_integration_status()
        print(json.dumps(status, indent=2))
        integration.cleanup()
    
    else:
        parser.print_help()
        print("\n" + "="*60)
        print("ENHANCED MONITORING INTEGRATION EXAMPLES")
        print("="*60)
        print("# Test integration:")
        print("python automation/enhanced_monitoring_integration.py --test-integration")
        print("\n# Show status:")
        print("python automation/enhanced_monitoring_integration.py --status")
        print("="*60)