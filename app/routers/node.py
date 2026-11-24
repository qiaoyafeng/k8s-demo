"""节点相关接口。

这两个接口是本项目学习 Kubernetes 的关键入口：
- /api/node/name 展示 downward API 注入的 Pod 名 / 节点名；
- /api/node/time 展示容器内系统时间与 TZ 时区配置。

在 K8s 中多副本部署后反复访问这两个接口，可以直观看到
Service 的负载均衡效果（每次可能命中不同 Pod / 节点）。
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import NodeInfo, TimeInfo

router = APIRouter(prefix="/api/node", tags=["node"])


@router.get("/name", response_model=NodeInfo, summary="返回当前 Pod 与所在节点名")
async def get_node_name() -> NodeInfo:
    """返回 Pod 名与 K8s 节点名。

    - pod_name：容器内 HOSTNAME 环境变量。K8s 默认把容器 hostname
      设为 Pod 名，因此它就是 Pod 名；
    - node_name：deployment.yaml 中通过 downward API
      （fieldRef: spec.nodeName）注入的 NODE_NAME 环境变量，
      表示该 Pod 被调度到了哪个工作节点。

    本地裸跑（非 K8s）时两者取不到值，会回退为 "unknown"，
    便于教学演示环境差异。
    """
    return NodeInfo(
        pod_name=os.environ.get("HOSTNAME", "unknown"),
        node_name=os.environ.get("NODE_NAME", "unknown"),
    )


@router.get("/time", response_model=TimeInfo, summary="返回当前系统时间")
async def get_node_time() -> TimeInfo:
    """返回容器系统时间与生效时区。

    时区来自 TZ 环境变量（默认 Asia/Shanghai），
    演示配置如何通过环境变量注入 Pod。
    """
    settings = get_settings()
    tz = settings.tz
    now = datetime.now(ZoneInfo(tz))
    return TimeInfo(time=now.isoformat(), timezone=tz)
