"""Prometheus 指标定义。

教学要点：
- 业务指标由应用自行埋点（Counter / Histogram），与 HTTP 请求指标互补；
- 指标命名遵循 Prometheus 惯例：<域>_<单位>，计数器以 _total 结尾；
- 标签（label）用于维度切分（本处按 model 与 status 切分），
  但标签基数不宜过高，避免时序爆炸。

指标清单：
- llm_chat_requests_total{model,status}：LLM 对话调用计数
  status 取值：success / not_configured / upstream_error
- llm_chat_duration_seconds{model}：LLM 对话耗时直方图
- http_*（由 prometheus-fastapi-instrumentator 自动生成）：
  各 HTTP 接口的请求计数、延迟直方图、请求体大小等
"""

from prometheus_client import Counter, Histogram

# 对话调用计数：按实际使用的模型与结果状态切分
LLM_CHAT_REQUESTS = Counter(
    "llm_chat_requests_total",
    "LLM 对话接口调用次数",
    ["model", "status"],
)

# 对话耗时直方图：观测值自动分桶（默认桶上限 10s）
LLM_CHAT_DURATION = Histogram(
    "llm_chat_duration_seconds",
    "LLM 对话接口耗时（秒）",
    ["model"],
)
