"""LLM client for OpenAI-compatible APIs."""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI, OpenAIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Rate limit exceeded error."""
    pass


class LLMClient:
    """OpenAI-compatible LLM client with rate limiting."""
    
    def __init__(self):
        """Initialize LLM client."""
        self.client = AsyncOpenAI(
            api_key=config.llm.api_key,
            base_url=config.llm.base_url,
            timeout=config.llm.timeout
        )
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()
        self._rate_limit_per_minute = config.security.rate_limit_per_minute
    
    async def _wait_for_rate_limit(self):
        """Wait if rate limit would be exceeded."""
        async with self._lock:
            now = time.time()
            
            self._request_times = [
                t for t in self._request_times 
                if now - t < 60
            ]
            
            if len(self._request_times) >= self._rate_limit_per_minute:
                oldest_request = self._request_times[0]
                wait_time = 60 - (now - oldest_request)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self._request_times.append(now)
    
    @retry(
        stop=stop_after_attempt(config.llm.max_retries),
        wait=wait_exponential(multiplier=config.llm.retry_delay, min=1, max=10),
        retry=retry_if_exception_type(OpenAIError),
        before_sleep=lambda retry_state: logger.warning(f"Retry {retry_state.attempt_number} due to: {retry_state.outcome.exception()}")
    )
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make a chat completion request."""
        await self._wait_for_rate_limit()

        start_time = time.time()

        try:
            # Build request parameters
            request_params = {
                "model": config.llm.model,
                "messages": messages,
                "temperature": temperature if temperature is not None else config.llm.temperature,
                "max_tokens": max_tokens if max_tokens is not None else config.llm.max_tokens,
                "top_p": config.llm.top_p,
                "seed": config.llm.seed,
                "stream": config.llm.stream,
            }

            if tools:
                request_params["tools"] = tools
            if tool_choice:
                request_params["tool_choice"] = tool_choice

            # NVIDIA NIM specific: chat_template_kwargs for thinking control
            # Must be passed via extra_body as it's not a standard OpenAI param
            if config.llm.enable_thinking or not config.llm.clear_thinking:
                request_params["extra_body"] = {
                    "chat_template_kwargs": {
                        "enable_thinking": config.llm.enable_thinking,
                        "clear_thinking": config.llm.clear_thinking
                    }
                }

            response = await self.client.chat.completions.create(**request_params)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"LLM Response received in {response_time_ms}ms")
            
            # Validate response structure
            if not response or not hasattr(response, 'choices') or not response.choices:
                logger.error(f"LLM Error: Invalid response - {response}")
                raise ValueError("Invalid response: No choices in response")
            
            if not response.choices[0] or not hasattr(response.choices[0], 'message'):
                raise ValueError("Invalid response: No message in choice")
            
            message = response.choices[0].message

            # Log API call
            try:
                from ..database import db_manager
                from ..database.models import APIRateLimitLog

                with db_manager.get_session() as db:
                    rate_log = APIRateLimitLog(
                        endpoint="chat/completions",
                        response_time_ms=response_time_ms,
                        status_code=200,
                        retry_count=0  # Tenacity handles retries transparently
                    )
                    db.add(rate_log)
                    db.commit()
            except Exception:
                pass  # Don't fail if logging fails
            
            # Extract content and tool calls safely
            content = message.content if hasattr(message, 'content') else None

            # Handle thinking models that return reasoning_content instead of content
            if not content and hasattr(message, 'reasoning_content') and message.reasoning_content:
                content = message.reasoning_content

            tool_calls = message.tool_calls if hasattr(message, 'tool_calls') else None
            
            # Extract usage safely
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 0,
                    "completion_tokens": response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 0,
                    "total_tokens": response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0
                }
            
            return {
                "content": content,
                "tool_calls": tool_calls,
                "usage": usage
            }
        except OpenAIError as e:
            if "rate limit" in str(e).lower():
                raise RateLimitError(f"Rate limit exceeded: {e}")
            raise
    
    async def get_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> str:
        """Get a simple text completion."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.chat_completion(messages)
        return response["content"]
    
    async def get_tool_calls(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tool calls from LLM."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.chat_completion(
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        tool_calls = response.get("tool_calls", [])
        
        if not tool_calls:
            return []
        
        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments
            }
            for tc in tool_calls
        ]
    
    async def get_structured_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a structured JSON response."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({
            "role": "user",
            "content": f"{prompt}\n\nRespond with valid JSON only."
        })
        
        response = await self.chat_completion(messages)
        content = response["content"]
        
        import json
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON response", "raw": content}
    
    def get_current_rate_limit_usage(self) -> Dict[str, int]:
        """Get current rate limit usage."""
        now = time.time()
        recent_requests = [
            t for t in self._request_times 
            if now - t < 60
        ]
        
        return {
            "requests_in_last_minute": len(recent_requests),
            "limit": self._rate_limit_per_minute,
            "remaining": self._rate_limit_per_minute - len(recent_requests)
        }
    
    async def close(self):
        """Close the client connection."""
        await self.client.close()


# Global LLM client instance
llm_client = LLMClient()
