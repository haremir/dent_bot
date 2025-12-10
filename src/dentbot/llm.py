"""
LLM integration with Groq and Ollama fallback.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from dentbot.config import get_config

logger = logging.getLogger(__name__)

# Groq API endpoint
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Ollama API endpoint (default local)
OLLAMA_API_URL = "http://localhost:11434/api/chat"


class LLMClient:
    """LLM client with Groq primary and Ollama fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: Groq API key (if None, will try to get from config)
            model: Model name (if None, will try to get from config)
            timeout: Request timeout in seconds (if None, will try to get from config)
        """
        config = get_config()
        self.api_key = api_key if api_key is not None else config.get_groq_api_key()
        self.model = model if model is not None else config.get_groq_model()
        self.timeout = timeout if timeout is not None else config.get_llm_timeout()
        self.use_groq = bool(self.api_key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Send a chat request to the LLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to prepend
        
        Returns:
            Response text from the LLM
        
        Raises:
            Exception: If both Groq and Ollama fail
        """
        # Prepare messages with system prompt if provided
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        formatted_messages.extend(messages)

        # Try Groq first if API key is available
        if self.use_groq:
            try:
                return self._chat_groq(formatted_messages)
            except Exception as e:
                logger.warning(f"Groq request failed: {e}. Trying Ollama fallback...")
                return self._chat_ollama(formatted_messages)
        else:
            # Use Ollama directly if no Groq API key
            logger.info("No Groq API key found. Using Ollama...")
            return self._chat_ollama(formatted_messages)

    def _chat_groq(self, messages: List[Dict[str, str]]) -> str:
        """Send chat request to Groq API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(GROQ_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract content from response
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError("Invalid response format from Groq API")

    def _chat_ollama(self, messages: List[Dict[str, str]]) -> str:
        """Send chat request to Ollama API (fallback)."""
        # Ollama chat API expects messages in a specific format
        # Convert system message to a regular message if present
        ollama_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Ollama uses "system" role, but we'll convert it to user if needed
            if role == "system":
                # Prepend system message as a user message with context
                ollama_messages.append({"role": "user", "content": f"[System Context] {content}"})
            else:
                ollama_messages.append({"role": role, "content": content})

        model_name = get_config().get_ollama_model()
        payload = {
            "model": model_name,  # Config'ten alınan Ollama model adı
            "messages": ollama_messages,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(OLLAMA_API_URL, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"]
                elif "response" in data:
                    # Fallback for older Ollama API format
                    return data["response"]
                else:
                    raise ValueError("Invalid response format from Ollama API")
        except httpx.ConnectError:
            raise ConnectionError(
                "Could not connect to Ollama. "
                "Make sure Ollama is running on localhost:11434. "
                "You can install Ollama from https://ollama.ai"
            )

    def simple_query(self, question: str, system_prompt: Optional[str] = None) -> str:
        """
        Simple query interface for asking a single question.
        
        Args:
            question: The question to ask
            system_prompt: Optional system prompt
        
        Returns:
            Response text
        """
        messages = [
            {
                "role": "user",
                "content": question,
            }
        ]
        return self.chat(messages, system_prompt=system_prompt)


# Global LLM client instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client instance."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def set_llm_client(client: LLMClient) -> None:
    """Set a custom LLM client instance (useful for testing)."""
    global _llm_client
    _llm_client = client
