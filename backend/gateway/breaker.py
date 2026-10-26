import time
from enum import Enum


class BreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Standard circuit breaker for protecting downstream LLM provider endpoints.
    """

    def __init__(self, failure_threshold: int = 3, recovery_time: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = BreakerState.CLOSED

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == BreakerState.OPEN:
            if now - self.last_failure_time >= self.recovery_time:
                self.state = BreakerState.HALF_OPEN
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = BreakerState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = BreakerState.OPEN
