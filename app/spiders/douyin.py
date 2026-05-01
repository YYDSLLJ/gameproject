# -*- coding: utf-8 -*-
"""
抖音爬虫

预留位置，暂不实现
不同源的爬虫接口一致，但数据解析不同
"""

import re
from . import BaseSpider, SpiderRegistry


class DouyinSpider(BaseSpider):
    """抖音爬虫"""

    URL_PATTERNS = [
        r'douyin\.com/video/(\d+)',
        r'v\.douyin\.com/([\w]+)',
    ]

    def __init__(self):
        # 暂不实现
        raise NotImplementedError("抖音爬虫暂未实现，预留位置")

    @classmethod
    def extract_id(cls, url):
        """从URL提取抖音视频ID"""
        match = re.search(r'douyin\.com/video/(\d+)', url)
        if match:
            return match.group(1)
        match = re.search(r'v\.douyin\.com/([\w]+)', url)
        if match:
            return match.group(1)
        return None

    def get_video_info(self, douyin_id):
        """获取视频基本信息"""
        raise NotImplementedError("抖音爬虫暂未实现")

    def get_video_stats(self, douyin_id):
        """获取视频统计数据"""
        raise NotImplementedError("抖音爬虫暂未实现")

    def get_comments(self, douyin_id, page=1, page_size=20):
        """获取评论列表"""
        raise NotImplementedError("抖音爬虫暂未实现")

    def get_danmaku(self, douyin_id):
        """抖音没有弹幕"""
        return []


# 注册爬虫（暂不注册，等实现后再挂载）
# SpiderRegistry.register('douyin', DouyinSpider)
