#!/usr/bin/env python3
"""
Event System for RDA Automation System

This module provides a comprehensive event-driven architecture for the RDA automation
system, enabling components to communicate through events and callbacks. It supports
request count monitoring, status changes, and dynamic processing triggers.

Key Features:
- Event-driven architecture with type-safe event dispatching
- Request count change events and callbacks
- Flexible event filtering and routing
- Thread-safe event handling
- Event history and analytics
- Integration with existing monitoring components
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict, deque

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class EventType(Enum):
    """Enumeration for event types."""
    REQUEST_COUNT_CHANGED = "request_count_changed"
    REQUEST_STATUS_CHANGED = "request_status_changed"
    CAPACITY_THRESHOLD_REACHED = "capacity_threshold_reached"
    PROCESSING_TRIGGER = "processing_trigger"
    SYSTEM_STATE_CHANGED = "system_state_changed"
    ERROR_DETECTED = "error_detected"
    MONITORING_CYCLE_COMPLETED = "monitoring_cycle_completed"


class EventPriority(Enum):
    """Enumeration for event priorities."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5


@dataclass
class EventContext:
    """Context information for events."""
    source_component: str
    timestamp: str
    event_id: str
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseEvent(ABC):
    """Base class for all events."""
    event_type: EventType
    priority: EventPriority
    context: EventContext
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "priority": self.priority.value,
            "context": asdict(self.context),
            "data": self.data,
            "timestamp": self.context.timestamp
        }


@dataclass
class RequestCountEvent(BaseEvent):
    """Event for request count changes."""
    previous_count: int = 0
    current_count: int = 0
    change_delta: int = 0
    threshold_crossed: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.REQUEST_COUNT_CHANGED
        self.data.update({
            "previous_count": self.previous_count,
            "current_count": self.current_count,
            "change_delta": self.change_delta,
            "threshold_crossed": self.threshold_crossed
        })


@dataclass
class RequestStatusEvent(BaseEvent):
    """Event for individual request status changes."""
    request_id: str = ""
    previous_status: str = ""
    current_status: str = ""
    control_file: Optional[str] = None
    
    def __post_init__(self):
        self.event_type = EventType.REQUEST_STATUS_CHANGED
        self.data.update({
            "request_id": self.request_id,
            "previous_status": self.previous_status,
            "current_status": self.current_status,
            "control_file": self.control_file
        })


@dataclass
class CapacityThresholdEvent(BaseEvent):
    """Event for capacity threshold crossings."""
    threshold_name: str = ""
    threshold_value: int = 0
    current_count: int = 0
    direction: str = ""  # "exceeded" or "below"
    
    def __post_init__(self):
        self.event_type = EventType.CAPACITY_THRESHOLD_REACHED
        self.data.update({
            "threshold_name": self.threshold_name,
            "threshold_value": self.threshold_value,
            "current_count": self.current_count,
            "direction": self.direction
        })


@dataclass
class ProcessingTriggerEvent(BaseEvent):
    """Event for processing triggers."""
    trigger_type: str = ""
    trigger_reason: str = ""
    suggested_action: str = ""
    urgency_level: str = ""
    
    def __post_init__(self):
        self.event_type = EventType.PROCESSING_TRIGGER
        self.data.update({
            "trigger_type": self.trigger_type,
            "trigger_reason": self.trigger_reason,
            "suggested_action": self.suggested_action,
            "urgency_level": self.urgency_level
        })


class EventFilter:
    """Filter for events based on criteria."""
    
    def __init__(self,
                 event_types: Optional[Set[EventType]] = None,
                 priorities: Optional[Set[EventPriority]] = None,
                 source_components: Optional[Set[str]] = None,
                 custom_filter: Optional[Callable[[BaseEvent], bool]] = None):
        """
        Initialize event filter.
        
        Args:
            event_types: Set of event types to include
            priorities: Set of priorities to include
            source_components: Set of source components to include
            custom_filter: Custom filter function
        """
        self.event_types = event_types
        self.priorities = priorities
        self.source_components = source_components
        self.custom_filter = custom_filter
    
    def matches(self, event: BaseEvent) -> bool:
        """Check if event matches filter criteria."""
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        if self.priorities and event.priority not in self.priorities:
            return False
        
        if self.source_components and event.context.source_component not in self.source_components:
            return False
        
        if self.custom_filter and not self.custom_filter(event):
            return False
        
        return True


class EventSubscription:
    """Subscription for event callbacks."""
    
    def __init__(self,
                 callback: Callable[[BaseEvent], None],
                 event_filter: Optional[EventFilter] = None,
                 subscription_id: Optional[str] = None):
        """
        Initialize event subscription.
        
        Args:
            callback: Function to call when event matches
            event_filter: Filter for events
            subscription_id: Unique identifier for subscription
        """
        self.callback = callback
        self.event_filter = event_filter or EventFilter()
        self.subscription_id = subscription_id or f"sub_{int(time.time() * 1000)}"
        self.created_at = datetime.now().isoformat()
        self.call_count = 0
        self.last_called = None
        self.active = True


class EventDispatcher:
    """
    Central event dispatcher for the RDA automation system.
    
    Provides thread-safe event dispatching, subscription management,
    and event history tracking.
    """
    
    def __init__(self, max_history_size: int = 1000):
        """
        Initialize the event dispatcher.
        
        Args:
            max_history_size: Maximum number of events to keep in history
        """
        self.logger = self._setup_logging()
        self.max_history_size = max_history_size
        
        # Event storage
        self.event_history: deque = deque(maxlen=max_history_size)
        self.subscriptions: Dict[str, EventSubscription] = {}
        
        # Event routing
        self.event_routes: Dict[EventType, List[str]] = defaultdict(list)
        
        # Statistics
        self.stats = {
            "total_events_dispatched": 0,
            "events_by_type": defaultdict(int),
            "events_by_priority": defaultdict(int),
            "subscription_calls": defaultdict(int),
            "last_dispatch_time": None,
            "dispatch_errors": 0
        }
        
        # Threading
        self.dispatch_lock = threading.RLock()
        self.async_dispatch_enabled = True
        self.dispatch_queue: deque = deque()
        self.dispatch_thread: Optional[threading.Thread] = None
        self.dispatch_active = False
        
        self.logger.info("EventDispatcher initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the event dispatcher."""
        logger = logging.getLogger('rda_automation.event_dispatcher')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def subscribe(self,
                  callback: Callable[[BaseEvent], None],
                  event_filter: Optional[EventFilter] = None,
                  subscription_id: Optional[str] = None) -> str:
        """
        Subscribe to events with optional filtering.
        
        Args:
            callback: Function to call when matching events occur
            event_filter: Filter criteria for events
            subscription_id: Optional custom subscription ID
            
        Returns:
            Subscription ID
        """
        try:
            subscription = EventSubscription(callback, event_filter, subscription_id)
            
            with self.dispatch_lock:
                self.subscriptions[subscription.subscription_id] = subscription
                
                # Add to event routes for efficient dispatching
                if event_filter and event_filter.event_types:
                    for event_type in event_filter.event_types:
                        self.event_routes[event_type].append(subscription.subscription_id)
                else:
                    # Subscribe to all event types
                    for event_type in EventType:
                        self.event_routes[event_type].append(subscription.subscription_id)
            
            self.logger.info(f"✅ Event subscription created: {subscription.subscription_id}")
            return subscription.subscription_id
            
        except Exception as e:
            self.logger.error(f"❌ Failed to create subscription: {e}")
            raise
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription_id: ID of subscription to remove
            
        Returns:
            True if unsubscribed successfully, False otherwise
        """
        try:
            with self.dispatch_lock:
                if subscription_id not in self.subscriptions:
                    self.logger.warning(f"⚠️ Subscription not found: {subscription_id}")
                    return False
                
                # Remove from subscriptions
                del self.subscriptions[subscription_id]
                
                # Remove from event routes
                for event_type, sub_ids in self.event_routes.items():
                    if subscription_id in sub_ids:
                        sub_ids.remove(subscription_id)
            
            self.logger.info(f"✅ Unsubscribed: {subscription_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe {subscription_id}: {e}")
            return False
    
    def dispatch_event(self, event: BaseEvent, async_dispatch: bool = True) -> bool:
        """
        Dispatch an event to all matching subscribers.
        
        Args:
            event: Event to dispatch
            async_dispatch: Whether to dispatch asynchronously
            
        Returns:
            True if dispatch was successful, False otherwise
        """
        try:
            # Add to history
            with self.dispatch_lock:
                self.event_history.append(event)
                self.stats["total_events_dispatched"] += 1
                self.stats["events_by_type"][event.event_type.value] += 1
                self.stats["events_by_priority"][event.priority.value] += 1
                self.stats["last_dispatch_time"] = datetime.now().isoformat()
            
            if async_dispatch and self.async_dispatch_enabled:
                # Add to dispatch queue for async processing
                self.dispatch_queue.append(event)
                self._ensure_dispatch_thread_running()
            else:
                # Synchronous dispatch
                self._dispatch_event_sync(event)
            
            self.logger.debug(f"📡 Event dispatched: {event.event_type.value} from {event.context.source_component}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to dispatch event: {e}")
            with self.dispatch_lock:
                self.stats["dispatch_errors"] += 1
            return False
    
    def _dispatch_event_sync(self, event: BaseEvent):
        """Synchronously dispatch event to subscribers."""
        try:
            # Get relevant subscriptions
            relevant_subscriptions = []
            
            with self.dispatch_lock:
                # Get subscriptions for this event type
                subscription_ids = self.event_routes.get(event.event_type, [])
                
                for sub_id in subscription_ids:
                    if sub_id in self.subscriptions:
                        subscription = self.subscriptions[sub_id]
                        if subscription.active and subscription.event_filter.matches(event):
                            relevant_subscriptions.append(subscription)
            
            # Call subscribers
            for subscription in relevant_subscriptions:
                try:
                    subscription.callback(event)
                    
                    # Update subscription stats
                    with self.dispatch_lock:
                        subscription.call_count += 1
                        subscription.last_called = datetime.now().isoformat()
                        self.stats["subscription_calls"][subscription.subscription_id] += 1
                    
                except Exception as e:
                    self.logger.error(f"❌ Error in event callback {subscription.subscription_id}: {e}")
                    with self.dispatch_lock:
                        self.stats["dispatch_errors"] += 1
            
        except Exception as e:
            self.logger.error(f"❌ Error in synchronous event dispatch: {e}")
    
    def _ensure_dispatch_thread_running(self):
        """Ensure the async dispatch thread is running."""
        if not self.dispatch_active:
            self.dispatch_active = True
            self.dispatch_thread = threading.Thread(target=self._async_dispatch_loop, daemon=True)
            self.dispatch_thread.start()
            self.logger.debug("🚀 Async dispatch thread started")
    
    def _async_dispatch_loop(self):
        """Async dispatch loop for processing queued events."""
        while self.dispatch_active:
            try:
                if self.dispatch_queue:
                    event = self.dispatch_queue.popleft()
                    self._dispatch_event_sync(event)
                else:
                    time.sleep(0.01)  # Small delay when queue is empty
                    
            except IndexError:
                # Queue is empty
                time.sleep(0.01)
            except Exception as e:
                self.logger.error(f"❌ Error in async dispatch loop: {e}")
                time.sleep(0.1)
    
    def create_request_count_event(self,
                                 source_component: str,
                                 previous_count: int,
                                 current_count: int,
                                 threshold_crossed: Optional[str] = None,
                                 priority: EventPriority = EventPriority.NORMAL,
                                 correlation_id: Optional[str] = None) -> RequestCountEvent:
        """
        Create a request count change event.
        
        Args:
            source_component: Component that detected the change
            previous_count: Previous request count
            current_count: Current request count
            threshold_crossed: Name of threshold that was crossed
            priority: Event priority
            correlation_id: Optional correlation ID
            
        Returns:
            RequestCountEvent instance
        """
        context = EventContext(
            source_component=source_component,
            timestamp=datetime.now().isoformat(),
            event_id=f"req_count_{int(time.time() * 1000)}",
            correlation_id=correlation_id
        )
        
        return RequestCountEvent(
            event_type=EventType.REQUEST_COUNT_CHANGED,
            priority=priority,
            context=context,
            previous_count=previous_count,
            current_count=current_count,
            change_delta=current_count - previous_count,
            threshold_crossed=threshold_crossed
        )
    
    def create_processing_trigger_event(self,
                                      source_component: str,
                                      trigger_type: str,
                                      trigger_reason: str,
                                      suggested_action: str,
                                      urgency_level: str = "normal",
                                      priority: EventPriority = EventPriority.HIGH,
                                      correlation_id: Optional[str] = None) -> ProcessingTriggerEvent:
        """
        Create a processing trigger event.
        
        Args:
            source_component: Component that triggered the event
            trigger_type: Type of trigger
            trigger_reason: Reason for the trigger
            suggested_action: Suggested action to take
            urgency_level: Urgency level
            priority: Event priority
            correlation_id: Optional correlation ID
            
        Returns:
            ProcessingTriggerEvent instance
        """
        context = EventContext(
            source_component=source_component,
            timestamp=datetime.now().isoformat(),
            event_id=f"trigger_{int(time.time() * 1000)}",
            correlation_id=correlation_id
        )
        
        return ProcessingTriggerEvent(
            event_type=EventType.PROCESSING_TRIGGER,
            priority=priority,
            context=context,
            trigger_type=trigger_type,
            trigger_reason=trigger_reason,
            suggested_action=suggested_action,
            urgency_level=urgency_level
        )
    
    def get_event_history(self, 
                         limit: Optional[int] = None,
                         event_filter: Optional[EventFilter] = None) -> List[Dict[str, Any]]:
        """
        Get event history with optional filtering.
        
        Args:
            limit: Maximum number of events to return
            event_filter: Filter criteria
            
        Returns:
            List of event dictionaries
        """
        try:
            with self.dispatch_lock:
                events = list(self.event_history)
            
            # Apply filter if provided
            if event_filter:
                events = [event for event in events if event_filter.matches(event)]
            
            # Apply limit
            if limit:
                events = events[-limit:]
            
            return [event.to_dict() for event in events]
            
        except Exception as e:
            self.logger.error(f"❌ Failed to get event history: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get event dispatcher statistics.
        
        Returns:
            Statistics dictionary
        """
        with self.dispatch_lock:
            return {
                "dispatcher_stats": dict(self.stats),
                "active_subscriptions": len(self.subscriptions),
                "event_history_size": len(self.event_history),
                "dispatch_queue_size": len(self.dispatch_queue),
                "async_dispatch_active": self.dispatch_active,
                "subscription_details": {
                    sub_id: {
                        "created_at": sub.created_at,
                        "call_count": sub.call_count,
                        "last_called": sub.last_called,
                        "active": sub.active
                    }
                    for sub_id, sub in self.subscriptions.items()
                },
                "generated_at": datetime.now().isoformat()
            }
    
    def stop_async_dispatch(self):
        """Stop the async dispatch thread."""
        self.dispatch_active = False
        
        if self.dispatch_thread and self.dispatch_thread.is_alive():
            self.dispatch_thread.join(timeout=5)
        
        self.logger.info("🛑 Async dispatch stopped")
    
    def cleanup(self):
        """Clean up the event dispatcher."""
        self.logger.info("🧹 Cleaning up EventDispatcher...")
        
        # Stop async dispatch
        self.stop_async_dispatch()
        
        # Clear all data
        with self.dispatch_lock:
            self.subscriptions.clear()
            self.event_routes.clear()
            self.event_history.clear()
            self.dispatch_queue.clear()
            self.stats.clear()
        
        self.logger.info("✅ EventDispatcher cleanup completed")


def create_event_dispatcher(max_history_size: int = 1000) -> EventDispatcher:
    """
    Factory function to create an EventDispatcher.
    
    Args:
        max_history_size: Maximum number of events to keep in history
        
    Returns:
        EventDispatcher instance
    """
    return EventDispatcher(max_history_size=max_history_size)


# Convenience functions for common event patterns
def create_request_count_filter(source_components: Optional[Set[str]] = None) -> EventFilter:
    """Create a filter for request count events."""
    return EventFilter(
        event_types={EventType.REQUEST_COUNT_CHANGED},
        source_components=source_components
    )


def create_high_priority_filter() -> EventFilter:
    """Create a filter for high priority events."""
    return EventFilter(
        priorities={EventPriority.HIGH, EventPriority.CRITICAL, EventPriority.EMERGENCY}
    )


def create_processing_trigger_filter() -> EventFilter:
    """Create a filter for processing trigger events."""
    return EventFilter(
        event_types={EventType.PROCESSING_TRIGGER}
    )


if __name__ == "__main__":
    # Example usage and testing
    import time
    
    # Create event dispatcher
    dispatcher = create_event_dispatcher()
    
    # Create a simple callback
    def request_count_callback(event: BaseEvent):
        if isinstance(event, RequestCountEvent):
            print(f"📊 Request count changed: {event.previous_count} -> {event.current_count}")
    
    # Subscribe to request count events
    sub_id = dispatcher.subscribe(
        callback=request_count_callback,
        event_filter=create_request_count_filter()
    )
    
    # Create and dispatch a test event
    event = dispatcher.create_request_count_event(
        source_component="test_monitor",
        previous_count=5,
        current_count=7,
        threshold_crossed="approaching_limit"
    )
    
    dispatcher.dispatch_event(event, async_dispatch=False)
    
    # Get statistics
    stats = dispatcher.get_statistics()
    print(f"📈 Dispatcher stats: {json.dumps(stats, indent=2)}")
    
    # Cleanup
    dispatcher.cleanup()