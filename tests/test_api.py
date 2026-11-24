"""基础接口测试。

用 FastAPI TestClient 验证不依赖外部服务的接口；
LLM 接口测试的是"未配置密钥时的报错路径"（无需真实 Key）。

外部环境隔离：tests/conftest.py 的 autouse 夹具强制清空 LLM 密钥，
即使开发者本机配置了 .env，测试也不会发起真实上游调用。
"""

import os
import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    """根路径应返回引导信息。"""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["docs"] == "/docs"
    assert resp.json()["chat_ui"] == "/chat"


def test_chat_page():
    """LLM 测试页应返回 HTML 页面。"""
    resp = client.get("/chat")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "LLM 对话测试台" in resp.text


def test_metrics_endpoint():
    """Prometheus 指标端点：应暴露 HTTP 请求指标。

    llm_* 业务指标需有调用后才会产生样本，
    其验证见 test_llm_error_is_recorded_in_metrics。
    """
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Instrumentator 统计的 HTTP 请求指标（前面的测试已产生请求样本）
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body


def test_llm_error_is_recorded_in_metrics():
    """未配置密钥的 502 调用应被计入 llm_chat_requests_total（not_configured）。"""
    resp = client.post(
        "/api/llm/chat",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )
    assert resp.status_code == 502
    metrics_body = client.get("/metrics").text
    # 计数器样本：带 model 与 status 标签（model 取配置值，不硬编码）
    assert re.search(
        r'llm_chat_requests_total\{model="[^"]+",status="not_configured"\}',
        metrics_body,
    )
    # 耗时直方图同步产生样本
    assert "llm_chat_duration_seconds_bucket" in metrics_body


def test_healthz():
    """健康检查：K8s 探针依赖此接口返回 200。"""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # app_env 默认 dev（未显式设置环境变量时）
    assert body["app_env"] == "dev"


def test_node_name():
    """节点信息接口：非 K8s 环境应回退为 unknown。"""
    resp = client.get("/api/node/name")
    assert resp.status_code == 200
    body = resp.json()
    assert "pod_name" in body and "node_name" in body
    # 本地跑没有 K8s downward API，应回退
    assert body["node_name"] == "unknown"


def test_node_time():
    """时间接口：返回 ISO 格式时间与默认时区。"""
    resp = client.get("/api/node/time")
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "Asia/Shanghai"
    # ISO 8601 格式应包含 T
    assert "T" in body["time"]


def test_llm_chat_without_key():
    """未配置 LLM_API_KEY 时，对话接口应返回 502 与可读提示。"""
    resp = client.post(
        "/api/llm/chat",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )
    assert resp.status_code == 502
    assert "LLM_API_KEY" in resp.json()["detail"]


def test_llm_chat_rejects_empty_messages():
    """空消息列表应被 Pydantic 校验拦截（422）。"""
    resp = client.post("/api/llm/chat", json={"messages": []})
    assert resp.status_code == 422
