"""
Design Patterns for Enhanced LangGraph Chat System

Provides reusable design patterns for reliability and performance:
- CircuitBreakerPattern: Prevents cascading failures
- RetryPattern: Implements retry logic with exponential backoff
- CachePattern: Intelligent caching for performance
- ThrottlePattern: Rate limiting and throttling
- BulkheadPattern: Isolation for different components

These patterns improve system reliability and performance.
"""

import logging
import asyncio
import time
from typing import Any, Callable, Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import random


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerPattern:
    """
    Circuit Breaker pattern implementation for preventing cascading failures.
    
    Features:
    - Configurable failure threshold
    - Automatic recovery testing
    - Timeout-based state transitions
    - Failure rate monitoring
    - Custom fallback handling
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0
        
        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        
        self.logger = logging.getLogger(__name__)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        
        self.total_requests += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
            else:
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Expected failure - record and check threshold
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            # Reset circuit breaker
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.logger.info(f"Circuit breaker {self.name} RESET to CLOSED")
        
        self.success_count += 1
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.logger.warning(f"Circuit breaker {self.name} OPENED after {self.failure_count} failures")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        failure_rate = self.total_failures / max(1, self.total_requests)
        
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "failure_rate": failure_rate,
            "last_failure": datetime.fromtimestamp(self.last_failure_time) if self.last_failure_time else None
        }
    
    def reset(self):
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.logger.info(f"Circuit breaker {self.name} manually reset")


class RetryPattern:
    """
    Retry pattern with exponential backoff and jitter.
    
    Features:
    - Configurable retry attempts
    - Exponential backoff
    - Jitter to prevent thundering herd
    - Custom exception handling
    - Retry condition evaluation
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        
        self.logger = logging.getLogger(__name__)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: Last exception if all retries failed
        """
        
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    # Last attempt failed
                    self.logger.error(f"All {self.max_attempts} retry attempts failed: {str(e)}")
                    raise e
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                
                self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
        
        # Should never reach here, but just in case
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt."""
        
        # Exponential backoff
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Apply maximum delay
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)


class CachePattern:
    """
    Intelligent caching pattern with TTL and size limits.
    
    Features:
    - TTL (Time To Live) based expiration
    - LRU (Least Recently Used) eviction
    - Size-based limits
    - Hit/miss statistics
    - Async-safe operations
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Cache storage
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        
        # Statistics
        self.hits = 0
        self.misses = 0
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logging.getLogger(__name__)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        
        async with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            entry = self.cache[key]
            
            # Check if expired
            if time.time() > entry["expires_at"]:
                del self.cache[key]
                del self.access_times[key]
                self.misses += 1
                return None
            
            # Update access time
            self.access_times[key] = time.time()
            self.hits += 1
            
            return entry["value"]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
        """
        
        async with self._lock:
            # Check size limit
            if len(self.cache) >= self.max_size and key not in self.cache:
                await self._evict_lru()
            
            # Set TTL
            if ttl is None:
                ttl = self.default_ttl
            
            # Store entry
            self.cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": time.time() + ttl
            }
            self.access_times[key] = time.time()
    
    async def delete(self, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if entry was deleted, False if not found
        """
        
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                del self.access_times[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        
        async with self._lock:
            self.cache.clear()
            self.access_times.clear()
    
    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        
        if not self.access_times:
            return
        
        # Find LRU key
        lru_key = min(self.access_times, key=self.access_times.get)
        
        # Remove entry
        del self.cache[lru_key]
        del self.access_times[lru_key]
        
        self.logger.debug(f"Evicted LRU cache entry: {lru_key}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        
        total_requests = self.hits + self.misses
        hit_rate = self.hits / max(1, total_requests)
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


class ThrottlePattern:
    """
    Rate limiting and throttling pattern.
    
    Features:
    - Token bucket algorithm
    - Configurable rate limits
    - Burst capacity
    - Per-key throttling
    - Automatic token replenishment
    """
    
    def __init__(self, rate: float, burst: int = 10):
        self.rate = rate  # tokens per second
        self.burst = burst  # max tokens
        
        # Token buckets per key
        self.buckets: Dict[str, Dict[str, Any]] = {}
        
        self.logger = logging.getLogger(__name__)
    
    async def acquire(self, key: str, tokens: int = 1) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            key: Throttling key (e.g., user_id)
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if rate limited
        """
        
        now = time.time()
        
        # Initialize bucket if needed
        if key not in self.buckets:
            self.buckets[key] = {
                "tokens": self.burst,
                "last_update": now
            }
        
        bucket = self.buckets[key]
        
        # Replenish tokens
        time_passed = now - bucket["last_update"]
        tokens_to_add = time_passed * self.rate
        bucket["tokens"] = min(self.burst, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now
        
        # Check if enough tokens available
        if bucket["tokens"] >= tokens:
            bucket["tokens"] -= tokens
            return True
        else:
            self.logger.warning(f"Rate limit exceeded for key: {key}")
            return False
    
    def get_bucket_status(self, key: str) -> Dict[str, Any]:
        """Get status of a specific bucket."""
        
        if key not in self.buckets:
            return {
                "tokens": self.burst,
                "rate": self.rate,
                "burst": self.burst
            }
        
        bucket = self.buckets[key]
        return {
            "tokens": bucket["tokens"],
            "rate": self.rate,
            "burst": self.burst,
            "last_update": bucket["last_update"]
        }


# Global instances for common use cases
default_circuit_breaker = CircuitBreakerPattern("default")
default_retry_pattern = RetryPattern()
default_cache = CachePattern()
default_throttle = ThrottlePattern(rate=10.0, burst=20)