"""DeepSeek agent adapter for Phoenix-Evo."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .base_agent_adapter import (
    AgentAdapter,
    AgentRunResult,
    EventType,
    TaskSpec,
)


class DeepSeekAdapter(AgentAdapter):
    """Adapter for DeepSeek API (OpenAI-compatible).

    Uses the openai Python package with DeepSeek's base URL.
    Falls back gracefully if the package is unavailable.
    """

    def __init__(
        self,
        agent_id: str = "deepseek",
        model_name: str = "deepseek-chat",
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/v1",
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
    ):
        super().__init__(agent_id=agent_id, model_name=model_name)
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._client = None

    def _get_client(self):
        """Lazily initialise the OpenAI client."""
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except ImportError:
            raise ImportError(
                "The 'openai' package is required for DeepSeekAdapter. "
                "Install it with: pip install openai"
            )
        return self._client

    @staticmethod
    def _redact_secrets(text: str) -> str:
        """Redact common secret patterns from text."""
        patterns = [
            (r'sk-[a-zA-Z0-9]{20,}', 'sk-***REDACTED***'),
            (r'AKIA[0-9A-Z]{16}', 'AKIA***REDACTED***'),
            (r'(?:password|passwd|pwd)\s*[=:]\s*\S+', 'password=***REDACTED***'),
            (r'(?:api[_-]?key|apikey)\s*[=:]\s*\S+', 'api_key=***REDACTED***'),
            (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer ***REDACTED***'),
            (r'token\s+[a-zA-Z0-9._-]+', 'token ***REDACTED***'),
            (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC )?PRIVATE KEY-----',
             '-----BEGIN PRIVATE KEY-----***REDACTED***-----END PRIVATE KEY-----'),
        ]
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    def _call_with_retry(self, messages: list[dict], tools: list[dict] | None = None) -> Any:
        """Call the DeepSeek API with exponential backoff retry."""
        client = self._get_client()
        last_error = None
        for attempt in range(self.max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.model_name,
                    "messages": messages,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                return client.chat.completions.create(**kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_base_delay * (2 ** attempt)
                    time.sleep(delay)
        raise last_error  # type: ignore[misc]

    def run_task(self, task: TaskSpec) -> AgentRunResult:
        """Execute a task using the DeepSeek API with tool calling."""
        start_time = time.time()
        self._events = []

        self.before_task(task)

        # Build initial messages
        system_msg = {
            "role": "system",
            "content": "You are a helpful AI assistant. Complete the task step by step.",
        }
        if task.injected_context:
            injected = self.before_context_injection(task, task.injected_context)
            system_msg["content"] += f"\n\nAdditional context: {json.dumps(injected)}"

        user_msg = {"role": "user", "content": task.description}
        messages = [system_msg, user_msg]

        # Build tools spec
        tools = None
        if task.allowed_tools:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t,
                        "description": f"Execute {t}",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
                for t in task.allowed_tools
            ]

        total_tokens = 0
        total_steps = 0
        final_output = None
        error = None
        success = False

        try:
            for _step in range(task.max_steps):
                total_steps += 1

                self._record_event(
                    EventType.LLM_REQUEST,
                    task_id=task.task_id,
                    model_name=self.model_name,
                )

                response = self._call_with_retry(messages, tools)
                choice = response.choices[0]
                msg = choice.message

                # Track token usage
                if hasattr(response, 'usage') and response.usage:
                    total_tokens += response.usage.total_tokens
                    self._record_event(
                        EventType.LLM_RESPONSE,
                        task_id=task.task_id,
                        model_name=self.model_name,
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                    )

                # Check if done
                if choice.finish_reason == "stop" or not msg.tool_calls:
                    final_output = msg.content
                    success = True
                    break

                # Process tool calls
                messages.append(msg.model_dump())
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Redact and record
                    redacted_args = self._redact_args(fn_args)
                    self._record_event(
                        EventType.TOOL_CALL,
                        task_id=task.task_id,
                        tool_name=fn_name,
                        tool_args_redacted=redacted_args,
                    )

                    # Simulated tool result (in production this would call real tools)
                    tool_result = f"Result of {fn_name} with args {redacted_args}"
                    self._record_event(
                        EventType.TOOL_RESULT,
                        task_id=task.task_id,
                        tool_name=fn_name,
                        tool_result_summary=tool_result[:200],
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": self._redact_secrets(tool_result),
                    })

            else:
                error = f"Task exceeded max_steps ({task.max_steps})"

        except Exception as e:
            error = str(e)
            self.after_failure(task, e)

        duration = time.time() - start_time

        result = AgentRunResult(
            task_id=task.task_id,
            success=success,
            final_output=final_output,
            error=error,
            events=list(self._events),
            total_tokens=total_tokens,
            total_steps=total_steps,
            duration_seconds=duration,
        )

        if success:
            self.after_success(task, result)
        self.after_task(task, result)

        return result
