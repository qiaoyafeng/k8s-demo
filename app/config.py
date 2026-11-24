"""应用配置模块。

设计约定（本项目贯穿所有部署方式的配置策略）：
1. 配置一律通过环境变量注入，代码中不写死任何密钥；
2. 敏感信息（LLM_API_KEY）使用 SecretStr 类型，天然脱敏：
   - 不参与 repr / 日志输出；
   - str(settings.llm_api_key) 只会得到 "**********"；
3. 配置优先级：环境变量 > 本地 .env 文件 > 代码默认值。
   .env 文件仅用于本地开发（已加入 .gitignore），容器内全部靠环境变量。

在不同部署方式下，同一个环境变量由不同机制注入：
- 本地开发：uv run + .env 文件（pydantic-settings 自动读取）
- Docker Compose：docker-compose.yml 的 environment 引用宿主机 .env
- Kubernetes：ConfigMap（非敏感）+ Secret（敏感，LLM_API_KEY）
- Helm：values.yaml 渲染出的 ConfigMap / Secret
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。字段名与 Kubernetes 环境变量一一对应（大写）。"""

    model_config = SettingsConfigDict(
        # 本地开发时从 .env 读取（该文件已被 gitignore）；
        # 环境变量的优先级高于 .env，容器场景不受影响。
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 环境标识：dev / test / prod。
    # 不同环境在部署侧由 kustomize overlay / Helm values 注入，
    # 应用侧仅用它决定日志级别等行为差异。
    app_env: Literal["dev", "test", "prod"] = "dev"

    # 时区：/api/node/time 接口按此时区返回时间。
    tz: str = "Asia/Shanghai"

    # ---- LLM 配置（OpenAI 兼容协议）----
    # API Base URL：默认 OpenAI 官方地址；任何 OpenAI 兼容服务
    # （DeepSeek、通义千问、vLLM、Ollama 等）只需替换此值。
    llm_base_url: str = "https://api.openai.com/v1"

    # API Key：敏感信息。SecretStr 保证任何打印/日志场景都自动脱敏。
    # 未配置时 /api/llm/chat 返回 502，不影响节点类接口。
    llm_api_key: SecretStr = SecretStr("")

    # 默认对话模型，请求体可临时覆盖。
    llm_model: str = "gpt-4o-mini"

    # LLM 请求超时（秒），避免上游服务异常时无限挂起。
    llm_timeout: float = 60.0

    @property
    def log_level(self) -> str:
        """按环境决定日志级别：开发环境开 DEBUG，测试/生产用 INFO。"""
        return "DEBUG" if self.app_env == "dev" else "INFO"

    @property
    def llm_configured(self) -> bool:
        """LLM 是否已配置好（API Key 非空）。"""
        return bool(self.llm_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    """进程内缓存的 Settings 单例，避免重复解析环境变量。"""
    return Settings()
