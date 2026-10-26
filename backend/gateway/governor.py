import time
from collections import deque
from typing import Dict


class QuotaExceededException(Exception):
    pass


class Governor:
    """
    Manages provider rate limits and daily quota reserves.
    """

    def __init__(self, max_requests_per_minute: int = 60, daily_quota: int = 1_000_000):
        self.max_rpm = max_requests_per_minute
        self.daily_quota = daily_quota
        self.request_history: Dict[str, deque] = {}
        self.token_usage: Dict[str, int] = {}

    def acquire(self, provider_name: str):
        now = time.time()
        if provider_name not in self.request_history:
            self.request_history[provider_name] = deque()

        history = self.request_history[provider_name]
        # Remove timestamps older than 60 seconds
        while history and now - history[0] > 60:
            history.popleft()

        if len(history) >= self.max_rpm:
            raise QuotaExceededException(f"Rate limit exceeded for provider {provider_name} (max {self.max_rpm} rpm).")

        current_tokens = self.token_usage.get(provider_name, 0)
        if current_tokens >= self.daily_quota:
            raise QuotaExceededException(f"Daily quota exceeded for provider {provider_name}.")

        history.append(now)

    def record_token_usage(self, provider_name: str, tokens: int):
        self.token_usage[provider_name] = self.token_usage.get(provider_name, 0) + tokens
