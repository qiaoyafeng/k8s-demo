"""OpenAI 兼容 LLM 客户端封装。

设计要点：
1. 使用官方 openai SDK（v1.x）的 AsyncOpenAI；
   base_url 可指向任何 OpenAI 兼容服务（DeepSeek / 通义 / vLLM / Ollama ...），
   因此无需为不同厂商引入各自的 SDK。
2. 惰性初始化：客户端只在第一次调用聊天接口时才创建，
   保证 LLM 未配置时节点类接口完全不受影响。
3. 错误统一转成 LLMNotConfigured / LLMUpstreamError，
   由路由层映射为 502 响应并附带可读信息。
"""

from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMNotConfigured(Exception):
    """LLM 未配置（缺少 LLM_API_KEY）时抛出。"""


class LLMUpstreamError(Exception):
    """调用上游 LLM 服务失败时抛出。"""


class LLMClient:
    """线程安全的一次性封装：持有配置与惰性创建的 AsyncOpenAI 客户端。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # 惰性初始化：真正需要时才连上游
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self._settings.llm_base_url,
                # SecretStr 需显式取出真实值才能传给 SDK
                api_key=self._settings.llm_api_key.get_secret_value(),
                timeout=self._settings.llm_timeout,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> str:
        """发起一次非流式对话，返回模型回复文本。"""
        if not self._settings.llm_configured:
            raise LLMNotConfigured(
                "LLM_API_KEY 未配置：请通过环境变量 / K8s Secret / "
                "Helm --set llm.apiKey 等方式注入密钥后重试"
            )

        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=model or self._settings.llm_model,
                messages=messages,
                stream=False,
            )
        except Exception as exc:  # noqa: BLE001 —— 教学示例，统一转义上游错误
            logger.warning("LLM 上游调用失败: %s", exc)
            raise LLMUpstreamError(
                f"上游 LLM 服务调用失败（{type(exc).__name__}）：请检查 "
                f"LLM_BASE_URL、LLM_API_KEY 与网络连通性"
            ) from exc

        # 常规场景取第一个候选的文本
        content = response.choices[0].message.content or ""
        return content

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ):
        """发起一次流式对话，逐块产出增量文本（供 SSE 转发）。"""
        if not self._settings.llm_configured:
            raise LLMNotConfigured(
                "LLM_API_KEY 未配置：请通过环境变量 / K8s Secret / "
                "Helm --set llm.apiKey 等方式注入密钥后重试"
            )

        client = self._get_client()
        try:
            stream = await client.chat.completions.create(
                model=model or self._settings.llm_model,
                messages=messages,
                stream=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM 上游流式调用失败: %s", exc)
            raise LLMUpstreamError(
                f"上游 LLM 服务调用失败（{type(exc).__name__}）：请检查 "
                f"LLM_BASE_URL、LLM_API_KEY 与网络连通性"
            ) from exc

        async for chunk in stream:
            # 流式响应中每个 chunk 携带一小段增量文本
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
