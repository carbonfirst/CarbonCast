#!/usr/bin/env python3
"""
Retry Queue Processor for Smart Retry System

This module provides intelligent queue processing for retry requests with
priority-based scheduling, rate limiting, and capacity-aware processing.
It manages the retry queue with sophisticated algorithms for optimal
throughput and system stability.

Key Features:
- Priority-based queue processing with multiple priority levels
- Rate limiting and capacity-aware scheduling
- Batch processing with configurable batch sizes
- Dead letter queue for failed retries
- Real-time queue monitoring and metrics
- Integration with circuit breakers and retry strategies
"""

import time
import logging
import json
import sqlite3
import threading
import heapq
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import concurrent.futures
from logger_utils import get_logger


class QueueStatus(Enum):
    """Queue item status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    DEAD_LETTER = "dead_letter"


class ProcessingResult(Enum):
    """Processing result types."""
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CIRCUIT_OPEN = "circuit_open"
    RATE_LIMITED = "rate_limited"
    CAPACITY_EXCEEDED = "capacity_exceeded"


@dataclass
class QueueProcessorConfig:
    """Configuration for queue processor."""
    max_concurrent_processing: int = 5
    batch_size: int = 10
    processing_interval: int = 30
    rate_limit_requests_per_minute: int = 60
    rate_limit_window_size: int = 60
    dead_letter_max_attempts: int = 10
    queue_size_limit: int = 1000
    priority_boost_threshold: int = 300  # seconds
    stale_item_timeout: int = 3600  # 1 hour
    metrics_retention_hours: int = 24
    enable_batch_processing: bool = True
    enable_priority_boost: bool = True
    enable_dead_letter_queue: bool = True


@dataclass
class QueueItem:
    """Individual queue item for retry processing."""
    id: Optional[int] = None
    original_request_id: str = ""
    error_tracking_id: Optional[int] = None
    queue_priority: int = 5
    retry_attempt: int = 1
    max_retry_attempts: int = 5
    retry_strategy: str = "exponential_backoff"
    base_delay_seconds: int = 60
    current_delay_seconds: int = 60
    next_retry_time: str = ""
    retry_window_start: Optional[str] = None
    retry_window_end: Optional[str] = None
    queue_status: QueueStatus = QueueStatus.PENDING
    request_data: str = ""
    context_data: Optional[str] = None
    region: Optional[str] = None
    variable_type: Optional[str] = None
    file_path: Optional[str] = None
    eligibility_score: float = 1.0
    success_probability: float = 0.5
    resource_requirements: Optional[str] = None
    dependencies: Optional[str] = None
    retry_conditions: Optional[str] = None
    failure_patterns: Optional[str] = None
    last_error_message: Optional[str] = None
    processing_node: Optional[str] = None
    queue_position: Optional[int] = None
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None
    retry_history: Optional[str] = None
    metrics_data: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ProcessingMetrics:
    """Metrics for queue processing."""
    total_processed: int = 0
    successful_processed: int = 0
    failed_processed: int = 0
    retried_items: int = 0
    dead_letter_items: int = 0
    average_processing_time: float = 0.0
    throughput_per_minute: float = 0.0
    queue_size: int = 0
    processing_queue_size: int = 0
    rate_limit_hits: int = 0
    circuit_breaker_blocks: int = 0
    capacity_exceeded_count: int = 0
    last_processing_time: Optional[str] = None


@dataclass
class BatchProcessingResult:
    """Result of batch processing operation."""
    batch_id: str
    items_processed: int
    successful_items: int
    failed_items: int
    retried_items: int
    dead_letter_items: int
    processing_time: float
    rate_limited: bool
    capacity_exceeded: bool
    errors: List[str]
    timestamp: str


class RetryQueueProcessor:
    """
    Intelligent retry queue processor with priority-based scheduling,
    rate limiting, and capacity management.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db",
                 config: Optional[QueueProcessorConfig] = None):
        """
        Initialize the retry queue processor.
        
        Args:
            db_path: Path to SQLite database
            config: Processor configuration
        """
        self.db_path = db_path
        self.config = config or QueueProcessorConfig()
        self.logger = self._setup_logging()
        
        # Processing state
        self.processing_active = False
        self.processing_thread = None
        self.current_batch_id = None
        
        # Priority queue (min-heap based on priority and next_retry_time)
        self.priority_queue = []
        self.processing_items: Set[str] = set()
        
        # Rate limiting
        self.rate_limit_window = deque()
        self.rate_limit_lock = threading.Lock()
        
        # Metrics
        self.metrics = ProcessingMetrics()
        self.processing_history = deque(maxlen=1000)
        
        # Threading
        self.queue_lock = threading.Lock()
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_processing
        )
        
        # Initialize database
        self._initialize_database()
        
        # Load existing queue items
        self._load_queue_from_database()
        
        self.logger.info("Retry Queue Processor initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for this component using centralized configuration."""
        return get_logger('smart_retry.queue_processor', level=logging.INFO)
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self):
        """Initialize database tables for queue processing."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Queue processing metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS queue_processing_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        batch_id TEXT,
                        items_processed INTEGER DEFAULT 0,
                        successful_items INTEGER DEFAULT 0,
                        failed_items INTEGER DEFAULT 0,
                        retried_items INTEGER DEFAULT 0,
                        dead_letter_items INTEGER DEFAULT 0,
                        processing_time REAL DEFAULT 0.0,
                        throughput_per_minute REAL DEFAULT 0.0,
                        rate_limited BOOLEAN DEFAULT FALSE,
                        capacity_exceeded BOOLEAN DEFAULT FALSE,
                        errors_data TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Dead letter queue table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS dead_letter_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_queue_item_id INTEGER,
                        original_request_id TEXT NOT NULL,
                        failure_reason TEXT,
                        failure_count INTEGER DEFAULT 1,
                        last_failure_time TEXT,
                        request_data TEXT,
                        context_data TEXT,
                        region TEXT,
                        variable_type TEXT,
                        file_path TEXT,
                        retry_history TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_queue_metrics_batch 
                    ON queue_processing_metrics(batch_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_queue_metrics_time 
                    ON queue_processing_metrics(created_at)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dead_letter_request 
                    ON dead_letter_queue(original_request_id)
                """)
                
                conn.commit()
                self.logger.debug("Queue processor database tables initialized")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error initializing queue processor database: {e}")
            raise
    
    def _load_queue_from_database(self):
        """Load existing queue items from database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM retry_queue 
                    WHERE queue_status IN ('pending', 'processing')
                    ORDER BY queue_priority ASC, next_retry_time ASC
                """)
                
                loaded_count = 0
                for row in cursor.fetchall():
                    queue_item = self._row_to_queue_item(row)
                    self._add_to_priority_queue(queue_item)
                    loaded_count += 1
                
                self.logger.info(f"Loaded {loaded_count} items from database queue")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error loading queue from database: {e}")
    
    def _row_to_queue_item(self, row: sqlite3.Row) -> QueueItem:
        """Convert database row to QueueItem."""
        return QueueItem(
            id=row['id'],
            original_request_id=row['original_request_id'],
            error_tracking_id=row['error_tracking_id'],
            queue_priority=row['queue_priority'],
            retry_attempt=row['retry_attempt'],
            max_retry_attempts=row['max_retry_attempts'],
            retry_strategy=row['retry_strategy'],
            base_delay_seconds=row['base_delay_seconds'],
            current_delay_seconds=row['current_delay_seconds'],
            next_retry_time=row['next_retry_time'],
            retry_window_start=row['retry_window_start'],
            retry_window_end=row['retry_window_end'],
            queue_status=QueueStatus(row['queue_status']),
            request_data=row['request_data'],
            context_data=row['context_data'],
            region=row['region'],
            variable_type=row['variable_type'],
            file_path=row['file_path'],
            eligibility_score=row['eligibility_score'] or 1.0,
            success_probability=row['success_probability'] or 0.5,
            resource_requirements=row['resource_requirements'],
            dependencies=row['dependencies'],
            retry_conditions=row['retry_conditions'],
            failure_patterns=row['failure_patterns'],
            last_error_message=row['last_error_message'],
            processing_node=row['processing_node'],
            queue_position=row['queue_position'],
            estimated_duration=row['estimated_duration'],
            actual_duration=row['actual_duration'],
            retry_history=row['retry_history'],
            metrics_data=row['metrics_data'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def _add_to_priority_queue(self, item: QueueItem):
        """Add item to priority queue with proper ordering."""
        # Priority tuple: (priority, next_retry_time_timestamp, item_id, item)
        next_retry_timestamp = datetime.fromisoformat(item.next_retry_time.replace('Z', '+00:00')).timestamp()
        priority_tuple = (item.queue_priority, next_retry_timestamp, item.id or 0, item)
        heapq.heappush(self.priority_queue, priority_tuple)
    
    def add_to_queue(self, item: QueueItem) -> bool:
        """
        Add item to retry queue.
        
        Args:
            item: Queue item to add
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            with self.queue_lock:
                # Check queue size limit
                if len(self.priority_queue) >= self.config.queue_size_limit:
                    self.logger.warning(f"Queue size limit reached: {self.config.queue_size_limit}")
                    return False
                
                # Set timestamps if not set
                if not item.created_at:
                    item.created_at = datetime.now().isoformat()
                if not item.updated_at:
                    item.updated_at = datetime.now().isoformat()
                
                # Persist to database
                item_id = self._persist_queue_item(item)
                if item_id:
                    item.id = item_id
                    self._add_to_priority_queue(item)
                    self.metrics.queue_size = len(self.priority_queue)
                    
                    self.logger.debug(f"Added item {item.original_request_id} to queue "
                                    f"(priority: {item.queue_priority})")
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error adding item to queue: {e}")
            return False
    
    def _persist_queue_item(self, item: QueueItem) -> Optional[int]:
        """Persist queue item to database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO retry_queue (
                        original_request_id, error_tracking_id, queue_priority,
                        retry_attempt, max_retry_attempts, retry_strategy,
                        base_delay_seconds, current_delay_seconds, next_retry_time,
                        retry_window_start, retry_window_end, queue_status,
                        request_data, context_data, region, variable_type, file_path,
                        eligibility_score, success_probability, resource_requirements,
                        dependencies, retry_conditions, failure_patterns,
                        last_error_message, processing_node, queue_position,
                        estimated_duration, actual_duration, retry_history,
                        metrics_data, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.original_request_id, item.error_tracking_id, item.queue_priority,
                    item.retry_attempt, item.max_retry_attempts, item.retry_strategy,
                    item.base_delay_seconds, item.current_delay_seconds, item.next_retry_time,
                    item.retry_window_start, item.retry_window_end, item.queue_status.value,
                    item.request_data, item.context_data, item.region, item.variable_type,
                    item.file_path, item.eligibility_score, item.success_probability,
                    item.resource_requirements, item.dependencies, item.retry_conditions,
                    item.failure_patterns, item.last_error_message, item.processing_node,
                    item.queue_position, item.estimated_duration, item.actual_duration,
                    item.retry_history, item.metrics_data, item.created_at, item.updated_at
                ))
                
                item_id = cursor.lastrowid
                conn.commit()
                return item_id
                
        except sqlite3.Error as e:
            self.logger.error(f"Error persisting queue item: {e}")
            return None
    
    def _update_queue_item(self, item: QueueItem):
        """Update queue item in database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE retry_queue SET
                        queue_priority = ?, retry_attempt = ?, current_delay_seconds = ?,
                        next_retry_time = ?, queue_status = ?, last_error_message = ?,
                        processing_node = ?, actual_duration = ?, retry_history = ?,
                        metrics_data = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    item.queue_priority, item.retry_attempt, item.current_delay_seconds,
                    item.next_retry_time, item.queue_status.value, item.last_error_message,
                    item.processing_node, item.actual_duration, item.retry_history,
                    item.metrics_data, item.id
                ))
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error updating queue item: {e}")
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows processing."""
        with self.rate_limit_lock:
            current_time = time.time()
            window_start = current_time - self.config.rate_limit_window_size
            
            # Remove old entries
            while self.rate_limit_window and self.rate_limit_window[0] < window_start:
                self.rate_limit_window.popleft()
            
            # Check if we can process
            if len(self.rate_limit_window) >= self.config.rate_limit_requests_per_minute:
                self.metrics.rate_limit_hits += 1
                return False
            
            # Add current request
            self.rate_limit_window.append(current_time)
            return True
    
    def get_ready_items(self, max_items: Optional[int] = None) -> List[QueueItem]:
        """
        Get items ready for processing.
        
        Args:
            max_items: Maximum number of items to return
            
        Returns:
            List of ready queue items
        """
        ready_items = []
        current_time = datetime.now()
        max_items = max_items or self.config.batch_size
        
        with self.queue_lock:
            temp_queue = []
            
            while self.priority_queue and len(ready_items) < max_items:
                priority, next_retry_timestamp, item_id, item = heapq.heappop(self.priority_queue)
                
                # Check if item is ready
                next_retry_time = datetime.fromisoformat(item.next_retry_time.replace('Z', '+00:00'))
                
                if (next_retry_time.replace(tzinfo=None) <= current_time and 
                    item.queue_status == QueueStatus.PENDING and
                    item.original_request_id not in self.processing_items):
                    
                    ready_items.append(item)
                    self.processing_items.add(item.original_request_id)
                else:
                    # Put back in queue if not ready
                    temp_queue.append((priority, next_retry_timestamp, item_id, item))
            
            # Put back items that weren't ready
            for item_tuple in temp_queue:
                heapq.heappush(self.priority_queue, item_tuple)
        
        return ready_items
    
    def process_item(self, item: QueueItem) -> ProcessingResult:
        """
        Process a single queue item.
        
        Args:
            item: Queue item to process
            
        Returns:
            Processing result
        """
        start_time = time.time()
        
        try:
            # Update item status
            item.queue_status = QueueStatus.PROCESSING
            item.processing_node = "queue_processor"
            self._update_queue_item(item)
            
            # Simulate processing (replace with actual retry logic)
            self.logger.info(f"Processing retry for {item.original_request_id} "
                           f"(attempt {item.retry_attempt}/{item.max_retry_attempts})")
            
            # Here you would integrate with the actual retry mechanism
            # For now, simulate based on success probability
            import random
            success = random.random() < item.success_probability
            
            processing_time = time.time() - start_time
            item.actual_duration = int(processing_time)
            
            if success:
                item.queue_status = QueueStatus.COMPLETED
                self._update_queue_item(item)
                self.metrics.successful_processed += 1
                return ProcessingResult.SUCCESS
            else:
                # Check if we should retry or send to dead letter queue
                if item.retry_attempt >= item.max_retry_attempts:
                    self._move_to_dead_letter_queue(item, "Max retry attempts exceeded")
                    self.metrics.dead_letter_items += 1
                    return ProcessingResult.FAILURE
                else:
                    # Schedule for retry
                    item.retry_attempt += 1
                    item.queue_status = QueueStatus.PENDING
                    # Calculate next retry time (simplified)
                    next_retry = datetime.now() + timedelta(seconds=item.current_delay_seconds)
                    item.next_retry_time = next_retry.isoformat()
                    item.current_delay_seconds = min(item.current_delay_seconds * 2, 3600)
                    
                    self._update_queue_item(item)
                    self._add_to_priority_queue(item)
                    self.metrics.retried_items += 1
                    return ProcessingResult.RETRY
                    
        except Exception as e:
            self.logger.error(f"Error processing item {item.original_request_id}: {e}")
            item.queue_status = QueueStatus.FAILED
            item.last_error_message = str(e)
            self._update_queue_item(item)
            self.metrics.failed_processed += 1
            return ProcessingResult.FAILURE
            
        finally:
            # Remove from processing set
            self.processing_items.discard(item.original_request_id)
    
    def _move_to_dead_letter_queue(self, item: QueueItem, reason: str):
        """Move item to dead letter queue."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO dead_letter_queue (
                        original_queue_item_id, original_request_id, failure_reason,
                        failure_count, last_failure_time, request_data, context_data,
                        region, variable_type, file_path, retry_history
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id, item.original_request_id, reason, item.retry_attempt,
                    datetime.now().isoformat(), item.request_data, item.context_data,
                    item.region, item.variable_type, item.file_path, item.retry_history
                ))
                
                # Update original item status
                item.queue_status = QueueStatus.DEAD_LETTER
                self._update_queue_item(item)
                
                conn.commit()
                self.logger.warning(f"Moved item {item.original_request_id} to dead letter queue: {reason}")
                
        except sqlite3.Error as e:
            self.logger.error(f"Error moving item to dead letter queue: {e}")
    
    def process_batch(self) -> BatchProcessingResult:
        """
        Process a batch of ready items.
        
        Returns:
            Batch processing result
        """
        batch_id = f"batch_{int(time.time())}"
        start_time = time.time()
        
        # Check rate limit
        if not self._check_rate_limit():
            return BatchProcessingResult(
                batch_id=batch_id,
                items_processed=0,
                successful_items=0,
                failed_items=0,
                retried_items=0,
                dead_letter_items=0,
                processing_time=0.0,
                rate_limited=True,
                capacity_exceeded=False,
                errors=["Rate limit exceeded"],
                timestamp=datetime.now().isoformat()
            )
        
        # Get ready items
        ready_items = self.get_ready_items()
        
        if not ready_items:
            return BatchProcessingResult(
                batch_id=batch_id,
                items_processed=0,
                successful_items=0,
                failed_items=0,
                retried_items=0,
                dead_letter_items=0,
                processing_time=time.time() - start_time,
                rate_limited=False,
                capacity_exceeded=False,
                errors=[],
                timestamp=datetime.now().isoformat()
            )
        
        self.logger.info(f"Processing batch {batch_id} with {len(ready_items)} items")
        
        # Process items concurrently
        results = []
        errors = []
        
        if self.config.enable_batch_processing:
            # Concurrent processing
            futures = []
            for item in ready_items:
                future = self.executor.submit(self.process_item, item)
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures, timeout=300):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
                    results.append(ProcessingResult.FAILURE)
        else:
            # Sequential processing
            for item in ready_items:
                try:
                    result = self.process_item(item)
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))
                    results.append(ProcessingResult.FAILURE)
        
        # Calculate results
        successful_items = results.count(ProcessingResult.SUCCESS)
        failed_items = results.count(ProcessingResult.FAILURE)
        retried_items = results.count(ProcessingResult.RETRY)
        
        processing_time = time.time() - start_time
        
        # Update metrics
        self.metrics.total_processed += len(ready_items)
        self.metrics.last_processing_time = datetime.now().isoformat()
        
        if processing_time > 0:
            self.metrics.throughput_per_minute = (len(ready_items) / processing_time) * 60
        
        # Create result
        batch_result = BatchProcessingResult(
            batch_id=batch_id,
            items_processed=len(ready_items),
            successful_items=successful_items,
            failed_items=failed_items,
            retried_items=retried_items,
            dead_letter_items=0,  # Calculated separately
            processing_time=processing_time,
            rate_limited=False,
            capacity_exceeded=False,
            errors=errors,
            timestamp=datetime.now().isoformat()
        )
        
        # Store batch result
        self._store_batch_result(batch_result)
        
        self.logger.info(f"Batch {batch_id} completed: {successful_items} success, "
                        f"{failed_items} failed, {retried_items} retried")
        
        return batch_result
    
    def _store_batch_result(self, result: BatchProcessingResult):
        """Store batch processing result in database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO queue_processing_metrics (
                        batch_id, items_processed, successful_items, failed_items,
                        retried_items, dead_letter_items, processing_time,
                        throughput_per_minute, rate_limited, capacity_exceeded,
                        errors_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.batch_id, result.items_processed, result.successful_items,
                    result.failed_items, result.retried_items, result.dead_letter_items,
                    result.processing_time, self.metrics.throughput_per_minute,
                    result.rate_limited, result.capacity_exceeded,
                    json.dumps(result.errors)
                ))
                
                conn.commit()
                
        except sqlite3.Error as e:
            self.logger.error(f"Error storing batch result: {e}")
    
    def start_processing(self):
        """Start continuous queue processing."""
        if self.processing_active:
            self.logger.warning("Queue processing is already active")
            return
        
        def processing_loop():
            self.logger.info(f"Starting queue processing loop (interval: {self.config.processing_interval}s)")
            
            while self.processing_active:
                try:
                    batch_result = self.process_batch()
                    
                    if batch_result.items_processed > 0:
                        self.logger.info(f"Processed batch: {batch_result.items_processed} items, "
                                       f"{batch_result.successful_items} successful")
                    
                    # Wait for next processing cycle
                    time.sleep(self.config.processing_interval)
                    
                except Exception as e:
                    self.logger.error(f"Error in processing loop: {e}")
                    time.sleep(min(self.config.processing_interval, 60))
            
            self.logger.info("Queue processing loop stopped")
        
        self.processing_active = True
        self.processing_thread = threading.Thread(target=processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("Queue processing started")
    
    def stop_processing(self):
        """Stop continuous queue processing."""
        if not self.processing_active:
            return
        
        self.logger.info("Stopping queue processing...")
        self.processing_active = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
        
        self.logger.info("Queue processing stopped")
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get comprehensive queue status.
        
        Returns:
            Dictionary containing queue status information
        """
        try:
            with self.queue_lock:
                queue_size = len(self.priority_queue)
                processing_size = len(self.processing_items)
            
            # Get status distribution
            status_distribution = defaultdict(int)
            priority_distribution = defaultdict(int)
            
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT queue_status, COUNT(*) as count
                    FROM retry_queue
                    GROUP BY queue_status
                """)
                
                for row in cursor.fetchall():
                    status_distribution[row['queue_status']] = row['count']
                
                cursor = conn.execute("""
                    SELECT queue_priority, COUNT(*) as count
                    FROM retry_queue
                    WHERE queue_status = 'pending'
                    GROUP BY queue_priority
                """)
                
                for row in cursor.fetchall():
                    priority_distribution[row['queue_priority']] = row['count']
            
            return {
                'queue_size': queue_size,
                'processing_size': processing_size,
                'status_distribution': dict(status_distribution),
                'priority_distribution': dict(priority_distribution),
                'metrics': asdict(self.metrics),
                'processing_active': self.processing_active,
                'configuration': asdict(self.config),
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error getting queue status: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }


def create_retry_queue_processor(db_path: str = "src/python/data/automation_state.db",
                               config: Optional[QueueProcessorConfig] = None) -> RetryQueueProcessor:
    """
    Factory function to create a Retry Queue Processor.
    
    Args:
        db_path: Path to SQLite database
        config: Processor configuration
        
    Returns:
        Configured RetryQueueProcessor instance
    """
    return RetryQueueProcessor(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Retry Queue Processor')
    parser.add_argument('--start-processing', action='store_true',
                       help='Start continuous queue processing')
    parser.add_argument('--process-batch', action='store_true',
                       help='Process a single batch')
    parser.add_argument('--status', action='store_true',
                       help='Show queue status')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create queue processor
    processor = create_retry_queue_processor(args.db_path)
    
    try:
        if args.start_processing:
            print("=== Starting Queue Processing ===")
            processor.start_processing()
            
            # Keep running until interrupted
            try:
                while processor.processing_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping queue processing...")
                processor.stop_processing()
        
        elif args.process_batch:
            print("=== Processing Single Batch ===")
            result = processor.process_batch()
            print(f"Batch Result: {result.items_processed} items processed, "
                  f"{result.successful_items} successful")
        
        elif args.status:
            print("=== Queue Status ===")
            status = processor.get_queue_status()
            print(json.dumps(status, indent=2))
        
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(processor, 'processing_active') and processor.processing_active:
            processor.stop_processing()