"""Pydantic 请求 / 响应模型。

把这些模型集中放在一个模块，便于教学时对照 API 文档阅读，
也让 FastAPI 自动生成 OpenAPI 文档时结构清晰。
"""

from pydantic import BaseModel, Field


# ---------- 节点相关 ----------

class NodeInfo(BaseModel):
    """节点信息：Pod 名与调度到的 K8s 节点名。"""
    pod_name: str = Field(description="当前 Pod 名（容器内 HOSTNAME 环境变量）")
    node_name: str = Field(description="调度节点名（downward API 注入的 NODE_NAME）")


class TimeInfo(BaseModel):
    """系统时间信息。"""
    time: str = Field(description="当前系统时间（ISO 8601 格式）")
    timezone: str = Field(description="使用的时区（TZ 环境变量）")


# ---------- LLM 对话相关 ----------

class ChatMessage(BaseModel):
    """OpenAI 风格消息：role 为 system / user / assistant 之一。"""
    role: str = Field(description="消息角色", examples=["user"])
    content: str = Field(description="消息内容")


class ChatRequest(BaseModel):
    """对话请求体，与 OpenAI Chat Completions 协议对齐。

    - messages：多轮对话历史，按时间顺序排列；
    - model：可选，覆盖环境变量 LLM_MODEL 指定的默认模型；
    - stream：可选，true 时以 SSE（text/event-stream）流式返回。
    """
    messages: list[ChatMessage] = Field(description="对话消息列表，至少一条", min_length=1)
    model: str | None = Field(default=None, description="覆盖默认模型（可选）")
    stream: bool = Field(default=False, description="是否流式返回（SSE）")


class ChatResponse(BaseModel):
    """非流式对话响应。"""
    reply: str = Field(description="模型回复内容")
    model: str = Field(description="实际使用的模型名")
    elapsed_seconds: float = Field(description="本次调用耗时（秒）")
