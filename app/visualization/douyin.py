# -*- coding: utf-8 -*-
"""
抖音可视化大屏
预留位置，暂不实现（等接入时再设计对应的大屏）
"""

from .registry import VizRegistry


@VizRegistry.register('douyin')
class DouyinVisualization:
    """
    抖音视频可视化大屏

    预留位置，后续实现时需要考虑：
    - 抖音数据字段与B站不同
    - 没有弹幕数据
    - 可能有不同的互动指标

    暂不实现，等接入时再设计对应的大屏
    """

    def __init__(self):
        self.platform = 'douyin'
        raise NotImplementedError("抖音可视化大屏暂未实现，预留位置")
