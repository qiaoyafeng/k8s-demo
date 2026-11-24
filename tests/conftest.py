"""pytest 全局夹具。

让测试与外部环境（.env 文件、真实 LLM 上游服务）解耦：
所有测试在"未配置 LLM 密钥"的状态下运行，
保证行为确定，且测试永不发起真实的外部 LLM 调用。
"""

import pytest
from pydantic import SecretStr

from app.config import get_settings


@pytest.fixture(autouse=True)
def disable_llm_upstream():
    """强制清空 LLM 密钥：测试只验证报错路径，不依赖外部服务。

    get_settings() 是 lru_cache 单例，routers/llm.py 中的 LLMClient
    持有同一实例引用，因此直接修改其属性即对所有调用生效。
    """
    settings = get_settings()
    original = settings.llm_api_key
    settings.llm_api_key = SecretStr("")
    yield
    settings.llm_api_key = original
