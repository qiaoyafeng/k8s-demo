# ============================================================
# k8s-demo 镜像构建（uv 多阶段构建，参考 uv 官方文档推荐写法）
#
# 教学要点：
# 1. 多阶段构建：builder 装依赖，runtime 只拷贝产物，镜像更小；
# 2. 依赖锁定：uv sync --frozen 严格按 uv.lock 安装，保证可复现；
# 3. 非 root 运行：容器内以 appuser 运行，符合安全最佳实践；
# 4. 配置不进入镜像：LLM_API_KEY 等一律靠运行时环境变量注入，
#    镜像可以在任何环境复用。
#
# 构建与运行：
#   docker build -t k8s-demo:latest .
#   docker run --rm -p 8000:8000 --env-file .env k8s-demo:latest
# ============================================================

# ---------- 阶段 1：依赖构建 ----------
# uv 官方镜像（带 Python 3.11 与 shell 的 bookworm-slim 版本），
# 纯 uv 镜像为 distroless（无 /bin/sh），无法执行 RUN 命令。
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# 先只拷贝依赖声明，利用 Docker 层缓存：
# 只有 pyproject.toml / uv.lock 变化时才重装依赖
COPY pyproject.toml uv.lock ./

# UV_COMPILE_BYTECODE：预编译 .pyc，加快启动
# UV_LINK_MODE=copy：独立拷贝文件（而非硬链接），跨阶段拷贝 .venv 必需
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# --frozen：严格按 uv.lock 安装（版本漂移会直接报错）
# --no-dev：跳过 pytest/httpx 等开发依赖，镜像只带运行依赖
RUN uv sync --frozen --no-dev

# 拷贝应用源码（app/ 包，package=false 无需安装项目本身）
COPY app ./app

# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim

WORKDIR /app

# 创建非 root 用户：容器进程不以 root 运行
RUN useradd --create-home --uid 1000 appuser

# 从 builder 拷贝虚拟环境与源码；owner 设为 appuser
COPY --from=builder --chown=appuser:appuser /app /app

# 把虚拟环境的可执行文件放进 PATH，直接调用 uvicorn
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser

# 容器内监听 8000（K8s Service 的 targetPort 与此对应）
EXPOSE 8000

# 注意：不在这里配置任何密钥；
# LLM_BASE_URL / LLM_API_KEY 等由 K8s ConfigMap/Secret 或 docker run 注入
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
