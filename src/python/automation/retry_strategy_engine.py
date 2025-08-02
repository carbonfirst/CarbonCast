#!/usr/bin/env python3
"""
Retry Strategy Engine for Smart Retry System

This module provides intelligent retry strategies with adaptive algorithms for
determining optimal retry timing, eligibility, and success probability based
on error types, patterns, and historical data.

Key Features:
- Multiple retry strategies (exponential backoff, linear, adaptive)
- Error-type specific retry logic
- Dynamic delay calculation with jitter
- Success probability estimation
- Retry eligibility determination
- Historical pattern analysis
- Rate limiting integration
"""

import math
import random
import time
import logging
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import threading


class RetryStrategy(Enum):
    """Enumeration of available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    ADAPTIVE_BACKOFF = "adaptive_backoff"
    FIXED_INTERVAL = "fixed_interval"
    FIBONACCI_BACKOFF = "fibonacci_backoff"
    CUSTOM = "custom"


class ErrorSeverity(Enum):
    """Error severity levels for retry strategy selection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for specialized retry handling."""
    TRANSIENT = "transient"
    PERSISTENT = "persistent"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    RESOURCE = "resource"
    VALIDATION = "validation"
    SYSTEM = "system"


@dataclass
class RetryContext:
    """Context information for retry decision making."""
    request_id: str
    error_type: str
    error_category: ErrorCategory
    error_severity: ErrorSeverity
    error_message: str
    attempt_number: int
    max_attempts: int
    region: Optional[str] = None
    variable_type: Optional[str] = None
    file_path: Optional[str] = None
    last_attempt_time: Optional[str] = None
    historical_success_rate: float = 0.5
    system_load: float = 0.5
    capacity_available: int = 10
    priority_level: int = 5
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RetryDecision:
    """Decision result from retry strategy engine."""
    should_retry: bool
    delay_seconds: int
    next_retry_time: str
    strategy_used: RetryStrategy
    success_probability: float
    eligibility_score: float
    reasoning: str
    conditions: List[str]
    metadata: Dict[str, Any]
    created_at: str


@dataclass
class StrategyConfig:
    """Configuration for retry strategies."""
    base_delay: int = 60
    max_delay: int = 3600
    multiplier: float = 2.0
    jitter_factor: float = 0.1
    max_jitter: int = 30
    success_threshold: float = 0.3
    eligibility_threshold: float = 0.5
    capacity_threshold: int = 8
    rate_limit_factor: float = 1.5
    adaptive_learning_rate: float = 0.1
    fibonacci_max_index: int = 10


class RetryStrategyEngine:
    """
    Intelligent retry strategy engine that determines optimal retry timing
    and eligibility based on error patterns, system state, and historical data.
    """
    
    def __init__(self, db_path: str = "src/python/data/automation_state.db",
                 config: Optional[StrategyConfig] = None):
        """
        Initialize the retry strategy engine.
        
        Args:
            db_path: Path to the SQLite database
            config: Strategy configuration (uses defaults if None)
        """
        self.db_path = db_path
        self.config = config or StrategyConfig()
        self.logger = self._setup_logging()
        
        # Strategy mappings
        self.strategy_map = {
            RetryStrategy.EXPONENTIAL_BACKOFF: self._exponential_backoff,
            RetryStrategy.LINEAR_BACKOFF: self._linear_backoff,
            RetryStrategy.ADAPTIVE_BACKOFF: self._adaptive_backoff,
            RetryStrategy.FIXED_INTERVAL: self._fixed_interval,
            RetryStrategy.FIBONACCI_BACKOFF: self._fibonacci_backoff
        }
        
        # Error category to strategy mapping
        self.category_strategy_map = {
            ErrorCategory.TRANSIENT: RetryStrategy.EXPONENTIAL_BACKOFF,
            ErrorCategory.NETWORK: RetryStrategy.EXPONENTIAL_BACKOFF,
            ErrorCategory.RATE_LIMIT: RetryStrategy.LINEAR_BACKOFF,
            ErrorCategory.RESOURCE: RetryStrategy.ADAPTIVE_BACKOFF,
            ErrorCategory.AUTHENTICATION: RetryStrategy.FIXED_INTERVAL,
            ErrorCategory.PERSISTENT: RetryStrategy.FIBONACCI_BACKOFF,
            ErrorCategory.VALIDATION: RetryStrategy.FIXED_INTERVAL,
            ErrorCategory.SYSTEM: RetryStrategy.ADAPTIVE_BACKOFF
        }
        
        # Fibonacci sequence cache
        self._fibonacci_cache = [1, 1]
        
        # Threading
        self.strategy_lock = threading.Lock()
        
        self.logger.info("Retry Strategy Engine initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the strategy engine."""
        logger = logging.getLogger('smart_retry.strategy_engine')
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
        return logger
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def determine_retry_strategy(self, context: RetryContext) -> RetryStrategy:
        """
        Determine the optimal retry strategy based on context.
        
        Args:
            context: Retry context information
            
        Returns:
            Optimal retry strategy for the given context
        """
        try:
            # Primary strategy selection based on error category
            primary_strategy = self.category_strategy_map.get(
                context.error_category, 
                RetryStrategy.EXPONENTIAL_BACKOFF
            )
            
            # Adjust strategy based on severity and system state
            if context.error_severity == ErrorSeverity.CRITICAL:
                # Critical errors get more aggressive retry
                if primary_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                    primary_strategy = RetryStrategy.LINEAR_BACKOFF
            elif context.error_severity == ErrorSeverity.LOW:
                # Low severity errors can use gentler strategies
                if primary_strategy == RetryStrategy.LINEAR_BACKOFF:
                    primary_strategy = RetryStrategy.EXPONENTIAL_BACKOFF
            
            # Consider system load and capacity
            if context.system_load > 0.8 or context.capacity_available <= 2:
                # High load - use more conservative strategies
                if primary_strategy in [RetryStrategy.LINEAR_BACKOFF, RetryStrategy.FIXED_INTERVAL]:
                    primary_strategy = RetryStrategy.EXPONENTIAL_BACKOFF
            
            # Historical success rate influence
            if context.historical_success_rate < 0.2:
                # Very low success rate - try adaptive strategy
                primary_strategy = RetryStrategy.ADAPTIVE_BACKOFF
            elif context.historical_success_rate > 0.8:
                # High success rate - can be more aggressive
                if primary_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                    primary_strategy = RetryStrategy.LINEAR_BACKOFF
            
            self.logger.debug(f"Selected strategy {primary_strategy.value} for {context.error_category.value} error")
            return primary_strategy
            
        except Exception as e:
            self.logger.error(f"Error determining retry strategy: {e}")
            return RetryStrategy.EXPONENTIAL_BACKOFF
    
    def calculate_retry_delay(self, context: RetryContext, strategy: RetryStrategy) -> int:
        """
        Calculate retry delay using the specified strategy.
        
        Args:
            context: Retry context information
            strategy: Retry strategy to use
            
        Returns:
            Delay in seconds before next retry
        """
        try:
            # Get base calculation from strategy
            strategy_func = self.strategy_map.get(strategy, self._exponential_backoff)
            base_delay = strategy_func(context)
            
            # Apply error-category specific multipliers
            category_multipliers = {
                ErrorCategory.RATE_LIMIT: 2.0,
                ErrorCategory.AUTHENTICATION: 1.5,
                ErrorCategory.RESOURCE: 1.3,
                ErrorCategory.NETWORK: 1.2,
                ErrorCategory.TRANSIENT: 1.0,
                ErrorCategory.PERSISTENT: 1.8,
                ErrorCategory.VALIDATION: 0.8,
                ErrorCategory.SYSTEM: 1.4
            }
            
            multiplier = category_multipliers.get(context.error_category, 1.0)
            adjusted_delay = int(base_delay * multiplier)
            
            # Apply severity adjustments
            severity_adjustments = {
                ErrorSeverity.LOW: 0.8,
                ErrorSeverity.MEDIUM: 1.0,
                ErrorSeverity.HIGH: 1.2,
                ErrorSeverity.CRITICAL: 0.7  # Critical errors retry faster
            }
            
            severity_factor = severity_adjustments.get(context.error_severity, 1.0)
            adjusted_delay = int(adjusted_delay * severity_factor)
            
            # Apply system load factor
            if context.system_load > 0.7:
                load_factor = 1.0 + (context.system_load - 0.7) * 2
                adjusted_delay = int(adjusted_delay * load_factor)
            
            # Apply capacity constraints
            if context.capacity_available <= 3:
                capacity_factor = 1.5 + (3 - context.capacity_available) * 0.5
                adjusted_delay = int(adjusted_delay * capacity_factor)
            
            # Add jitter to prevent thundering herd
            jitter = self._calculate_jitter(adjusted_delay)
            final_delay = max(self.config.base_delay, adjusted_delay + jitter)
            final_delay = min(final_delay, self.config.max_delay)
            
            self.logger.debug(f"Calculated delay: base={base_delay}, adjusted={adjusted_delay}, "
                            f"final={final_delay} (strategy={strategy.value})")
            
            return final_delay
            
        except Exception as e:
            self.logger.error(f"Error calculating retry delay: {e}")
            return self.config.base_delay
    
    def _exponential_backoff(self, context: RetryContext) -> int:
        """Calculate exponential backoff delay."""
        return int(self.config.base_delay * (self.config.multiplier ** (context.attempt_number - 1)))
    
    def _linear_backoff(self, context: RetryContext) -> int:
        """Calculate linear backoff delay."""
        return self.config.base_delay * context.attempt_number
    
    def _adaptive_backoff(self, context: RetryContext) -> int:
        """Calculate adaptive backoff based on historical success rate."""
        # Adaptive factor based on success rate
        success_factor = 1.0 - context.historical_success_rate
        adaptive_multiplier = 1.0 + (success_factor * 2.0)  # Range: 1.0 to 3.0
        
        # Base exponential with adaptive adjustment
        base_delay = self.config.base_delay * (self.config.multiplier ** (context.attempt_number - 1))
        return int(base_delay * adaptive_multiplier)
    
    def _fixed_interval(self, context: RetryContext) -> int:
        """Calculate fixed interval delay."""
        return self.config.base_delay
    
    def _fibonacci_backoff(self, context: RetryContext) -> int:
        """Calculate Fibonacci sequence backoff delay."""
        fib_index = min(context.attempt_number, self.config.fibonacci_max_index)
        fib_value = self._get_fibonacci(fib_index)
        return self.config.base_delay * fib_value
    
    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number with caching."""
        while len(self._fibonacci_cache) <= n:
            next_fib = self._fibonacci_cache[-1] + self._fibonacci_cache[-2]
            self._fibonacci_cache.append(next_fib)
        return self._fibonacci_cache[n]
    
    def _calculate_jitter(self, base_delay: int) -> int:
        """Calculate jitter to add to delay."""
        max_jitter = min(
            int(base_delay * self.config.jitter_factor),
            self.config.max_jitter
        )
        return random.randint(-max_jitter, max_jitter)
    
    def estimate_success_probability(self, context: RetryContext) -> float:
        """
        Estimate the probability of success for a retry attempt.
        
        Args:
            context: Retry context information
            
        Returns:
            Estimated success probability (0.0 to 1.0)
        """
        try:
            # Base probability from historical data
            base_probability = context.historical_success_rate
            
            # Adjust based on attempt number (generally decreases with attempts)
            attempt_factor = 1.0 / (1.0 + (context.attempt_number - 1) * 0.2)
            
            # Error category influence
            category_factors = {
                ErrorCategory.TRANSIENT: 0.8,      # High chance of recovery
                ErrorCategory.NETWORK: 0.7,        # Good chance of recovery
                ErrorCategory.RATE_LIMIT: 0.9,     # Very high chance after delay
                ErrorCategory.RESOURCE: 0.6,       # Moderate chance
                ErrorCategory.AUTHENTICATION: 0.3, # Low chance without intervention
                ErrorCategory.PERSISTENT: 0.4,     # Low chance
                ErrorCategory.VALIDATION: 0.2,     # Very low chance
                ErrorCategory.SYSTEM: 0.5          # Moderate chance
            }
            
            category_factor = category_factors.get(context.error_category, 0.5)
            
            # System state influence
            system_factor = 1.0 - (context.system_load * 0.3)  # High load reduces success
            capacity_factor = min(1.0, context.capacity_available / 5.0)  # Low capacity reduces success
            
            # Priority influence (higher priority gets slight boost)
            priority_factor = 1.0 + ((10 - context.priority_level) * 0.02)
            
            # Combine all factors
            estimated_probability = (
                base_probability * 
                attempt_factor * 
                category_factor * 
                system_factor * 
                capacity_factor * 
                priority_factor
            )
            
            # Clamp to valid range
            estimated_probability = max(0.0, min(1.0, estimated_probability))
            
            self.logger.debug(f"Success probability: {estimated_probability:.3f} "
                            f"(base={base_probability:.3f}, attempt={attempt_factor:.3f}, "
                            f"category={category_factor:.3f})")
            
            return estimated_probability
            
        except Exception as e:
            self.logger.error(f"Error estimating success probability: {e}")
            return 0.5
    
    def calculate_eligibility_score(self, context: RetryContext) -> float:
        """
        Calculate eligibility score for retry queue prioritization.
        
        Args:
            context: Retry context information
            
        Returns:
            Eligibility score (0.0 to 1.0, higher is better)
        """
        try:
            # Base score from success probability
            success_prob = self.estimate_success_probability(context)
            base_score = success_prob
            
            # Priority influence (higher priority = higher score)
            priority_score = (10 - context.priority_level) / 10.0
            
            # Attempt number influence (fewer attempts = higher score)
            attempt_score = max(0.1, 1.0 - ((context.attempt_number - 1) / context.max_attempts))
            
            # Error severity influence
            severity_scores = {
                ErrorSeverity.CRITICAL: 1.0,
                ErrorSeverity.HIGH: 0.8,
                ErrorSeverity.MEDIUM: 0.6,
                ErrorSeverity.LOW: 0.4
            }
            severity_score = severity_scores.get(context.error_severity, 0.6)
            
            # Time since last attempt (longer wait = higher score)
            time_score = 1.0
            if context.last_attempt_time:
                try:
                    last_time = datetime.fromisoformat(context.last_attempt_time.replace('Z', '+00:00'))
                    time_diff = (datetime.now() - last_time.replace(tzinfo=None)).total_seconds()
                    # Score increases with time, maxing out at 1 hour
                    time_score = min(1.0, time_diff / 3600.0)
                except Exception:
                    pass
            
            # Combine scores with weights
            weights = {
                'success': 0.3,
                'priority': 0.25,
                'attempt': 0.2,
                'severity': 0.15,
                'time': 0.1
            }
            
            eligibility_score = (
                base_score * weights['success'] +
                priority_score * weights['priority'] +
                attempt_score * weights['attempt'] +
                severity_score * weights['severity'] +
                time_score * weights['time']
            )
            
            # Clamp to valid range
            eligibility_score = max(0.0, min(1.0, eligibility_score))
            
            self.logger.debug(f"Eligibility score: {eligibility_score:.3f} "
                            f"(success={base_score:.3f}, priority={priority_score:.3f}, "
                            f"attempt={attempt_score:.3f})")
            
            return eligibility_score
            
        except Exception as e:
            self.logger.error(f"Error calculating eligibility score: {e}")
            return 0.5
    
    def should_retry(self, context: RetryContext) -> bool:
        """
        Determine if a request should be retried based on context.
        
        Args:
            context: Retry context information
            
        Returns:
            True if request should be retried, False otherwise
        """
        try:
            # Check basic retry limits
            if context.attempt_number >= context.max_attempts:
                self.logger.debug(f"Max attempts reached: {context.attempt_number}/{context.max_attempts}")
                return False
            
            # Check success probability threshold
            success_prob = self.estimate_success_probability(context)
            if success_prob < self.config.success_threshold:
                self.logger.debug(f"Success probability too low: {success_prob:.3f} < {self.config.success_threshold}")
                return False
            
            # Check eligibility score threshold
            eligibility_score = self.calculate_eligibility_score(context)
            if eligibility_score < self.config.eligibility_threshold:
                self.logger.debug(f"Eligibility score too low: {eligibility_score:.3f} < {self.config.eligibility_threshold}")
                return False
            
            # Check system capacity
            if context.capacity_available <= 1:
                self.logger.debug(f"Insufficient capacity: {context.capacity_available}")
                return False
            
            # Error category specific rules
            if context.error_category == ErrorCategory.VALIDATION:
                # Validation errors rarely succeed on retry without changes
                return success_prob > 0.7
            
            if context.error_category == ErrorCategory.AUTHENTICATION:
                # Auth errors need manual intervention usually
                return success_prob > 0.6
            
            self.logger.debug(f"Retry approved: success_prob={success_prob:.3f}, "
                            f"eligibility={eligibility_score:.3f}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error determining retry eligibility: {e}")
            return False
    
    def create_retry_decision(self, context: RetryContext) -> RetryDecision:
        """
        Create a comprehensive retry decision based on context.
        
        Args:
            context: Retry context information
            
        Returns:
            Complete retry decision with timing and reasoning
        """
        try:
            # Determine if we should retry
            should_retry = self.should_retry(context)
            
            if not should_retry:
                return RetryDecision(
                    should_retry=False,
                    delay_seconds=0,
                    next_retry_time="",
                    strategy_used=RetryStrategy.EXPONENTIAL_BACKOFF,
                    success_probability=0.0,
                    eligibility_score=0.0,
                    reasoning="Retry not recommended based on context analysis",
                    conditions=[],
                    metadata={},
                    created_at=datetime.now().isoformat()
                )
            
            # Determine strategy and calculate delay
            strategy = self.determine_retry_strategy(context)
            delay_seconds = self.calculate_retry_delay(context, strategy)
            next_retry_time = (datetime.now() + timedelta(seconds=delay_seconds)).isoformat()
            
            # Calculate probabilities and scores
            success_probability = self.estimate_success_probability(context)
            eligibility_score = self.calculate_eligibility_score(context)
            
            # Build reasoning
            reasoning_parts = [
                f"Strategy: {strategy.value}",
                f"Success probability: {success_probability:.3f}",
                f"Eligibility score: {eligibility_score:.3f}",
                f"Attempt {context.attempt_number}/{context.max_attempts}"
            ]
            reasoning = "; ".join(reasoning_parts)
            
            # Build conditions
            conditions = []
            if context.capacity_available <= self.config.capacity_threshold:
                conditions.append(f"Low capacity: {context.capacity_available}")
            if context.system_load > 0.7:
                conditions.append(f"High system load: {context.system_load:.2f}")
            if context.error_category in [ErrorCategory.RATE_LIMIT, ErrorCategory.RESOURCE]:
                conditions.append(f"Resource constraint: {context.error_category.value}")
            
            # Build metadata
            metadata = {
                'strategy_details': {
                    'base_delay': self.config.base_delay,
                    'calculated_delay': delay_seconds,
                    'jitter_applied': True,
                    'multiplier_used': self.config.multiplier
                },
                'context_factors': {
                    'error_category': context.error_category.value,
                    'error_severity': context.error_severity.value,
                    'system_load': context.system_load,
                    'capacity_available': context.capacity_available,
                    'historical_success_rate': context.historical_success_rate
                },
                'decision_factors': {
                    'success_threshold': self.config.success_threshold,
                    'eligibility_threshold': self.config.eligibility_threshold,
                    'capacity_threshold': self.config.capacity_threshold
                }
            }
            
            decision = RetryDecision(
                should_retry=True,
                delay_seconds=delay_seconds,
                next_retry_time=next_retry_time,
                strategy_used=strategy,
                success_probability=success_probability,
                eligibility_score=eligibility_score,
                reasoning=reasoning,
                conditions=conditions,
                metadata=metadata,
                created_at=datetime.now().isoformat()
            )
            
            self.logger.info(f"Retry decision created: {reasoning}")
            return decision
            
        except Exception as e:
            self.logger.error(f"Error creating retry decision: {e}")
            return RetryDecision(
                should_retry=False,
                delay_seconds=0,
                next_retry_time="",
                strategy_used=RetryStrategy.EXPONENTIAL_BACKOFF,
                success_probability=0.0,
                eligibility_score=0.0,
                reasoning=f"Error in decision making: {str(e)}",
                conditions=[],
                metadata={'error': str(e)},
                created_at=datetime.now().isoformat()
            )
    
    def get_strategy_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about strategy usage and effectiveness.
        
        Returns:
            Dictionary containing strategy statistics
        """
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get strategy usage from retry queue
                cursor.execute("""
                    SELECT retry_strategy, COUNT(*) as usage_count,
                           AVG(success_probability) as avg_success_prob,
                           AVG(eligibility_score) as avg_eligibility
                    FROM retry_queue 
                    GROUP BY retry_strategy
                """)
                
                strategy_stats = {}
                for row in cursor.fetchall():
                    strategy_stats[row['retry_strategy']] = {
                        'usage_count': row['usage_count'],
                        'avg_success_probability': row['avg_success_prob'] or 0.0,
                        'avg_eligibility_score': row['avg_eligibility'] or 0.0
                    }
                
                # Get overall statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_decisions,
                        AVG(success_probability) as avg_success_prob,
                        AVG(eligibility_score) as avg_eligibility,
                        AVG(current_delay_seconds) as avg_delay
                    FROM retry_queue
                """)
                
                overall_stats = cursor.fetchone()
                
                return {
                    'strategy_usage': strategy_stats,
                    'overall_statistics': {
                        'total_decisions': overall_stats['total_decisions'] or 0,
                        'average_success_probability': overall_stats['avg_success_prob'] or 0.0,
                        'average_eligibility_score': overall_stats['avg_eligibility'] or 0.0,
                        'average_delay_seconds': overall_stats['avg_delay'] or 0.0
                    },
                    'configuration': asdict(self.config),
                    'available_strategies': [s.value for s in RetryStrategy],
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting strategy statistics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }


def create_retry_strategy_engine(db_path: str = "src/python/data/automation_state.db",
                               config: Optional[StrategyConfig] = None) -> RetryStrategyEngine:
    """
    Factory function to create a Retry Strategy Engine.
    
    Args:
        db_path: Path to the SQLite database
        config: Strategy configuration (uses defaults if None)
        
    Returns:
        Configured RetryStrategyEngine instance
    """
    return RetryStrategyEngine(db_path, config)


if __name__ == "__main__":
    # Example usage and testing
    import argparse
    
    parser = argparse.ArgumentParser(description='Retry Strategy Engine')
    parser.add_argument('--test-strategies', action='store_true',
                       help='Test different retry strategies')
    parser.add_argument('--statistics', action='store_true',
                       help='Show strategy statistics')
    parser.add_argument('--db-path', default='src/python/data/automation_state.db',
                       help='Database path')
    
    args = parser.parse_args()
    
    # Create strategy engine
    engine = create_retry_strategy_engine(args.db_path)
    
    try:
        if args.test_strategies:
            print("=== Testing Retry Strategies ===")
            
            # Create test context
            test_context = RetryContext(
                request_id="test_001",
                error_type="HTTP_500",
                error_category=ErrorCategory.TRANSIENT,
                error_severity=ErrorSeverity.MEDIUM,
                error_message="Internal server error",
                attempt_number=2,
                max_attempts=5,
                region="CISO",
                variable_type="dswrf",
                historical_success_rate=0.7,
                system_load=0.5,
                capacity_available=6,
                priority_level=3
            )
            
            # Test decision making
            decision = engine.create_retry_decision(test_context)
            print(f"Retry Decision: {decision.should_retry}")
            print(f"Strategy: {decision.strategy_used.value}")
            print(f"Delay: {decision.delay_seconds} seconds")
            print(f"Success Probability: {decision.success_probability:.3f}")
            print(f"Eligibility Score: {decision.eligibility_score:.3f}")
            print(f"Reasoning: {decision.reasoning}")
            
        elif args.statistics:
            print("=== Strategy Statistics ===")
            stats = engine.get_strategy_statistics()
            print(json.dumps(stats, indent=2))
            
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Error: {e}")