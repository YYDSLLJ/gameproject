# -*- coding: utf-8 -*-
"""
多源视频热度分析系统 - 可视化模块

设计思路：
- 每个平台有独立的大屏可视化模块
- 通过 VizRegistry 注册，动态加载对应平台的大屏
- 支持平台特定的数据字段
"""

from flask import Blueprint

viz_bp = Blueprint('visualization', __name__)


class VizRegistry:
    """大屏注册表"""
    _registry = {}

    @classmethod
    def register(cls, platform):
        """装饰器：@VizRegistry.register('bilibili')"""
        def decorator(f):
            cls._registry[platform] = f
            return f
        return decorator

    @classmethod
    def get_viz(cls, platform):
        """获取平台对应的大屏类"""
        viz_class = cls._registry.get(platform)
        if viz_class is None:
            raise ValueError(f"不支持的平台: {platform}")
        return viz_class

    @classmethod
    def list_platforms(cls):
        """列出所有已注册的平台"""
        return list(cls._registry.keys())


def get_platform_viz(platform):
    """获取平台对应的大屏实例"""
    return VizRegistry.get_viz(platform)()
