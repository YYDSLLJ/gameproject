# -*- coding: utf-8 -*-
"""
可视化注册表
每个平台的大屏模块在这里注册
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
