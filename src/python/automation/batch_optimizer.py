#!/usr/bin/env python3
"""
Batch Optimizer for RDA Automation System

This module provides intelligent batch optimization for the RDA system, implementing
advanced strategies for batch size calculation, submission timing, and throughput
optimization while respecting the 10-request limit.

Key Features:
- Intelligent batch size optimization based on current system state
- Submission timing strategies for optimal throughput
- Predictive capacity management and load balancing
- Integration with dynamic trigger system and capacity manager
- Comprehensive analytics and performance monitoring
- Adaptive optimization based on historical performance
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import deque
import statistics
import math

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.dynamic_trigger_system import DynamicTriggerSystem, BatchCalculation, TriggerType
from automation.capacity_manager import CapacityManager, CapacityLevel, CapacityStatus
from automation.enhanced_request_monitor import EnhancedRequestMonitor, RequestCountSnapshot


class OptimizationStrategy(Enum):
    """Optimization strategies for batch processing."""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    ADAPTIVE = "adaptive"
    PREDICTIVE = "predictive"


class SystemState(Enum):
    """System state classifications."""
    IDLE = "idle"              # 0-3 requests
    NORMAL = "normal"          # 4-7 requests
    BUSY = "busy"              # 8-9 requests
    SATURATED = "saturated"    # 10 requests
    OVERLOADED = "overloaded"  # >10 requests (error state)


class OptimizationMode(Enum):
    """Optimization modes."""
    THROUGHPUT = "throughput"      # Maximize request throughput
    EFFICIENCY = "efficiency"      # Optimize resource utilization
    RELIABILITY = "reliability"    # Prioritize success rate
    BALANCED = "balanced"          # Balance all factors


@dataclass
class OptimizationConfig:
    """Configuration for batch optimization."""
    strategy: OptimizationStrategy = OptimizationStrategy.ADAPTIVE
    mode: OptimizationMode = OptimizationMode.BALANCED
    target_utilization: float = 0.9  # Target 90% of 10-request capacity
    min_batch_size: int = 1
    max_batch_size: int = 10
    optimization_interval: int = 30  # seconds
    learning_enabled: bool = True
    predictive_window: int = 300  # 5 minutes for predictions
    risk_tolerance: float = 0.7  # 0.0 = very conservative, 1.0 = very aggressive
    performance_weight: float = 0.4
    reliability_weight: float = 0.3
    efficiency_weight: float = 0.3


@dataclass
class SystemMetrics:
    """Current system performance metrics."""
    current_request_count: int
    average_processing_time: float
    success_rate: float
    throughput_rate: float  # requests per hour
    capacity_utilization: float
    error_rate: float
    queue_length: int
    available_files: int
    timestamp: str


@dataclass
class OptimizationResult:
    """Result of batch optimization calculation."""
    recommended_batch_size: int
    confidence_score: float
    optimization_strategy: OptimizationStrategy
    reasoning: str
    expected_performance: Dict[str, float]
    risk_assessment: str
    alternative_options: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceHistory:
    """Historical performance data point."""
    timestamp: str
    batch_size: int
    processing_time: float
    success_rate: float
    system_state: SystemState
    optimization_strategy: OptimizationStrategy
    actual_throughput: float
    predicted_throughput: float


class BatchOptimizer:
    """
    Intelligent batch optimizer that analyzes system state and optimizes batch processing
    for maximum efficiency while maintaining the 10-request target capacity.
    """
    
    def __init__(self,
                 config: Optional[OptimizationConfig] = None,
                 capacity_manager: Optional[CapacityManager] = None,
                 enhanced_monitor: Optional[EnhancedRequestMonitor] = None,
                 dynamic_trigger: Optional[DynamicTriggerSystem] = None):
        """
        Initialize the Batch Optimizer.
        
        Args:
            config: Optimization configuration
            capacity_manager: Capacity manager for system state
            enhanced_monitor: Enhanced request monitor for metrics
            dynamic_trigger: Dynamic trigger system for coordination
        """
        self.logger = self._setup_logging()
        self.config = config or OptimizationConfig()
        
        # Core components
        self.capacity_manager = capacity_manager
        self.enhanced_monitor = enhanced_monitor
        self.dynamic_trigger = dynamic_trigger
        
        # Optimization state
        self.optimization_active = False
        self.optimization_thread: Optional[threading.Thread] = None
        self.current_strategy = self.config.strategy
        
        # Performance tracking
        self.performance_history: deque = deque(maxlen=1000)
        self.system_metrics_history: deque = deque(maxlen=200)
        self.optimization_results: deque = deque(maxlen=100)
        
        # Learning and adaptation
        self.strategy_performance: Dict[OptimizationStrategy, List[float]] = {
            strategy: [] for strategy in OptimizationStrategy
        }
        self.adaptive_weights = {
            "performance": self.config.performance_weight,
            "reliability": self.config.reliability_weight,
            "efficiency": self.config.efficiency_weight
        }
        
        # Threading
        self.optimizer_lock = threading.RLock()
        
        # Integration components
        self.batch_system = None
        self.queue_manager = None
        
        self.logger.info("BatchOptimizer initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the batch optimizer."""
        logger = logging.getLogger('rda_automation.batch_optimizer')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        return logger
    
    def set_integration_components(self, batch_system=None, queue_manager=None):
        """
        Set integration components.
        
        Args:
            batch_system: BatchAutomationSystem instance
            queue_manager: IntelligentQueueManager instance
        """
        self.batch_system = batch_system
        self.queue_manager = queue_manager
        
        self.logger.info("✅ Integration components configured for batch optimizer")
    
    def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system performance metrics.
        
        Returns:
            SystemMetrics with current system state
        """
        try:
            # Get current request count
            current_count = 0
            if self.enhanced_monitor:
                snapshot = self.enhanced_monitor.create_snapshot()
                current_count = snapshot.total_requests
            elif self.capacity_manager:
                status = self.capacity_manager.get_current_capacity_status()
                current_count = status.total_requests
            
            # Calculate metrics from performance history
            recent_history = list(self.performance_history)[-20:]  # Last 20 operations
            
            avg_processing_time = 0.0
            success_rate = 1.0
            throughput_rate = 0.0
            error_rate = 0.0
            
            if recent_history:
                processing_times = [h.processing_time for h in recent_history if h.processing_time > 0]
                if processing_times:
                    avg_processing_time = statistics.mean(processing_times)
                
                successful = len([h for h in recent_history if h.success_rate > 0.8])
                success_rate = successful / len(recent_history)
                error_rate = 1.0 - success_rate
                
                # Calculate throughput (requests per hour)
                if len(recent_history) > 1:
                    time_span = (datetime.fromisoformat(recent_history[-1].timestamp) - 
                               datetime.fromisoformat(recent_history[0].timestamp)).total_seconds()
                    if time_span > 0:
                        throughput_rate = (len(recent_history) * 3600) / time_span
            
            # Calculate capacity utilization
            capacity_utilization = current_count / 10.0
            
            # Get queue length and available files
            queue_length = 0
            available_files = 0
            
            if self.queue_manager:
                try:
                    queue_status = self.queue_manager.get_queue_status()
                    queue_length = queue_status.get('pending_requests', 0)
                except:
                    pass
            
            # Estimate available files (simplified)
            if self.capacity_manager:
                try:
                    upload_status = self.capacity_manager.get_upload_status()
                    available_files = upload_status.get('available_control_files', 0)
                except:
                    pass
            
            return SystemMetrics(
                current_request_count=current_count,
                average_processing_time=avg_processing_time,
                success_rate=success_rate,
                throughput_rate=throughput_rate,
                capacity_utilization=capacity_utilization,
                error_rate=error_rate,
                queue_length=queue_length,
                available_files=available_files,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error collecting system metrics: {e}")
            return SystemMetrics(
                current_request_count=0,
                average_processing_time=0.0,
                success_rate=1.0,
                throughput_rate=0.0,
                capacity_utilization=0.0,
                error_rate=0.0,
                queue_length=0,
                available_files=0,
                timestamp=datetime.now().isoformat()
            )
    
    def classify_system_state(self, metrics: SystemMetrics) -> SystemState:
        """
        Classify current system state based on metrics.
        
        Args:
            metrics: Current system metrics
            
        Returns:
            SystemState classification
        """
        try:
            count = metrics.current_request_count
            
            if count > 10:
                return SystemState.OVERLOADED
            elif count == 10:
                return SystemState.SATURATED
            elif count >= 8:
                return SystemState.BUSY
            elif count >= 4:
                return SystemState.NORMAL
            else:
                return SystemState.IDLE
                
        except Exception as e:
            self.logger.error(f"❌ Error classifying system state: {e}")
            return SystemState.NORMAL
    
    def calculate_optimal_batch_size(self, 
                                   metrics: SystemMetrics,
                                   system_state: SystemState,
                                   strategy: OptimizationStrategy) -> OptimizationResult:
        """
        Calculate optimal batch size based on current conditions.
        
        Args:
            metrics: Current system metrics
            system_state: Current system state
            strategy: Optimization strategy to use
            
        Returns:
            OptimizationResult with recommended batch size and analysis
        """
        try:
            available_slots = max(0, 10 - metrics.current_request_count)
            
            if available_slots == 0:
                return OptimizationResult(
                    recommended_batch_size=0,
                    confidence_score=1.0,
                    optimization_strategy=strategy,
                    reasoning="No available capacity slots",
                    expected_performance={"throughput": 0.0, "success_rate": 1.0},
                    risk_assessment="none",
                    alternative_options=[]
                )
            
            # Strategy-specific calculations
            if strategy == OptimizationStrategy.CONSERVATIVE:
                batch_size = self._calculate_conservative_batch(metrics, system_state, available_slots)
            elif strategy == OptimizationStrategy.AGGRESSIVE:
                batch_size = self._calculate_aggressive_batch(metrics, system_state, available_slots)
            elif strategy == OptimizationStrategy.BALANCED:
                batch_size = self._calculate_balanced_batch(metrics, system_state, available_slots)
            elif strategy == OptimizationStrategy.ADAPTIVE:
                batch_size = self._calculate_adaptive_batch(metrics, system_state, available_slots)
            elif strategy == OptimizationStrategy.PREDICTIVE:
                batch_size = self._calculate_predictive_batch(metrics, system_state, available_slots)
            else:
                batch_size = self._calculate_balanced_batch(metrics, system_state, available_slots)
            
            # Apply constraints
            batch_size = max(self.config.min_batch_size, 
                           min(batch_size, self.config.max_batch_size, available_slots))
            
            # Calculate confidence and performance expectations
            confidence = self._calculate_confidence_score(batch_size, metrics, system_state, strategy)
            expected_performance = self._predict_performance(batch_size, metrics, system_state)
            risk_assessment = self._assess_risk(batch_size, metrics, system_state)
            
            # Generate alternative options
            alternatives = self._generate_alternatives(batch_size, metrics, system_state, available_slots)
            
            # Create reasoning
            reasoning = self._generate_reasoning(batch_size, metrics, system_state, strategy)
            
            return OptimizationResult(
                recommended_batch_size=batch_size,
                confidence_score=confidence,
                optimization_strategy=strategy,
                reasoning=reasoning,
                expected_performance=expected_performance,
                risk_assessment=risk_assessment,
                alternative_options=alternatives,
                metadata={
                    "available_slots": available_slots,
                    "system_state": system_state.value,
                    "utilization": metrics.capacity_utilization
                }
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating optimal batch size: {e}")
            return OptimizationResult(
                recommended_batch_size=1,
                confidence_score=0.5,
                optimization_strategy=strategy,
                reasoning=f"Error in calculation: {str(e)}",
                expected_performance={"throughput": 0.0, "success_rate": 0.5},
                risk_assessment="unknown",
                alternative_options=[]
            )
    
    def _calculate_conservative_batch(self, metrics: SystemMetrics, state: SystemState, available: int) -> int:
        """Calculate batch size using conservative strategy."""
        if state == SystemState.SATURATED:
            return 0
        elif state == SystemState.BUSY:
            return min(1, available)
        elif state == SystemState.NORMAL:
            return min(2, available)
        else:  # IDLE
            return min(3, available)
    
    def _calculate_aggressive_batch(self, metrics: SystemMetrics, state: SystemState, available: int) -> int:
        """Calculate batch size using aggressive strategy."""
        if state == SystemState.SATURATED:
            return 0
        elif state == SystemState.BUSY:
            return min(available, 3)
        elif state == SystemState.NORMAL:
            return min(available, 6)
        else:  # IDLE
            return available  # Fill all available slots
    
    def _calculate_balanced_batch(self, metrics: SystemMetrics, state: SystemState, available: int) -> int:
        """Calculate batch size using balanced strategy."""
        if state == SystemState.SATURATED:
            return 0
        elif state == SystemState.BUSY:
            return min(2, available)
        elif state == SystemState.NORMAL:
            return min(4, available)
        else:  # IDLE
            return min(6, available)
    
    def _calculate_adaptive_batch(self, metrics: SystemMetrics, state: SystemState, available: int) -> int:
        """Calculate batch size using adaptive strategy based on historical performance."""
        try:
            # Start with balanced approach
            base_size = self._calculate_balanced_batch(metrics, state, available)
            
            # Adjust based on recent performance
            if self.performance_history:
                recent_performance = list(self.performance_history)[-10:]
                avg_success_rate = statistics.mean([p.success_rate for p in recent_performance])
                
                if avg_success_rate > 0.9:
                    # High success rate, can be more aggressive
                    adjustment = 1.2
                elif avg_success_rate < 0.7:
                    # Low success rate, be more conservative
                    adjustment = 0.8
                else:
                    adjustment = 1.0
                
                adjusted_size = int(base_size * adjustment)
                return min(adjusted_size, available)
            
            return base_size
            
        except Exception as e:
            self.logger.error(f"❌ Error in adaptive calculation: {e}")
            return self._calculate_balanced_batch(metrics, state, available)
    
    def _calculate_predictive_batch(self, metrics: SystemMetrics, state: SystemState, available: int) -> int:
        """Calculate batch size using predictive strategy."""
        try:
            # Predict future capacity needs based on trends
            if len(self.system_metrics_history) < 5:
                return self._calculate_balanced_batch(metrics, state, available)
            
            recent_metrics = list(self.system_metrics_history)[-5:]
            
            # Calculate trend in request count
            counts = [m.current_request_count for m in recent_metrics]
            if len(counts) >= 2:
                # Simple linear trend
                trend = (counts[-1] - counts[0]) / len(counts)
                
                # Predict future capacity needs
                predicted_count = metrics.current_request_count + (trend * 2)  # 2 cycles ahead
                predicted_available = max(0, 10 - predicted_count)
                
                # Adjust batch size based on prediction
                if trend > 0:  # Increasing trend
                    # Be more conservative as system is getting busier
                    return min(2, available)
                elif trend < -1:  # Decreasing trend
                    # Be more aggressive as capacity is freeing up
                    return min(available, 6)
            
            return self._calculate_balanced_batch(metrics, state, available)
            
        except Exception as e:
            self.logger.error(f"❌ Error in predictive calculation: {e}")
            return self._calculate_balanced_batch(metrics, state, available)
    
    def _calculate_confidence_score(self, batch_size: int, metrics: SystemMetrics, 
                                  state: SystemState, strategy: OptimizationStrategy) -> float:
        """Calculate confidence score for the recommendation."""
        try:
            confidence = 0.7  # Base confidence
            
            # Adjust based on available data
            if len(self.performance_history) > 10:
                confidence += 0.1
            
            # Adjust based on system state
            if state == SystemState.NORMAL:
                confidence += 0.1
            elif state in [SystemState.SATURATED, SystemState.OVERLOADED]:
                confidence -= 0.2
            
            # Adjust based on success rate
            if metrics.success_rate > 0.9:
                confidence += 0.1
            elif metrics.success_rate < 0.7:
                confidence -= 0.2
            
            # Adjust based on strategy performance
            if strategy in self.strategy_performance and self.strategy_performance[strategy]:
                avg_performance = statistics.mean(self.strategy_performance[strategy])
                if avg_performance > 0.8:
                    confidence += 0.1
                elif avg_performance < 0.6:
                    confidence -= 0.1
            
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            self.logger.error(f"❌ Error calculating confidence score: {e}")
            return 0.5
    
    def _predict_performance(self, batch_size: int, metrics: SystemMetrics, 
                           state: SystemState) -> Dict[str, float]:
        """Predict expected performance for the given batch size."""
        try:
            # Base predictions
            expected_throughput = batch_size * 0.5  # requests per hour (rough estimate)
            expected_success_rate = 0.85
            expected_processing_time = batch_size * 2.0  # hours
            
            # Adjust based on system state
            if state == SystemState.BUSY:
                expected_success_rate *= 0.9
                expected_processing_time *= 1.2
            elif state == SystemState.SATURATED:
                expected_success_rate *= 0.8
                expected_processing_time *= 1.5
            elif state == SystemState.IDLE:
                expected_success_rate *= 1.1
                expected_processing_time *= 0.9
            
            # Adjust based on historical performance
            if metrics.success_rate > 0:
                expected_success_rate = (expected_success_rate + metrics.success_rate) / 2
            
            return {
                "throughput": expected_throughput,
                "success_rate": min(1.0, expected_success_rate),
                "processing_time": expected_processing_time,
                "efficiency": expected_throughput / max(1, batch_size)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error predicting performance: {e}")
            return {"throughput": 0.0, "success_rate": 0.5, "processing_time": 0.0, "efficiency": 0.0}
    
    def _assess_risk(self, batch_size: int, metrics: SystemMetrics, state: SystemState) -> str:
        """Assess risk level for the given batch size."""
        try:
            risk_score = 0.0
            
            # Risk from batch size
            if batch_size > 7:
                risk_score += 0.3
            elif batch_size > 4:
                risk_score += 0.1
            
            # Risk from system state
            if state == SystemState.SATURATED:
                risk_score += 0.4
            elif state == SystemState.BUSY:
                risk_score += 0.2
            
            # Risk from low success rate
            if metrics.success_rate < 0.7:
                risk_score += 0.3
            elif metrics.success_rate < 0.8:
                risk_score += 0.1
            
            # Risk from high utilization
            if metrics.capacity_utilization > 0.9:
                risk_score += 0.2
            
            if risk_score > 0.6:
                return "high"
            elif risk_score > 0.3:
                return "medium"
            else:
                return "low"
                
        except Exception as e:
            self.logger.error(f"❌ Error assessing risk: {e}")
            return "unknown"
    
    def _generate_alternatives(self, recommended_size: int, metrics: SystemMetrics, 
                             state: SystemState, available: int) -> List[Dict[str, Any]]:
        """Generate alternative batch size options."""
        try:
            alternatives = []
            
            # Conservative alternative
            if recommended_size > 1:
                conservative_size = max(1, recommended_size // 2)
                alternatives.append({
                    "batch_size": conservative_size,
                    "strategy": "conservative",
                    "confidence": 0.8,
                    "reasoning": "Lower risk, slower progress"
                })
            
            # Aggressive alternative
            if recommended_size < available and available > recommended_size:
                aggressive_size = min(available, recommended_size + 2)
                alternatives.append({
                    "batch_size": aggressive_size,
                    "strategy": "aggressive",
                    "confidence": 0.6,
                    "reasoning": "Higher throughput, increased risk"
                })
            
            # Single file alternative (safest)
            if recommended_size > 1:
                alternatives.append({
                    "batch_size": 1,
                    "strategy": "minimal_risk",
                    "confidence": 0.9,
                    "reasoning": "Minimal risk, guaranteed progress"
                })
            
            return alternatives
            
        except Exception as e:
            self.logger.error(f"❌ Error generating alternatives: {e}")
            return []
    
    def _generate_reasoning(self, batch_size: int, metrics: SystemMetrics, 
                          state: SystemState, strategy: OptimizationStrategy) -> str:
        """Generate human-readable reasoning for the recommendation."""
        try:
            reasoning_parts = []
            
            # System state reasoning
            if state == SystemState.IDLE:
                reasoning_parts.append("System has low utilization, can handle larger batches")
            elif state == SystemState.NORMAL:
                reasoning_parts.append("System operating normally, balanced approach recommended")
            elif state == SystemState.BUSY:
                reasoning_parts.append("System approaching capacity, conservative sizing advised")
            elif state == SystemState.SATURATED:
                reasoning_parts.append("System at capacity, waiting for slots to become available")
            
            # Strategy reasoning
            strategy_reasons = {
                OptimizationStrategy.CONSERVATIVE: "Using conservative approach to minimize risk",
                OptimizationStrategy.AGGRESSIVE: "Using aggressive approach to maximize throughput",
                OptimizationStrategy.BALANCED: "Using balanced approach for optimal efficiency",
                OptimizationStrategy.ADAPTIVE: "Using adaptive approach based on historical performance",
                OptimizationStrategy.PREDICTIVE: "Using predictive approach based on system trends"
            }
            reasoning_parts.append(strategy_reasons.get(strategy, "Using default optimization"))
            
            # Performance reasoning
            if metrics.success_rate > 0.9:
                reasoning_parts.append("High success rate supports larger batch sizes")
            elif metrics.success_rate < 0.7:
                reasoning_parts.append("Low success rate suggests smaller batch sizes")
            
            # Capacity reasoning
            available_slots = 10 - metrics.current_request_count
            if available_slots >= 5:
                reasoning_parts.append(f"Ample capacity available ({available_slots} slots)")
            elif available_slots >= 2:
                reasoning_parts.append(f"Moderate capacity available ({available_slots} slots)")
            else:
                reasoning_parts.append(f"Limited capacity available ({available_slots} slots)")
            
            return ". ".join(reasoning_parts) + "."
            
        except Exception as e:
            self.logger.error(f"❌ Error generating reasoning: {e}")
            return "Optimization calculation completed with default parameters."
    
    def optimize_batch_processing(self) -> OptimizationResult:
        """
        Run complete batch optimization analysis.
        
        Returns:
            OptimizationResult with recommendations
        """
        try:
            # Collect current metrics
            metrics = self.collect_system_metrics()
            
            # Classify system state
            system_state = self.classify_system_state(metrics)
            
            # Store metrics history
            with self.optimizer_lock:
                self.system_metrics_history.append(metrics)
            
            # Determine optimization strategy
            if self.config.strategy == OptimizationStrategy.ADAPTIVE:
                strategy = self._select_adaptive_strategy(metrics, system_state)
            else:
                strategy = self.config.strategy
            
            # Calculate optimal batch size
            result = self.calculate_optimal_batch_size(metrics, system_state, strategy)
            
            # Store optimization result
            with self.optimizer_lock:
                self.optimization_results.append(result)
            
            self.logger.info(f"🎯 Optimization complete: {result.recommended_batch_size} files "
                           f"({result.optimization_strategy.value}, confidence: {result.confidence_score:.2f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error in batch optimization: {e}")
            return OptimizationResult(
                recommended_batch_size=1,
                confidence_score=0.5,
                optimization_strategy=OptimizationStrategy.CONSERVATIVE,
                reasoning=f"Error in optimization: {str(e)}",
                expected_performance={"throughput": 0.0, "success_rate": 0.5},
                risk_assessment="unknown",
                alternative_options=[]
            )
    
    def _select_adaptive_strategy(self, metrics: SystemMetrics, state: SystemState) -> OptimizationStrategy:
        """Select the best strategy based on current conditions and historical performance."""
        try:
            # If no historical data, use balanced approach
            if not self.strategy_performance or all(not perf for perf in self.strategy_performance.values()):
                return OptimizationStrategy.BALANCED
            
            # Calculate performance scores for each strategy
            strategy_scores = {}
            for strategy, performances in self.strategy_performance.items():
                if performances:
                    avg_performance = statistics.mean(performances[-10:])  # Last 10 results
                    strategy_scores[strategy] = avg_performance
            
            if not strategy_scores:
                return OptimizationStrategy.BALANCED
            
            # Select best performing strategy, but consider system state
            best_strategy = max(strategy_scores, key=strategy_scores.get)
            
            # Override based on system state if needed
            if state == SystemState.SATURATED:
                return OptimizationStrategy.CONSERVATIVE
            elif state == SystemState.IDLE and metrics.available_files > 5:
                return OptimizationStrategy.AGGRESSIVE
            
            return best_strategy
            
        except Exception as e:
            self.logger.error(f"❌ Error selecting adaptive strategy: {e}")
            return OptimizationStrategy.BALANCED
    
    def record_performance(self, batch_size: int, processing_time: float, 
                         success_rate: float, strategy: OptimizationStrategy):
        """
        Record performance results for learning and adaptation.
        
        Args:
            batch_size: Size of the processed batch
            processing_time: Time taken to process the batch
            success_rate: Success rate of the batch
            strategy: Strategy used for the batch
        """
        try:
            # Get current metrics for context
            metrics = self.collect_system_metrics()
            system_state = self.classify_system_state(metrics)
            
            # Calculate actual throughput
            actual_throughput = (batch_size / max(processing_time, 0.1)) * 3600  # per hour
            
            # Predict what throughput should have been
            expected_perf = self._predict_performance(batch_size, metrics, system_state)
            predicted_throughput = expected_perf.get("throughput", 0.0)
            
            # Create performance record
            performance_record = PerformanceHistory(
                timestamp=datetime.now().isoformat(),
                batch_size=batch_size,
                processing_time=processing_time,
                success_rate=success_rate,
                system_state=system_state,
                optimization_strategy=strategy,
                actual_throughput=actual_throughput,
                predicted_throughput=predicted_throughput
            )
            
            # Store performance data
            with self.optimizer_lock:
                self.performance_history.append(performance_record)
                
                # Update strategy performance tracking
                performance_score = (success_rate * 0.5) + (min(actual_throughput / max(predicted_throughput, 0.1), 2.0) * 0.5)
                self.strategy_performance[strategy].append(performance_score)
                
                # Keep only recent performance data
                if len(self.strategy_performance[strategy]) > 50:
                    self.strategy_performance[strategy] = self.strategy_performance[strategy][-50:]
            
            self.logger.debug(f"📊 Performance recorded: batch={batch_size}, time={processing_time:.2f}s, "
                            f"success={success_rate:.2f}, throughput={actual_throughput:.2f}/hr")
            
        except Exception as e:
            self.logger.error(f"❌ Error recording performance: {e}")
    
    def get_optimization_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive optimization analytics and insights.
        
        Returns:
            Dictionary with optimization analytics
        """
        try:
            with self.optimizer_lock:
                # Performance summary
                if not self.performance_history:
                    return {"message": "No performance data available", "generated_at": datetime.now().isoformat()}
                
                recent_performance = list(self.performance_history)[-20:]
                
                # Calculate summary statistics
                avg_batch_size = statistics.mean([p.batch_size for p in recent_performance])
                avg_processing_time = statistics.mean([p.processing_time for p in recent_performance])
                avg_success_rate = statistics.mean([p.success_rate for p in recent_performance])
                avg_throughput = statistics.mean([p.actual_throughput for p in recent_performance])
                
                # Strategy performance analysis
                strategy_analysis = {}
                for strategy, performances in self.strategy_performance.items():
                    if performances:
                        strategy_analysis[strategy.value] = {
                            "average_performance": statistics.mean(performances),
                            "best_performance": max(performances),
                            "worst_performance": min(performances),
                            "total_uses": len(performances),
                            "recent_trend": "improving" if len(performances) > 5 and
                                          statistics.mean(performances[-5:]) > statistics.mean(performances[-10:-5]) else "stable"
                        }
                
                # System state analysis
                state_distribution = {}
                for record in recent_performance:
                    state = record.system_state.value
                    state_distribution[state] = state_distribution.get(state, 0) + 1
                
                # Optimization results analysis
                recent_optimizations = list(self.optimization_results)[-10:]
                if recent_optimizations:
                    avg_confidence = statistics.mean([r.confidence_score for r in recent_optimizations])
                    risk_distribution = {}
                    for result in recent_optimizations:
                        risk = result.risk_assessment
                        risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
                else:
                    avg_confidence = 0.0
                    risk_distribution = {}
                
                return {
                    "performance_summary": {
                        "average_batch_size": avg_batch_size,
                        "average_processing_time": avg_processing_time,
                        "average_success_rate": avg_success_rate,
                        "average_throughput": avg_throughput,
                        "total_batches_processed": len(self.performance_history)
                    },
                    "strategy_analysis": strategy_analysis,
                    "system_state_distribution": state_distribution,
                    "optimization_confidence": avg_confidence,
                    "risk_distribution": risk_distribution,
                    "current_strategy": self.current_strategy.value,
                    "adaptive_weights": self.adaptive_weights,
                    "configuration": asdict(self.config),
                    "generated_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting optimization analytics: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}
    
    def start_optimization_monitoring(self):
        """Start continuous optimization monitoring."""
        try:
            if self.optimization_active:
                self.logger.warning("⚠️ Optimization monitoring is already active")
                return
            
            def optimization_loop():
                self.logger.info(f"🚀 Batch optimization monitoring started (interval: {self.config.optimization_interval}s)")
                
                while self.optimization_active:
                    try:
                        # Run optimization analysis
                        result = self.optimize_batch_processing()
                        
                        # Log results
                        self.logger.debug(f"🎯 Optimization cycle: {result.recommended_batch_size} files recommended "
                                        f"({result.optimization_strategy.value}, confidence: {result.confidence_score:.2f})")
                        
                        # Wait for next cycle
                        time.sleep(self.config.optimization_interval)
                        
                    except Exception as e:
                        self.logger.error(f"❌ Error in optimization loop: {e}")
                        time.sleep(min(self.config.optimization_interval, 60))
                
                self.logger.info("🛑 Batch optimization monitoring stopped")
            
            self.optimization_active = True
            self.optimization_thread = threading.Thread(target=optimization_loop, daemon=True)
            self.optimization_thread.start()
            
            self.logger.info("✅ Batch optimization monitoring started")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start optimization monitoring: {e}")
    
    def stop_optimization_monitoring(self):
        """Stop continuous optimization monitoring."""
        try:
            if not self.optimization_active:
                return
            
            self.logger.info("🛑 Stopping batch optimization monitoring...")
            self.optimization_active = False
            
            if self.optimization_thread and self.optimization_thread.is_alive():
                self.optimization_thread.join(timeout=10)
            
            self.logger.info("✅ Batch optimization monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping optimization monitoring: {e}")
    
    def get_current_recommendation(self) -> OptimizationResult:
        """
        Get current batch size recommendation.
        
        Returns:
            OptimizationResult with current recommendation
        """
        return self.optimize_batch_processing()
    
    def cleanup(self):
        """Clean up the batch optimizer."""
        self.logger.info("🧹 Cleaning up BatchOptimizer...")
        
        # Stop monitoring
        self.stop_optimization_monitoring()
        
        # Clear data structures
        with self.optimizer_lock:
            self.performance_history.clear()
            self.system_metrics_history.clear()
            self.optimization_results.clear()
            for strategy_list in self.strategy_performance.values():
                strategy_list.clear()
        
        self.logger.info("✅ BatchOptimizer cleanup completed")


def create_batch_optimizer(config: Optional[OptimizationConfig] = None,
                          capacity_manager: Optional[CapacityManager] = None,
                          enhanced_monitor: Optional[EnhancedRequestMonitor] = None,
                          dynamic_trigger: Optional[DynamicTriggerSystem] = None) -> BatchOptimizer:
    """
    Factory function to create a BatchOptimizer.
    
    Args:
        config: Optimization configuration
        capacity_manager: Capacity manager for system state
        enhanced_monitor: Enhanced request monitor for metrics
        dynamic_trigger: Dynamic trigger system for coordination
        
    Returns:
        BatchOptimizer instance
    """
    return BatchOptimizer(
        config=config,
        capacity_manager=capacity_manager,
        enhanced_monitor=enhanced_monitor,
        dynamic_trigger=dynamic_trigger
    )


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch Optimizer')
    parser.add_argument('--start-monitoring', action='store_true',
                       help='Start optimization monitoring')
    parser.add_argument('--single-optimization', action='store_true',
                       help='Run single optimization cycle')
    parser.add_argument('--analytics', action='store_true',
                       help='Show optimization analytics')
    parser.add_argument('--test-strategies', action='store_true',
                       help='Test different optimization strategies')
    
    args = parser.parse_args()
    
    # Create batch optimizer
    optimizer = create_batch_optimizer()
    
    try:
        if args.start_monitoring:
            print("=== Starting Batch Optimization Monitoring ===")
            optimizer.start_optimization_monitoring()
            
            # Keep running until interrupted
            try:
                while optimizer.optimization_active:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping optimization monitoring...")
                optimizer.stop_optimization_monitoring()
        
        elif args.single_optimization:
            print("=== Running Single Optimization Cycle ===")
            result = optimizer.optimize_batch_processing()
            print(json.dumps(asdict(result), indent=2))
        
        elif args.analytics:
            print("=== Optimization Analytics ===")
            analytics = optimizer.get_optimization_analytics()
            print(json.dumps(analytics, indent=2))
        
        elif args.test_strategies:
            print("=== Testing Optimization Strategies ===")
            
            # Create test metrics
            test_metrics = SystemMetrics(
                current_request_count=5,
                average_processing_time=2.0,
                success_rate=0.85,
                throughput_rate=2.5,
                capacity_utilization=0.5,
                error_rate=0.15,
                queue_length=3,
                available_files=10,
                timestamp=datetime.now().isoformat()
            )
            
            system_state = optimizer.classify_system_state(test_metrics)
            
            # Test each strategy
            for strategy in OptimizationStrategy:
                result = optimizer.calculate_optimal_batch_size(test_metrics, system_state, strategy)
                print(f"\n{strategy.value.upper()}:")
                print(f"  Recommended batch size: {result.recommended_batch_size}")
                print(f"  Confidence: {result.confidence_score:.2f}")
                print(f"  Risk: {result.risk_assessment}")
                print(f"  Reasoning: {result.reasoning}")
        
        else:
            parser.print_help()
            print("\n" + "="*60)
            print("BATCH OPTIMIZER EXAMPLES")
            print("="*60)
            print("# Start optimization monitoring:")
            print("python automation/batch_optimizer.py --start-monitoring")
            print("\n# Run single optimization:")
            print("python automation/batch_optimizer.py --single-optimization")
            print("\n# Show analytics:")
            print("python automation/batch_optimizer.py --analytics")
            print("\n# Test strategies:")
            print("python automation/batch_optimizer.py --test-strategies")
            print("="*60)
            
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(optimizer, 'optimization_active') and optimizer.optimization_active:
            optimizer.stop_optimization_monitoring()
    finally:
        optimizer.cleanup()