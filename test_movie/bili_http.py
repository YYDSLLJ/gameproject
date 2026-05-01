# -*- coding: utf-8 -*-
"""
HTTP会话封装 - 参考bilibili_spider_view/spider/http.py
"""

import os
import json
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
)

def load_cookie(config_path: str = "b_config.json") -> str:
    """
    加载cookie，优先顺序：环境变量 BILI_COOKIE > 本地 b_config.json > 空字符串
    """
    env_cookie = os.getenv("BILI_COOKIE")
    if env_cookie:
        return env_cookie
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("cookie", "") or ""
        except Exception:
            return ""
    return ""


class BiliSession:
    """
    轻量HTTP会话封装，提供：
    - 统一UA/Referer/Cookie头
    - 简单的重试策略
    """
    def __init__(
        self,
        referer: str = "https://www.bilibili.com/",
        cookie: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

        ck = cookie if cookie is not None else load_cookie()
        self.headers = {
            "User-Agent": DEFAULT_UA,
            "Referer": referer,
        }
        if ck:
            self.headers["Cookie"] = ck
        if extra_headers:
            self.headers.update(extra_headers)

    def get(self, url: str, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", None) or {}
        merged = {**self.headers, **headers}
        return self.session.get(url, headers=merged, timeout=kwargs.pop("timeout", 15), **kwargs)

    def get_json(self, url: str, **kwargs) -> Dict[str, Any]:
        resp = self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()