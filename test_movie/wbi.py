# -*- coding: utf-8 -*-
"""
WBI签名 - 参考bilibili_spider_view/spider/wbi.py
"""

import hashlib
from urllib.parse import quote

# 与原脚本完全一致的签名盐
_SECRET = "ea1db124af3c7062474693fa704f4ff8"


def compute_w_rid(params: dict, wts: int) -> str:
    """
    计算w_rid签名

    keys_order = ['mode','oid','pagination_str','plat','seek_rpid','type','web_location']
    其中pagination_str需要URL编码，其余保持原值

    注意：wts作为一项追加到拼接列表，再在末尾直接+SECRET（不再拼接'&'）
    """
    keys_order = ['mode', 'oid', 'pagination_str', 'plat', 'seek_rpid', 'type', 'web_location']
    items = []
    for key in keys_order:
        val = params.get(key, '')
        if key == 'pagination_str':
            val = quote(str(val), safe='')
        items.append(f"{key}={val}")
    items.append(f"wts={wts}")
    s = '&'.join(items) + _SECRET
    return hashlib.md5(s.encode('utf-8')).hexdigest()