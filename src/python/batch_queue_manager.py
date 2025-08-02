#!/usr/bin/env python3
"""
Advanced Queue Management System for Batch Automation

This module provides intelligent queuing, priority management, and advanced
monitoring capabilities for the batch automation system.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import heapq

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_automation import RequestStatus, BatchAutomationSystem


class Priority(Enum):
    """Request priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueuedRequest:
    """Enhanced request with queue management features."""
    control_file: str
    priority: Priority = Priority.NORMAL
    estimated_size_gb: float = 1.0
    estimated_duration_hours: float = 2.0
    dependencies: List[str] = None
    region_group: str = "default"
    variable_group: str = "default"
    queue_time: str = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.queue_time is None:
            self.queue_time = datetime.now().isoformat()
    
    def __lt__(self, other):
        """Priority queue comparison."""
        # Higher priority value = higher priority in queue
        return self.priority.value > other.priority.value


class IntelligentQueueManager:
    """Advanced queue management with intelligent scheduling."""
    
    def __init__(self, batch_system: BatchAutomationSystem):
        self.batch_system = batch_system
        self.logger = logging.getLogger('queue_manager')
        
        # Queue management
        self.priority_queue = []  # Priority heap
        self.processing_queue = []  # Currently processing
        self.completed_queue = []  # Completed requests
        self.failed_queue = []  # Failed requests
        
        # Rate limiting and resource management
        self.max_concurrent_by_region = 8  # Max concurrent per region (increased from 2)
        self.max_concurrent_by_variable = 10  # Max concurrent per variable type (increased from 3)
        self.max_total_concurrent = 10  # Overall max concurrent (increased from 5)
        self.region_counters = {}  # Track active requests per region
        self.variable_counters = {}  # Track active requests per variable
        
        # Load queue state
        self.queue_state_file = Path("queue_state.json")
        self._load_queue_state()
    
    def _load_queue_state(self):
        """Load queue state from file."""
        if self.queue_state_file.exists():
            try:
                with open(self.queue_state_file, 'r') as f:
                    state_data = json.load(f)
                
                def deserialize_request(item_data):
                    """Convert serialized dict back to QueuedRequest."""
                    if 'priority' in item_data and isinstance(item_data['priority'], str):
                        # Convert string back to Priority enum
                        item_data['priority'] = Priority[item_data['priority']]
                    return QueuedRequest(**item_data)
                
                # Reconstruct priority queue
                for item_data in state_data.get('priority_queue', []):
                    request = deserialize_request(item_data)
                    heapq.heappush(self.priority_queue, request)
                
                # Load other queues
                for item_data in state_data.get('processing_queue', []):
                    self.processing_queue.append(deserialize_request(item_data))
                
                for item_data in state_data.get('completed_queue', []):
                    self.completed_queue.append(deserialize_request(item_data))
                
                for item_data in state_data.get('failed_queue', []):
                    self.failed_queue.append(deserialize_request(item_data))
                
                self.logger.info(f"Loaded queue state: {len(self.priority_queue)} pending, {len(self.processing_queue)} processing")
            except Exception as e:
                self.logger.error(f"Error loading queue state: {e}")
                # Reset queues on error
                self.priority_queue = []
                self.processing_queue = []
                self.completed_queue = []
                self.failed_queue = []
    
    def _save_queue_state(self):
        """Save queue state to file."""
        try:
            def serialize_request(req):
                """Convert QueuedRequest to serializable dict."""
                req_dict = asdict(req)
                req_dict['priority'] = req.priority.name  # Convert enum to string
                return req_dict
            
            state_data = {
                'priority_queue': [serialize_request(req) for req in self.priority_queue],
                'processing_queue': [serialize_request(req) for req in self.processing_queue],
                'completed_queue': [serialize_request(req) for req in self.completed_queue[-100:]],  # Keep last 100
                'failed_queue': [serialize_request(req) for req in self.failed_queue[-50:]]  # Keep last 50
            }
            
            with open(self.queue_state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            self.logger.debug("Queue state saved")
        except Exception as e:
            self.logger.error(f"Error saving queue state: {e}")
    
    def analyze_control_file(self, control_file: str) -> QueuedRequest:
        """Analyze control file to determine queue parameters."""
        try:
            # Extract region and variable from filename
            filename = Path(control_file).name
            if filename.endswith('_control.ctl'):
                base_name = filename[:-12]
                parts = base_name.split('_')
                if len(parts) >= 2:
                    region = parts[0].upper()
                    variable = parts[1].lower()
                else:
                    region = "UNKNOWN"
                    variable = "unknown"
            else:
                region = "UNKNOWN"
                variable = "unknown"
            
            # Estimate size and duration based on variable type
            size_estimates = {
                'dswrf': 2.5,  # Solar data tends to be larger
                'wind': 3.0,   # Wind components (U+V) are larger
                'temp': 1.5,   # Temperature data is moderate
                'rain': 1.0,   # Precipitation data is smaller
                'unknown': 2.0  # Default estimate
            }
            
            duration_estimates = {
                'dswrf': 3.0,  # Solar processing takes longer
                'wind': 4.0,   # Wind processing is most complex
                'temp': 2.0,   # Temperature is moderate
                'rain': 1.5,   # Precipitation is fastest
                'unknown': 2.5  # Default estimate
            }
            
            # Determine priority based on region importance and variable type
            priority = Priority.NORMAL
            
            # High priority regions (major grid operators)
            high_priority_regions = {'CISO', 'ERCOT', 'PJM', 'MISO', 'ISNE'}
            if region in high_priority_regions:
                priority = Priority.HIGH
            
            # Solar data gets higher priority (common use case)
            if variable == 'dswrf':
                priority = Priority.HIGH if priority == Priority.NORMAL else Priority.URGENT
            
            return QueuedRequest(
                control_file=control_file,
                priority=priority,
                estimated_size_gb=size_estimates.get(variable, 2.0),
                estimated_duration_hours=duration_estimates.get(variable, 2.5),
                region_group=region,
                variable_group=variable
            )
        
        except Exception as e:
            self.logger.error(f"Error analyzing control file {control_file}: {e}")
            return QueuedRequest(control_file=control_file)
    
    def add_to_queue(self, control_files: List[str]):
        """Add control files to the priority queue."""
        for control_file in control_files:
            # Skip if already in any queue
            if self._is_in_any_queue(control_file):
                continue
            
            queued_request = self.analyze_control_file(control_file)
            heapq.heappush(self.priority_queue, queued_request)
            
            self.logger.info(f"Added to queue: {control_file} (Priority: {queued_request.priority.name})")
        
        self._save_queue_state()
        self.logger.info(f"Queue updated: {len(self.priority_queue)} requests pending")
    
    def _is_in_any_queue(self, control_file: str) -> bool:
        """Check if control file is already in any queue."""
        all_queues = [
            self.priority_queue,
            self.processing_queue,
            self.completed_queue,
            self.failed_queue
        ]
        
        for queue in all_queues:
            if any(req.control_file == control_file for req in queue):
                return True
        
        return False
    
    def can_process_request(self, request: QueuedRequest) -> bool:
        """Check if request can be processed based on resource limits."""
        # Check overall concurrent limit
        if len(self.processing_queue) >= self.max_total_concurrent:
            return False
        
        # Check region-specific limit
        region_count = self.region_counters.get(request.region_group, 0)
        if region_count >= self.max_concurrent_by_region:
            return False
        
        # Check variable-specific limit
        variable_count = self.variable_counters.get(request.variable_group, 0)
        if variable_count >= self.max_concurrent_by_variable:
            return False
        
        # Check dependencies
        if request.dependencies:
            for dep in request.dependencies:
                if not self._is_dependency_satisfied(dep):
                    return False
        
        return True
    
    def _is_dependency_satisfied(self, dependency: str) -> bool:
        """Check if a dependency is satisfied (completed)."""
        return any(
            req.control_file == dependency
            for req in self.completed_queue
        )
    
    def get_next_requests(self) -> List[QueuedRequest]:
        """Get next requests that can be processed."""
        available_requests = []
        temp_queue = []
        
        # Extract requests from priority queue that can be processed
        while self.priority_queue and len(available_requests) < 10:  # Get up to 10 at once (increased from 3)
            request = heapq.heappop(self.priority_queue)
            
            if self.can_process_request(request):
                available_requests.append(request)
                
                # Update counters
                self.region_counters[request.region_group] = \
                    self.region_counters.get(request.region_group, 0) + 1
                self.variable_counters[request.variable_group] = \
                    self.variable_counters.get(request.variable_group, 0) + 1
                
                # Move to processing queue
                self.processing_queue.append(request)
            else:
                # Put back in queue for later
                temp_queue.append(request)
        
        # Put back requests that couldn't be processed
        for request in temp_queue:
            heapq.heappush(self.priority_queue, request)
        
        if available_requests:
            self._save_queue_state()
            self.logger.info(f"Selected {len(available_requests)} requests for processing")
        
        return available_requests
    
    def mark_request_completed(self, control_file: str, success: bool = True):
        """Mark a request as completed or failed."""
        # Find and remove from processing queue
        request = None
        for i, req in enumerate(self.processing_queue):
            if req.control_file == control_file:
                request = self.processing_queue.pop(i)
                break
        
        if not request:
            self.logger.warning(f"Request not found in processing queue: {control_file}")
            return
        
        # Update counters
        self.region_counters[request.region_group] = \
            max(0, self.region_counters.get(request.region_group, 0) - 1)
        self.variable_counters[request.variable_group] = \
            max(0, self.variable_counters.get(request.variable_group, 0) - 1)
        
        # Move to appropriate queue
        if success:
            self.completed_queue.append(request)
            self.logger.info(f"Request completed: {control_file}")
        else:
            self.failed_queue.append(request)
            self.logger.warning(f"Request failed: {control_file}")
        
        self._save_queue_state()
    
    def requeue_failed_requests(self, max_retries: int = 3):
        """Requeue failed requests with lower priority."""
        requeued = 0
        remaining_failed = []
        
        for request in self.failed_queue:
            # Check if we should retry (simple retry logic)
            if hasattr(request, 'retry_count'):
                request.retry_count += 1
            else:
                request.retry_count = 1
            
            if request.retry_count <= max_retries:
                # Lower the priority for retry
                if request.priority != Priority.LOW:
                    request.priority = Priority(max(1, request.priority.value - 1))
                
                heapq.heappush(self.priority_queue, request)
                requeued += 1
                self.logger.info(f"Requeued failed request: {request.control_file} (attempt {request.retry_count})")
            else:
                remaining_failed.append(request)
        
        self.failed_queue = remaining_failed
        
        if requeued > 0:
            self._save_queue_state()
            self.logger.info(f"Requeued {requeued} failed requests")
    
    def optimize_queue_order(self):
        """Optimize queue order based on current system state."""
        if not self.priority_queue:
            return
        
        # Extract all requests
        all_requests = []
        while self.priority_queue:
            all_requests.append(heapq.heappop(self.priority_queue))
        
        # Re-prioritize based on current conditions
        for request in all_requests:
            # Boost priority for underutilized regions/variables
            region_load = self.region_counters.get(request.region_group, 0)
            variable_load = self.variable_counters.get(request.variable_group, 0)
            
            if region_load == 0 and variable_load == 0:
                # Boost priority for completely idle categories
                if request.priority.value < Priority.HIGH.value:
                    request.priority = Priority(request.priority.value + 1)
        
        # Re-add to priority queue
        for request in all_requests:
            heapq.heappush(self.priority_queue, request)
        
        self._save_queue_state()
        self.logger.info("Queue order optimized")
    
    def get_queue_statistics(self) -> Dict:
        """Get comprehensive queue statistics."""
        stats = {
            'queue_lengths': {
                'pending': len(self.priority_queue),
                'processing': len(self.processing_queue),
                'completed': len(self.completed_queue),
                'failed': len(self.failed_queue)
            },
            'resource_utilization': {
                'total_concurrent': len(self.processing_queue),
                'max_total_concurrent': self.max_total_concurrent,
                'region_utilization': dict(self.region_counters),
                'variable_utilization': dict(self.variable_counters)
            },
            'priority_distribution': {},
            'estimated_completion': {}
        }
        
        # Calculate priority distribution
        priority_counts = {}
        for request in self.priority_queue:
            priority_counts[request.priority.name] = \
                priority_counts.get(request.priority.name, 0) + 1
        stats['priority_distribution'] = priority_counts
        
        # Estimate completion times
        if self.priority_queue:
            total_estimated_hours = sum(req.estimated_duration_hours for req in self.priority_queue)
            avg_concurrent = max(1, len(self.processing_queue))
            estimated_completion_hours = total_estimated_hours / avg_concurrent
            
            stats['estimated_completion'] = {
                'total_estimated_hours': total_estimated_hours,
                'estimated_completion_hours': estimated_completion_hours,
                'estimated_completion_time': (
                    datetime.now() + timedelta(hours=estimated_completion_hours)
                ).isoformat()
            }
        
        return stats
    
    def print_queue_status(self):
        """Print detailed queue status."""
        stats = self.get_queue_statistics()
        
        print("\n" + "="*70)
        print("INTELLIGENT QUEUE MANAGER STATUS")
        print("="*70)
        
        # Queue lengths
        print("Queue Lengths:")
        for queue_name, length in stats['queue_lengths'].items():
            print(f"  {queue_name.capitalize()}: {length}")
        
        # Resource utilization
        print(f"\nResource Utilization:")
        util = stats['resource_utilization']
        print(f"  Total Concurrent: {util['total_concurrent']}/{util['max_total_concurrent']}")
        
        if util['region_utilization']:
            print("  Region Utilization:")
            for region, count in util['region_utilization'].items():
                print(f"    {region}: {count}/{self.max_concurrent_by_region}")
        
        if util['variable_utilization']:
            print("  Variable Utilization:")
            for variable, count in util['variable_utilization'].items():
                print(f"    {variable}: {count}/{self.max_concurrent_by_variable}")
        
        # Priority distribution
        if stats['priority_distribution']:
            print("\nPriority Distribution:")
            for priority, count in stats['priority_distribution'].items():
                print(f"  {priority}: {count}")
        
        # Estimated completion
        if stats['estimated_completion']:
            est = stats['estimated_completion']
            print(f"\nEstimated Completion:")
            print(f"  Total Estimated Hours: {est['total_estimated_hours']:.1f}")
            print(f"  Completion Time: {est['estimated_completion_time']}")
        
        print("="*70)


def main():
    """Main function for testing queue manager."""
    # Initialize batch system and queue manager
    batch_system = BatchAutomationSystem()
    queue_manager = IntelligentQueueManager(batch_system)
    
    # Discover control files
    control_files = batch_system.discover_control_files()
    
    if control_files:
        print(f"Found {len(control_files)} control files")
        
        # Add to queue
        queue_manager.add_to_queue(control_files[:10])  # Test with first 10
        
        # Print status
        queue_manager.print_queue_status()
        
        # Get next requests
        next_requests = queue_manager.get_next_requests()
        print(f"\nNext {len(next_requests)} requests ready for processing:")
        for req in next_requests:
            print(f"  {req.control_file} (Priority: {req.priority.name})")
    else:
        print("No control files found")


if __name__ == '__main__':
    main()