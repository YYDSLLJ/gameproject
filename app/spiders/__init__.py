# -*- coding: utf-8 -*-
"""
爬虫模块 - 统一接口
"""

import re
from abc import ABC, abstractmethod


class BaseSpider(ABC):
    """爬虫基类"""

    # 支持的URL模式（子类覆盖）
    URL_PATTERNS = []

    @classmethod
    def match(cls, url):
        """判断URL是否匹配此爬虫"""
        for pattern in cls.URL_PATTERNS:
            if re.search(pattern, url):
                return True
        return False

    @abstractmethod
    def get_video_info(self, platform_id):
        """获取视频基本信息"""
        pass

    @abstractmethod
    def get_video_stats(self, platform_id):
        """获取视频统计数据"""
        pass

    @abstractmethod
    def get_comments(self, platform_id, page=1, page_size=20):
        """获取评论列表"""
        pass

    def get_danmaku(self, platform_id):
        """获取弹幕列表（B站有，其他平台可返回空）"""
        return []


class SpiderRegistry:
    """爬虫注册表"""
    _spiders = {}

    @classmethod
    def register(cls, name, spider_class):
        cls._spiders[name] = spider_class

    @classmethod
    def get_spider(cls, name):
        return cls._spiders.get(name)

    @classmethod
    def match_url(cls, url):
        """根据URL匹配爬虫"""
        for name, spider_class in cls._spiders.items():
            if spider_class.match(url):
                return spider_class
        return None


def parse_video_url(url):
    """解析视频URL，返回 (platform, platform_id)"""
    from .bilibili import BilibiliSpider
    from .douyin import DouyinSpider

    # 尝试B站
    if BilibiliSpider.match(url):
        bvid = BilibiliSpider.extract_bvid(url)
        return ('bilibili', bvid)

    # 尝试抖音
    if DouyinSpider.match(url):
        douyin_id = DouyinSpider.extract_id(url)
        return ('douyin', douyin_id)

    raise ValueError(f"不支持的URL: {url}")
