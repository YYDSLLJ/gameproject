# -*- coding: utf-8 -*-
"""
可视化模块 - 预留接入多平台大屏
"""

from .registry import VizRegistry, get_platform_viz

# 导入各平台大屏模块，触发注册装饰器执行
from . import bilibili  # noqa: F401
from . import douyin    # noqa: F401

__all__ = ['VizRegistry', 'get_platform_viz']
