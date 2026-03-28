#!/usr/bin/env python3
"""
Integration Example: Enhanced Monitoring with Batch Automation

This example shows how to integrate the enhanced request monitoring system
with the existing batch_automation_integrated.py system. This demonstrates
the minimal changes needed to add enhanced monitoring capabilities.

This file serves as a reference for how to modify existing systems to
incorporate the enhanced monitoring functionality.
"""

import os
import sys
import logging
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger

# Import enhanced monitoring components
from automation.enhanced_monitoring_integration import integrate_with_batch_system
from automation.monitoring_config import create_default_monitoring_config


class EnhancedIntegratedBatchSystem:
    """
    Enhanced version of IntegratedBatchSystem with advanced monitoring.
    
    This class shows how to extend the existing IntegratedBatchSystem
    to include enhanced request monitoring capabilities.
    """
    
    def __init__(self, config_file: str = "automation_config.json"):
        """Initialize the enhanced integrated system."""
        self.logger = self._setup_logging()
        
        # Initialize existing components (simplified for example)
        self.batch_system = None  # Would be BatchAutomationSystem(config_file)
        self.capacity_manager = None  # Would be created from existing code
        self.status_monitor = None  # Would be created from existing code
        self.queue_manager = None  # Would be created from existing code
        
        # Enhanced monitoring integration
        self.enhanced_monitoring = None
        self._setup_enhanced_monitoring()
        
        self.logger.info("Enhanced Integrated Batch System initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('enhanced_integrated_batch_system', level=logging.INFO)
    
    def _setup_enhanced_monitoring(self):
        """Set up enhanced monitoring integration."""
        try:
            # Create enhanced monitoring configuration
            monitoring_config = create_default_monitoring_config()
            
            # Customize configuration for this system
            monitoring_config.adaptive_intervals.base_interval = 30  # 30 second base interval
            monitoring_config.adaptive_intervals.min_interval = 10   # Minimum 10 seconds
            monitoring_config.adaptive_intervals.max_interval = 120  # Maximum 2 minutes
            
            # Enable all features
            monitoring_config.event_system.enabled = True
            monitoring_config.notifications.enabled = True
            monitoring_config.integration.batch_system_enabled = True
            
            # Create integration (will be connected when components are available)
            self.enhanced_monitoring = integrate_with_batch_system(
                batch_system=self.batch_system,  # Will be None initially
                capacity_manager=self.capacity_manager,
                status_monitor=self.status_monitor,
                queue_manager=self.queue_manager,
                config=monitoring_config
            )
            
            # Add custom callbacks for this system
            self._setup_monitoring_callbacks()
            
            self.logger.info("✅ Enhanced monitoring integration configured")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to setup enhanced monitoring: {e}")
            self.enhanced_monitoring = None
    
    def _setup_monitoring_callbacks(self):
        """Set up custom monitoring callbacks for this system."""
        if not self.enhanced_monitoring:
            return
        
        def handle_processing_trigger(trigger_type, reason, action, urgency):
            """Handle processing triggers from enhanced monitoring."""
            self.logger.info(f"🚀 ENHANCED TRIGGER: {trigger_type}")
            self.logger.info(f"   Reason: {reason}")
            self.logger.info(f"   Suggested Action: {action}")
            self.logger.info(f"   Urgency: {urgency}")
            
            # Execute appropriate actions based on trigger type
            if trigger_type == "low_request_count":
                self._handle_low_request_count(urgency)
            elif trigger_type == "approaching_capacity":
                self._handle_approaching_capacity(urgency)
            elif trigger_type == "at_capacity":
                self._handle_at_capacity(urgency)
            elif trigger_type == "significant_drop":
                self._handle_significant_drop(urgency)
        
        def handle_status_change(current_count, previous_count, delta):
            """Handle request count status changes."""
            self.logger.info(f"📊 ENHANCED STATUS: {previous_count} → {current_count} (Δ{delta})")
            
            # Update any internal state or metrics
            self._update_internal_metrics(current_count, previous_count, delta)
        
        # Register callbacks
        self.enhanced_monitoring.add_processing_trigger_callback(handle_processing_trigger)
        self.enhanced_monitoring.add_status_change_callback(handle_status_change)
        
        self.logger.info("✅ Enhanced monitoring callbacks registered")
    
    def _handle_low_request_count(self, urgency: str):
        """Handle low request count trigger."""
        self.logger.info(f"🔥 Handling low request count (urgency: {urgency})")
        
        # Example actions:
        # 1. Trigger upload automation more aggressively
        # 2. Check for available control files
        # 3. Increase monitoring frequency
        
        if urgency == "high":
            self.logger.info("   🚨 HIGH URGENCY: Activating aggressive upload automation")
            # Would call: self._auto_upload_new_files(available_slots=5)
        else:
            self.logger.info("   📤 NORMAL: Triggering standard upload automation")
            # Would call: self._auto_upload_new_files(available_slots=2)
    
    def _handle_approaching_capacity(self, urgency: str):
        """Handle approaching capacity trigger."""
        self.logger.info(f"⚠️ Handling approaching capacity (urgency: {urgency})")
        
        # Example actions:
        # 1. Increase monitoring frequency
        # 2. Prepare capacity management
        # 3. Monitor completion rates more closely
        
        self.logger.info("   📊 Increasing monitoring frequency")
        self.logger.info("   🔍 Preparing capacity management strategies")
    
    def _handle_at_capacity(self, urgency: str):
        """Handle at capacity trigger."""
        self.logger.warning(f"🚨 Handling at capacity (urgency: {urgency})")
        
        # Example actions:
        # 1. Activate capacity management
        # 2. Process completed requests immediately
        # 3. Purge error requests
        # 4. Maximum monitoring frequency
        
        if urgency == "critical":
            self.logger.warning("   🔥 CRITICAL: Activating emergency capacity management")
            # Would call capacity management emergency procedures
        
        self.logger.info("   ⚡ Processing completed requests immediately")
        self.logger.info("   🧹 Purging error requests")
    
    def _handle_significant_drop(self, urgency: str):
        """Handle significant drop trigger."""
        self.logger.info(f"📉 Handling significant drop (urgency: {urgency})")
        
        # Example actions:
        # 1. Investigate completion cause
        # 2. Trigger upload automation to maintain capacity
        # 3. Maintain target capacity
        
        self.logger.info("   🔍 Investigating completion cause")
        self.logger.info("   🎯 Maintaining target capacity")
    
    def _update_internal_metrics(self, current_count: int, previous_count: int, delta: int):
        """Update internal metrics based on request count changes."""
        # Example: Update dashboard metrics, log to database, etc.
        self.logger.debug(f"📈 Updating internal metrics: count={current_count}, delta={delta}")
    
    def connect_existing_components(self, batch_system, capacity_manager=None, 
                                  status_monitor=None, queue_manager=None):
        """
        Connect existing components to the enhanced system.
        
        This method shows how to integrate existing components with
        the enhanced monitoring system.
        """
        try:
            # Store component references
            self.batch_system = batch_system
            self.capacity_manager = capacity_manager
            self.status_monitor = status_monitor
            self.queue_manager = queue_manager
            
            # Connect to enhanced monitoring if available
            if self.enhanced_monitoring:
                if batch_system:
                    self.enhanced_monitoring.connect_batch_system(batch_system)
                
                if capacity_manager:
                    self.enhanced_monitoring.connect_capacity_manager(capacity_manager)
                
                if status_monitor:
                    self.enhanced_monitoring.connect_status_monitor(status_monitor)
                
                if queue_manager:
                    self.enhanced_monitoring.connect_queue_manager(queue_manager)
                
                self.logger.info("✅ Existing components connected to enhanced monitoring")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect existing components: {e}")
    
    def process_all_control_files(self):
        """
        Enhanced version of process_all_control_files with monitoring integration.
        
        This method shows how the existing processing loop can be enhanced
        with the new monitoring capabilities.
        """
        self.logger.info("🚀 Starting enhanced batch processing...")
        
        try:
            # Start enhanced monitoring if available
            if self.enhanced_monitoring:
                self.enhanced_monitoring.start_integration()
                self.logger.info("✅ Enhanced monitoring started")
            
            # Existing processing logic would go here
            # This is simplified for the example
            
            self.logger.info("📋 Processing control files...")
            
            # Simulate processing loop
            import time
            processing_active = True
            cycle_count = 0
            
            while processing_active and cycle_count < 5:  # Limited for example
                cycle_count += 1
                self.logger.info(f"🔄 Processing cycle {cycle_count}")
                
                # Simulate processing work
                time.sleep(2)
                
                # The enhanced monitoring system will automatically:
                # 1. Monitor request count changes
                # 2. Detect when count drops below thresholds
                # 3. Trigger appropriate actions
                # 4. Adjust monitoring intervals based on activity
                
                # Example: Simulate request count changes
                if cycle_count == 3:
                    self.logger.info("🔄 Simulating request completion...")
                    # Enhanced monitoring will detect this change automatically
                
                self.logger.info(f"✅ Cycle {cycle_count} completed")
            
            self.logger.info("🎉 Enhanced batch processing completed")
            
        except KeyboardInterrupt:
            self.logger.info("⏹️ Processing interrupted by user")
        except Exception as e:
            self.logger.error(f"❌ Error in enhanced processing: {e}")
        finally:
            self.shutdown()
    
    def get_enhanced_status(self) -> dict:
        """Get enhanced status including monitoring information."""
        status = {
            "system_active": True,
            "enhanced_monitoring_available": self.enhanced_monitoring is not None,
            "components_connected": {
                "batch_system": self.batch_system is not None,
                "capacity_manager": self.capacity_manager is not None,
                "status_monitor": self.status_monitor is not None,
                "queue_manager": self.queue_manager is not None
            }
        }
        
        # Add enhanced monitoring status if available
        if self.enhanced_monitoring:
            try:
                monitoring_status = self.enhanced_monitoring.get_integration_status()
                status["enhanced_monitoring"] = monitoring_status
            except Exception as e:
                status["enhanced_monitoring_error"] = str(e)
        
        return status
    
    def shutdown(self):
        """Enhanced shutdown with monitoring cleanup."""
        self.logger.info("🛑 Shutting down enhanced integrated system...")
        
        # Stop enhanced monitoring
        if self.enhanced_monitoring:
            try:
                self.enhanced_monitoring.stop_integration()
                self.enhanced_monitoring.cleanup()
                self.logger.info("✅ Enhanced monitoring stopped")
            except Exception as e:
                self.logger.error(f"❌ Error stopping enhanced monitoring: {e}")
        
        # Existing shutdown logic would go here
        
        self.logger.info("✅ Enhanced integrated system shutdown complete")


def demonstrate_integration():
    """Demonstrate the enhanced integration."""
    print("=" * 80)
    print("🌟 ENHANCED BATCH AUTOMATION INTEGRATION EXAMPLE")
    print("=" * 80)
    print("This example shows how to integrate enhanced monitoring")
    print("with the existing batch automation system.")
    print("=" * 80)
    
    # Create enhanced system
    enhanced_system = EnhancedIntegratedBatchSystem()
    
    try:
        # Show initial status
        print("\n📊 Initial System Status:")
        status = enhanced_system.get_enhanced_status()
        print(f"   • Enhanced Monitoring Available: {status['enhanced_monitoring_available']}")
        print(f"   • Components Connected: {sum(status['components_connected'].values())}/4")
        
        # Simulate connecting existing components (normally these would be real)
        print("\n🔗 Connecting existing components...")
        
        # In a real implementation, these would be actual component instances
        mock_batch_system = type('MockBatch', (), {'_get_current_request_count': lambda: 7})()
        mock_capacity_manager = type('MockCapacity', (), {})()
        
        enhanced_system.connect_existing_components(
            batch_system=mock_batch_system,
            capacity_manager=mock_capacity_manager
        )
        
        print("✅ Components connected")
        
        # Show updated status
        status = enhanced_system.get_enhanced_status()
        print(f"   • Components Now Connected: {sum(status['components_connected'].values())}/4")
        
        # Run enhanced processing
        print("\n🚀 Starting enhanced processing demonstration...")
        enhanced_system.process_all_control_files()
        
        print("\n✅ Integration demonstration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Integration demonstration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        enhanced_system.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced Monitoring Integration Example')
    parser.add_argument('--demo', action='store_true',
                       help='Run integration demonstration')
    
    args = parser.parse_args()
    
    if args.demo:
        demonstrate_integration()
    else:
        parser.print_help()
        print("\n" + "="*60)
        print("INTEGRATION EXAMPLE")
        print("="*60)
        print("This file shows how to integrate enhanced monitoring")
        print("with existing batch automation systems.")
        print("")
        print("# Run demonstration:")
        print("python automation/integration_example.py --demo")
        print("")
        print("Key integration points:")
        print("1. Create enhanced monitoring configuration")
        print("2. Set up integration with existing components")
        print("3. Register custom callbacks for triggers")
        print("4. Start enhanced monitoring alongside existing processing")
        print("5. Handle monitoring events and triggers")
        print("="*60)