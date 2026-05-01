#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunicorn 配置文件
根据服务器资源自动调整 worker 数量
"""

import os


def get_worker_count():
    """根据 CPU 核心数计算 worker 数量"""
    try:
        n = os.cpu_count() or 1
    except Exception:
        n = 1
    # 内存 <= 2GB 时限制为 1 worker，防止 OOM
    return 1


# 绑定地址
bind = "127.0.0.1:8080"

# Worker 数量（内存保护）
workers = get_worker_count()
threads = 2

# 超时配置
timeout = 120
graceful_timeout = 30
keepalive = 5

# 防止内存泄漏：每个 worker 处理 max_requests 后自动重启
max_requests = 500
max_requests_jitter = 50

# 日志
errorlog = "gunicorn_error.log"
accesslog = "gunicorn_access.log"
loglevel = "warning"

# 进程名称
proc_name = "kui_video_project"

# 预加载应用（共享内存，减少内存占用）
preload_app = True
