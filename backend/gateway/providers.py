import abc
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ProviderAdapter(abc.ABC):
    """Abstract base adapter for LLM providers."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name

    @abc.abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """Generate a response from the provider."""
        pass


class GeminiAdapter(ProviderAdapter):
    """Adapter for Google Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY")
        if key:
            key = key.strip('"\'')
        model = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        super().__init__(api_key=key, model_name=model)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        try:
            import httpx
            model_clean = self.model_name.replace("models/", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={self.api_key}"

            contents = []
            if system_prompt:
                contents.append({"role": "user", "parts": [{"text": f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nPlease strictly follow these instructions."}]})
                contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow the instructions."}]})
            contents.append({"role": "user", "parts": [{"text": prompt}]})

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json={"contents": contents})
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise


class GroqAdapter(ProviderAdapter):
    """Adapter for Groq models."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        key = api_key or os.getenv("GROQ_API_KEY")
        if key:
            key = key.strip('"\'')
        model = model_name or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        super().__init__(api_key=key, model_name=model)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured.")
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            chat_completion = await client.chat.completions.create(
                messages=messages,
                model=self.model_name,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq generation error: {e}")
            raise


class CerebrasAdapter(ProviderAdapter):
    """Adapter for Cerebras inference API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama3.1-70b"):
        try:
            resolved_key = api_key or os.getenv("CEREBRAS_API_KEY")
            super().__init__(api_key=resolved_key, model_name=model_name)
        except Exception as e:
            logger.warning(f"Cerebras client instantiation skipped: {e}")
            super().__init__(api_key=None, model_name=model_name)

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        if not self.api_key:
            logger.warning("CEREBRAS_API_KEY is missing or empty. Bypassing Cerebras execution.")
            raise ValueError("CEREBRAS_API_KEY is not configured.")
        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.cerebras.ai/v1/chat/completions",
                    headers=headers,
                    json={"model": self.model_name, "messages": messages}
                )
                res.raise_for_status()
                data = res.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Cerebras generation error: {e}")
            raise


class MockAdapter(ProviderAdapter):
    """Deterministic mock provider for offline demo / testing."""

    def __init__(self, name: str = "mock"):
        super().__init__(api_key="mock-key", model_name="mock-model")
        self.name = name

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        # Returns a valid simulated JSON plan matching our schema
        sample_plan = {
            "intent": "Filter customers in workspace and generate summary report",
            "steps": [
                {
                    "step_id": 1,
                    "action": "READ_CSV",
                    "params": {"file": "customers.csv"},
                    "description": "Load customer data"
                },
                {
                    "step_id": 2,
                    "action": "FILTER_ROWS",
                    "params": {"file": "customers.csv", "column": "country", "operator": "==", "value": "USA"},
                    "description": "Filter customers from USA"
                },
                {
                    "step_id": 3,
                    "action": "EXPORT_CSV",
                    "params": {"source_step": 2, "output_file": "usa_customers.csv"},
                    "description": "Export filtered result"
                }
            ]
        }
        return json.dumps(sample_plan)
