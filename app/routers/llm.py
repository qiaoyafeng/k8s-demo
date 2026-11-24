"""LLM 对话接口。

演示如何把外部依赖（OpenAI 兼容 LLM）接入 K8s 应用：
- 配置全部来自环境变量（见 app/config.py）；
- 密钥走 Secret 注入，应用内用 SecretStr 脱敏；
- LLM 不可用时返回 502，不影响节点类接口的可用性；
- 每次调用埋点 Prometheus 业务指标（llm_chat_requests_total / llm_chat_duration_seconds），
  配合告警规则可及时发现 LLM 上游异常。
"""

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import metrics
from app.config import get_settings
from app.schemas import ChatRequest, ChatResponse
from app.services.llm_client import LLMClient, LLMNotConfigured, LLMUpstreamError

router = APIRouter(prefix="/api/llm", tags=["llm"])

# 惰性单例：第一次请求到达时才真正创建（也才真正连接上游）
_client = LLMClient()


@router.post("/chat", response_model=ChatResponse, summary="LLM 对话（OpenAI 兼容）")
async def chat(req: ChatRequest):
    """对话接口。请求体与 OpenAI Chat Completions 协议对齐。

    传 stream=true 时返回 SSE 流（text/event-stream），
    否则返回普通 JSON（response_model 仅约束非流式分支）。
    """
    settings = get_settings()
    model = req.model or settings.llm_model
    # Pydantic 模型 → OpenAI SDK 期望的纯字典结构
    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if req.stream:
        return await _stream_chat(messages, model)

    started = time.perf_counter()
    try:
        reply = await _client.chat(messages, model=model)
    except LLMNotConfigured as exc:
        metrics.LLM_CHAT_REQUESTS.labels(model=model, status="not_configured").inc()
        metrics.LLM_CHAT_DURATION.labels(model=model).observe(
            time.perf_counter() - started
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMUpstreamError as exc:
        metrics.LLM_CHAT_REQUESTS.labels(model=model, status="upstream_error").inc()
        metrics.LLM_CHAT_DURATION.labels(model=model).observe(
            time.perf_counter() - started
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    elapsed = time.perf_counter() - started
    metrics.LLM_CHAT_REQUESTS.labels(model=model, status="success").inc()
    metrics.LLM_CHAT_DURATION.labels(model=model).observe(elapsed)
    return ChatResponse(reply=reply, model=model, elapsed_seconds=round(elapsed, 3))


async def _stream_chat(messages: list[dict[str, str]], model: str) -> StreamingResponse:
    """把上游流式增量转成 SSE 事件流（同样埋点，流结束时统一记录）。"""

    async def event_source():
        started = time.perf_counter()
        status = "success"
        try:
            async for delta in _client.chat_stream(messages, model=model):
                # 每条 data 事件携带一段增量文本；前端可按此逐字渲染
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        except LLMNotConfigured as exc:
            status = "not_configured"
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        except LLMUpstreamError as exc:
            status = "upstream_error"
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            # 无论成败都记录一次调用（status 标签区分结果）
            metrics.LLM_CHAT_REQUESTS.labels(model=model, status=status).inc()
            metrics.LLM_CHAT_DURATION.labels(model=model).observe(
                time.perf_counter() - started
            )
        # 标准 SSE 结束标记
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
