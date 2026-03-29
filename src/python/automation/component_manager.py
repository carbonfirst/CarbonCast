#!/usr/bin/env python3
"""
Component Manager for RDA Automation System

This module provides detailed component lifecycle management capabilities,
including initialization, monitoring, restart, and cleanup operations.
It works in conjunction with the SystemIntegrator to provide granular
control over individual components.

Key Features:
- Component lifecycle management (start, stop, restart)
- Dependency resolution and validation
- Health monitoring and diagnostics
- Resource management and cleanup
- Component state tracking and persistence
- Performance metrics collection
- Error handling and recovery
"""

import os
import sys
import json
import time
import logging
import threading
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_utils import get_logger


class ComponentState(Enum):
    """Enumeration for component states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"
    MAINTENANCE = "maintenance"


class ComponentPriority(Enum):
    """Enumeration for component priorities."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class ComponentMetrics:
    """Component performance metrics."""
    start_time: Optional[float] = None
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_response_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    last_health_check: Optional[str] = None
    uptime_seconds: float = 0.0
    restart_count: int = 0
    error_count: int = 0


@dataclass
class ComponentDefinition:
    """Definition of a component for management."""
    name: str
    factory_function: Callable
    dependencies: List[str]
    priority: ComponentPriority
    config_params: Dict[str, Any]
    health_check_method: Optional[str] = None
    cleanup_method: Optional[str] = None
    restart_on_failure: bool = True
    max_restart_attempts: int = 3
    restart_delay: float = 5.0
    timeout_seconds: int = 30


@dataclass
class ManagedComponent:
    """A managed component with full lifecycle tracking."""
    definition: ComponentDefinition
    instance: Optional[Any] = None
    state: ComponentState = ComponentState.UNINITIALIZED
    metrics: ComponentMetrics = None
    last_error: Optional[str] = None
    initialization_future: Optional[Future] = None
    state_history: List[Tuple[str, ComponentState]] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.metrics is None:
            self.metrics = ComponentMetrics()
        if self.state_history is None:
            self.state_history = []


class ComponentManager:
    """
    Advanced component lifecycle manager.
    
    Provides detailed management of component lifecycle, including dependency
    resolution, health monitoring, performance tracking, and error recovery.
    """
    
    def __init__(self, max_workers: int = 10, enable_metrics: bool = True):
        """
        Initialize the Component Manager.
        
        Args:
            max_workers: Maximum number of worker threads
            enable_metrics: Whether to collect performance metrics
        """
        self.logger = self._setup_logging()
        self.max_workers = max_workers
        self.enable_metrics = enable_metrics
        
        # Component management
        self.components: Dict[str, ManagedComponent] = {}
        self.component_definitions: Dict[str, ComponentDefinition] = {}
        
        # Threading and execution
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.manager_lock = threading.RLock()
        
        # State tracking
        self.initialization_order: List[str] = []
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Monitoring
        self.health_check_interval = 60  # seconds
        self.metrics_collection_interval = 30  # seconds
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        self.logger.info("Component Manager initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('rda_automation.component_manager', level=logging.INFO)
    
    def register_component(self, definition: ComponentDefinition) -> bool:
        """
        Register a component definition for management.
        
        Args:
            definition: Component definition
            
        Returns:
            True if registration was successful, False otherwise
        """
        try:
            with self.manager_lock:
                if definition.name in self.component_definitions:
                    self.logger.warning(f"⚠️ Component {definition.name} already registered, updating...")
                
                self.component_definitions[definition.name] = definition
                
                # Create managed component if not exists
                if definition.name not in self.components:
                    self.components[definition.name] = ManagedComponent(definition=definition)
                else:
                    # Update existing component's definition
                    self.components[definition.name].definition = definition
                
                # Update dependency graph
                self.dependency_graph[definition.name] = definition.dependencies
                
                self.logger.info(f"✅ Component {definition.name} registered successfully")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Failed to register component {definition.name}: {e}")
            return False
    
    def register_components(self, definitions: List[ComponentDefinition]) -> int:
        """
        Register multiple component definitions.
        
        Args:
            definitions: List of component definitions
            
        Returns:
            Number of successfully registered components
        """
        successful_count = 0
        
        for definition in definitions:
            if self.register_component(definition):
                successful_count += 1
        
        # Recalculate initialization order
        self._calculate_initialization_order()
        
        self.logger.info(f"📋 Registered {successful_count}/{len(definitions)} components")
        return successful_count
    
    def _calculate_initialization_order(self) -> List[str]:
        """Calculate component initialization order based on dependencies."""
        try:
            # Topological sort
            order = []
            visited = set()
            temp_visited = set()
            
            def visit(component_name: str):
                if component_name in temp_visited:
                    raise ValueError(f"Circular dependency detected involving {component_name}")
                if component_name in visited:
                    return
                
                temp_visited.add(component_name)
                
                # Visit dependencies first
                dependencies = self.dependency_graph.get(component_name, [])
                for dep in dependencies:
                    if dep in self.dependency_graph:  # Only visit registered components
                        visit(dep)
                
                temp_visited.remove(component_name)
                visited.add(component_name)
                order.append(component_name)
            
            # Visit all components
            for component_name in self.dependency_graph.keys():
                if component_name not in visited:
                    visit(component_name)
            
            self.initialization_order = order
            self.logger.debug(f"🔄 Initialization order calculated: {order}")
            return order
            
        except Exception as e:
            self.logger.error(f"❌ Failed to calculate initialization order: {e}")
            return list(self.dependency_graph.keys())
    
    def initialize_component(self, component_name: str, timeout: Optional[int] = None) -> bool:
        """
        Initialize a specific component.
        
        Args:
            component_name: Name of the component to initialize
            timeout: Initialization timeout in seconds
            
        Returns:
            True if initialization was successful, False otherwise
        """
        if component_name not in self.components:
            self.logger.error(f"❌ Component {component_name} not registered")
            return False
        
        component = self.components[component_name]
        definition = component.definition
        
        try:
            with self.manager_lock:
                if component.state in [ComponentState.INITIALIZED, ComponentState.RUNNING]:
                    self.logger.info(f"ℹ️ Component {component_name} already initialized")
                    return True
                
                self._transition_component_state(component, ComponentState.INITIALIZING)
            
            self.logger.info(f"🔧 Initializing component: {component_name}")
            
            # Check dependencies
            for dep_name in definition.dependencies:
                if dep_name not in self.components:
                    raise Exception(f"Dependency {dep_name} not registered")
                
                dep_component = self.components[dep_name]
                if dep_component.state not in [ComponentState.INITIALIZED, ComponentState.RUNNING]:
                    raise Exception(f"Dependency {dep_name} not initialized")
            
            # Initialize component using factory function
            start_time = time.time()
            
            try:
                component_instance = definition.factory_function(**definition.config_params)
                
                # Perform additional initialization if needed
                if hasattr(component_instance, 'initialize'):
                    component_instance.initialize()
                
                with self.manager_lock:
                    component.instance = component_instance
                    component.metrics.start_time = start_time
                    self._transition_component_state(component, ComponentState.INITIALIZED)
                
                initialization_time = time.time() - start_time
                self.logger.info(f"✅ Component {component_name} initialized in {initialization_time:.2f}s")
                
                return True
                
            except Exception as init_error:
                with self.manager_lock:
                    component.last_error = str(init_error)
                    component.metrics.error_count += 1
                    self._transition_component_state(component, ComponentState.ERROR)
                
                raise init_error
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize component {component_name}: {e}")
            return False
    
    def start_component(self, component_name: str) -> bool:
        """
        Start a component (move from initialized to running state).
        
        Args:
            component_name: Name of the component to start
            
        Returns:
            True if start was successful, False otherwise
        """
        if component_name not in self.components:
            self.logger.error(f"❌ Component {component_name} not registered")
            return False
        
        component = self.components[component_name]
        
        try:
            with self.manager_lock:
                if component.state == ComponentState.RUNNING:
                    self.logger.info(f"ℹ️ Component {component_name} already running")
                    return True
                
                if component.state != ComponentState.INITIALIZED:
                    self.logger.error(f"❌ Component {component_name} not initialized (state: {component.state.value})")
                    return False
                
                self._transition_component_state(component, ComponentState.STARTING)
            
            self.logger.info(f"▶️ Starting component: {component_name}")
            
            # Start component if it has a start method
            if component.instance and hasattr(component.instance, 'start'):
                component.instance.start()
            
            with self.manager_lock:
                self._transition_component_state(component, ComponentState.RUNNING)
            
            self.logger.info(f"✅ Component {component_name} started successfully")
            return True
            
        except Exception as e:
            with self.manager_lock:
                component.last_error = str(e)
                component.metrics.error_count += 1
                self._transition_component_state(component, ComponentState.ERROR)
            
            self.logger.error(f"❌ Failed to start component {component_name}: {e}")
            return False
    
    def stop_component(self, component_name: str, timeout: int = 30) -> bool:
        """
        Stop a component gracefully.
        
        Args:
            component_name: Name of the component to stop
            timeout: Stop timeout in seconds
            
        Returns:
            True if stop was successful, False otherwise
        """
        if component_name not in self.components:
            self.logger.error(f"❌ Component {component_name} not registered")
            return False
        
        component = self.components[component_name]
        
        try:
            with self.manager_lock:
                if component.state in [ComponentState.STOPPED, ComponentState.UNINITIALIZED]:
                    self.logger.info(f"ℹ️ Component {component_name} already stopped")
                    return True
                
                self._transition_component_state(component, ComponentState.STOPPING)
            
            self.logger.info(f"⏹️ Stopping component: {component_name}")
            
            # Stop component using appropriate method
            if component.instance:
                cleanup_method = component.definition.cleanup_method
                
                if cleanup_method and hasattr(component.instance, cleanup_method):
                    getattr(component.instance, cleanup_method)()
                elif hasattr(component.instance, 'stop'):
                    component.instance.stop()
                elif hasattr(component.instance, 'cleanup'):
                    component.instance.cleanup()
                elif hasattr(component.instance, 'close'):
                    component.instance.close()
            
            with self.manager_lock:
                component.instance = None
                self._transition_component_state(component, ComponentState.STOPPED)
            
            self.logger.info(f"✅ Component {component_name} stopped successfully")
            return True
            
        except Exception as e:
            with self.manager_lock:
                component.last_error = str(e)
                component.metrics.error_count += 1
                self._transition_component_state(component, ComponentState.ERROR)
            
            self.logger.error(f"❌ Failed to stop component {component_name}: {e}")
            return False
    
    def restart_component(self, component_name: str) -> bool:
        """
        Restart a component (stop then start).
        
        Args:
            component_name: Name of the component to restart
            
        Returns:
            True if restart was successful, False otherwise
        """
        self.logger.info(f"🔄 Restarting component: {component_name}")
        
        # Stop the component
        if not self.stop_component(component_name):
            return False
        
        # Wait for restart delay
        if component_name in self.components:
            delay = self.components[component_name].definition.restart_delay
            time.sleep(delay)
        
        # Initialize and start the component
        if not self.initialize_component(component_name):
            return False
        
        if not self.start_component(component_name):
            return False
        
        # Update restart count
        with self.manager_lock:
            self.components[component_name].metrics.restart_count += 1
        
        self.logger.info(f"✅ Component {component_name} restarted successfully")
        return True
    
    def initialize_all_components(self) -> Tuple[int, int]:
        """
        Initialize all registered components in dependency order.
        
        Returns:
            Tuple of (successful_count, total_count)
        """
        self.logger.info("🚀 Initializing all components...")
        
        if not self.initialization_order:
            self._calculate_initialization_order()
        
        successful_count = 0
        total_count = len(self.initialization_order)
        
        for component_name in self.initialization_order:
            if self.initialize_component(component_name):
                successful_count += 1
            else:
                # Check if this is a critical component
                component = self.components[component_name]
                if component.definition.priority == ComponentPriority.CRITICAL:
                    self.logger.error(f"💥 Critical component {component_name} failed - aborting initialization")
                    break
        
        self.logger.info(f"📊 Component initialization completed: {successful_count}/{total_count} successful")
        return successful_count, total_count
    
    def start_all_components(self) -> Tuple[int, int]:
        """
        Start all initialized components.
        
        Returns:
            Tuple of (successful_count, total_count)
        """
        self.logger.info("▶️ Starting all components...")
        
        successful_count = 0
        initialized_components = [
            name for name, comp in self.components.items()
            if comp.state == ComponentState.INITIALIZED
        ]
        
        for component_name in initialized_components:
            if self.start_component(component_name):
                successful_count += 1
        
        total_count = len(initialized_components)
        self.logger.info(f"📊 Component startup completed: {successful_count}/{total_count} successful")
        return successful_count, total_count
    
    def stop_all_components(self) -> Tuple[int, int]:
        """
        Stop all running components in reverse dependency order.
        
        Returns:
            Tuple of (successful_count, total_count)
        """
        self.logger.info("⏹️ Stopping all components...")
        
        # Stop in reverse order
        stop_order = list(reversed(self.initialization_order))
        successful_count = 0
        running_components = [
            name for name in stop_order
            if name in self.components and self.components[name].state == ComponentState.RUNNING
        ]
        
        for component_name in running_components:
            if self.stop_component(component_name):
                successful_count += 1
        
        total_count = len(running_components)
        self.logger.info(f"📊 Component shutdown completed: {successful_count}/{total_count} successful")
        return successful_count, total_count
    
    def _transition_component_state(self, component: ManagedComponent, new_state: ComponentState):
        """Transition a component to a new state."""
        old_state = component.state
        component.state = new_state
        
        # Record state transition
        timestamp = datetime.now().isoformat()
        component.state_history.append((timestamp, new_state))
        
        # Keep only last 50 state transitions
        if len(component.state_history) > 50:
            component.state_history = component.state_history[-50:]
        
        self.logger.debug(f"🔄 {component.definition.name}: {old_state.value} -> {new_state.value}")
    
    def get_component_status(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            Component status dictionary or None if not found
        """
        if component_name not in self.components:
            return None
        
        component = self.components[component_name]
        
        # Calculate uptime
        uptime = 0.0
        if component.metrics.start_time:
            uptime = time.time() - component.metrics.start_time
            component.metrics.uptime_seconds = uptime
        
        return {
            'name': component.definition.name,
            'state': component.state.value,
            'priority': component.definition.priority.value,
            'dependencies': component.definition.dependencies,
            'last_error': component.last_error,
            'metrics': asdict(component.metrics),
            'state_history': component.state_history[-10:],  # Last 10 transitions
            'has_instance': component.instance is not None,
            'restart_on_failure': component.definition.restart_on_failure,
            'max_restart_attempts': component.definition.max_restart_attempts
        }
    
    def get_all_component_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all components.
        
        Returns:
            Dictionary mapping component names to their status
        """
        return {
            name: self.get_component_status(name)
            for name in self.components.keys()
        }
    
    def perform_health_check(self, component_name: str) -> bool:
        """
        Perform health check on a specific component.
        
        Args:
            component_name: Name of the component
            
        Returns:
            True if component is healthy, False otherwise
        """
        if component_name not in self.components:
            return False
        
        component = self.components[component_name]
        
        if component.state != ComponentState.RUNNING or not component.instance:
            return False
        
        try:
            # Use custom health check method if specified
            health_check_method = component.definition.health_check_method
            if health_check_method and hasattr(component.instance, health_check_method):
                result = getattr(component.instance, health_check_method)()
                is_healthy = bool(result)
            else:
                # Default health check - instance exists and no recent errors
                is_healthy = (
                    component.instance is not None and
                    component.state == ComponentState.RUNNING
                )
            
            # Update health check timestamp
            component.metrics.last_health_check = datetime.now().isoformat()
            
            return is_healthy
            
        except Exception as e:
            self.logger.warning(f"⚠️ Health check failed for {component_name}: {e}")
            return False
    
    def start_monitoring(self):
        """Start background monitoring of all components."""
        if self.monitoring_active:
            self.logger.info("ℹ️ Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        self.logger.info("👁️ Component monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10)
        
        self.logger.info("👁️ Component monitoring stopped")
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        last_health_check = 0
        last_metrics_collection = 0
        
        while self.monitoring_active:
            try:
                current_time = time.time()
                
                # Perform health checks
                if current_time - last_health_check >= self.health_check_interval:
                    self._perform_all_health_checks()
                    last_health_check = current_time
                
                # Collect metrics
                if self.enable_metrics and current_time - last_metrics_collection >= self.metrics_collection_interval:
                    self._collect_all_metrics()
                    last_metrics_collection = current_time
                
                time.sleep(min(self.health_check_interval, self.metrics_collection_interval) / 4)
                
            except Exception as e:
                self.logger.error(f"❌ Error in monitoring loop: {e}")
                time.sleep(10)
    
    def _perform_all_health_checks(self):
        """Perform health checks on all running components."""
        running_components = [
            name for name, comp in self.components.items()
            if comp.state == ComponentState.RUNNING
        ]
        
        for component_name in running_components:
            try:
                is_healthy = self.perform_health_check(component_name)
                
                if not is_healthy:
                    component = self.components[component_name]
                    self.logger.warning(f"⚠️ Health check failed for {component_name}")
                    
                    # Auto-restart if configured
                    if component.definition.restart_on_failure:
                        restart_count = component.metrics.restart_count
                        max_attempts = component.definition.max_restart_attempts
                        
                        if restart_count < max_attempts:
                            self.logger.info(f"🔄 Auto-restarting {component_name} (attempt {restart_count + 1}/{max_attempts})")
                            self.restart_component(component_name)
                        else:
                            self.logger.error(f"💥 Component {component_name} exceeded max restart attempts")
                            with self.manager_lock:
                                self._transition_component_state(component, ComponentState.ERROR)
                
            except Exception as e:
                self.logger.error(f"❌ Error checking health of {component_name}: {e}")
    
    def _collect_all_metrics(self):
        """Collect performance metrics for all components."""
        for component_name, component in self.components.items():
            try:
                if component.instance and hasattr(component.instance, 'get_metrics'):
                    metrics = component.instance.get_metrics()
                    if isinstance(metrics, dict):
                        # Update component metrics with instance-specific data
                        for key, value in metrics.items():
                            if hasattr(component.metrics, key):
                                setattr(component.metrics, key, value)
                
            except Exception as e:
                self.logger.debug(f"Could not collect metrics for {component_name}: {e}")
    
    def cleanup(self):
        """Clean up the component manager."""
        self.logger.info("🧹 Cleaning up Component Manager...")
        
        # Stop monitoring
        self.stop_monitoring()
        
        # Stop all components
        self.stop_all_components()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.logger.info("✅ Component Manager cleanup completed")


def create_component_manager(max_workers: int = 10, enable_metrics: bool = True) -> ComponentManager:
    """
    Create and return a ComponentManager instance.
    
    Args:
        max_workers: Maximum number of worker threads
        enable_metrics: Whether to collect performance metrics
        
    Returns:
        ComponentManager instance
    """
    return ComponentManager(max_workers=max_workers, enable_metrics=enable_metrics)


if __name__ == "__main__":
    # Example usage
    manager = create_component_manager()
    
    # Example component definition
    def example_factory(**kwargs):
        class ExampleComponent:
            def initialize(self):
                print("Example component initialized")
            
            def start(self):
                print("Example component started")
            
            def stop(self):
                print("Example component stopped")
            
            def health_check(self):
                return True
        
        return ExampleComponent()
    
    # Register example component
    definition = ComponentDefinition(
        name="example_component",
        factory_function=example_factory,
        dependencies=[],
        priority=ComponentPriority.NORMAL,
        config_params={}
    )
    
    manager.register_component(definition)
    
    # Test lifecycle
    print("Testing component lifecycle...")
    manager.initialize_component("example_component")
    manager.start_component("example_component")
    
    status = manager.get_component_status("example_component")
    print(f"Component status: {status['state']}")
    
    manager.stop_component("example_component")
    manager.cleanup()