"""FastAPI 应用入口。

教学要点：
- /healthz 供 Kubernetes liveness / readiness 探针使用；
  返回体附带 app_env，方便确认当前请求命中了哪个环境的副本；
- 启动时打印生效配置（敏感 Key 自动脱敏），
  便于在 kubectl logs 中直接核对 ConfigMap / Secret 是否正确注入；
- /chat 提供 LLM 对话测试页（单文件 HTML，无前端构建依赖）；
- /metrics 暴露 Prometheus 指标（HTTP 请求指标 + LLM 业务指标），
  供 kube-prometheus-stack 的 ServiceMonitor 抓取。
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import get_settings
from app.routers import llm, node

# 按 APP_ENV 决定日志级别（dev=DEBUG，test/prod=INFO）
settings = get_settings()
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="k8s-demo",
    description=(
        "Kubernetes / Helm Chart 学习示例：节点信息接口 + "
        "OpenAI 兼容 LLM 对话接口。交互式文档见 /docs。"
    ),
    version="1.0.0",
)

# 注册业务路由
app.include_router(node.router)
app.include_router(llm.router)

# ---- Prometheus 指标 ----
# Instrumentator 自动统计各 HTTP 接口的请求量/延迟等指标（http_*），
# 与 app/metrics.py 中的业务指标（llm_*）共用同一个默认注册表，
# 统一暴露在 /metrics 供 Prometheus 抓取。
expose_metrics = Instrumentator().instrument(app)
expose_metrics.expose(app, endpoint="/metrics", include_in_schema=False)

# ---- LLM 测试页 ----
# 静态资源目录（chat.html 等）挂载到 /static 下
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/chat", include_in_schema=False, summary="LLM 对话测试页")
async def chat_page() -> FileResponse:
    """返回单文件测试页：支持多轮对话、流式/非流式切换、模型覆盖。"""
    return FileResponse(STATIC_DIR / "chat.html")


@app.get("/healthz", summary="健康检查（K8s 探针入口）")
async def healthz() -> dict[str, str]:
    """存活 / 就绪探针都指向这里。

    K8s 中探针返回非 2xx 状态码会被视为不健康，
    进而触发 Pod 重启（liveness）或摘除流量（readiness）。
    """
    return {"status": "ok", "app_env": settings.app_env}


@app.get("/", summary="根路径：返回应用简介")
async def root() -> dict[str, str]:
    """根路径提示：引导用户访问 /docs 与各教学接口。"""
    return {
        "message": "k8s-demo 教学示例已运行",
        "docs": "/docs",
        "health": "/healthz",
        "chat_ui": "/chat",
    }


# ---------- 启动日志（教学用） ----------
# 打印非敏感配置用于核对；LLM_API_KEY 是 SecretStr，
# str() 只会输出 "**********"，绝不会泄露明文。
logger.info("========== k8s-demo 启动配置 ==========")
logger.info("APP_ENV      = %s", settings.app_env)
logger.info("日志级别      = %s", settings.log_level)
logger.info("TZ           = %s", settings.tz)
logger.info("LLM_BASE_URL = %s", settings.llm_base_url)
logger.info("LLM_MODEL    = %s", settings.llm_model)
logger.info("LLM_API_KEY  = %s（已脱敏，非空=%s）", settings.llm_api_key, settings.llm_configured)
logger.info("当前容器     = HOSTNAME:%s NODE_NAME:%s", os.environ.get("HOSTNAME", "unknown"), os.environ.get("NODE_NAME", "unknown"))
logger.info("=======================================")
