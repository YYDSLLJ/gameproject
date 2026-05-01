# -*- coding: utf-8 -*-
"""
评论爬虫 - 参考bilibili_spider_view/spider/comments.py
"""

import csv
import json
import time
from typing import List, Dict, Optional, Tuple

import bili_http
import wbi
BiliSession = bili_http.BiliSession
load_cookie = bili_http.load_cookie
compute_w_rid = wbi.compute_w_rid

MAIN_API = "https://api.bilibili.com/x/v2/reply/wbi/main"
SUB_API = "https://api.bilibili.com/x/v2/reply/reply"

COLUMNS = [
    'uid', '昵称', '性别', '地区', '签名', '等级',
    '评论内容', '评论时间', '点赞数', '评论等级', '父评论ID'
]


class CommentCrawler:
    """
    B站评论爬虫
    - 纯函数接口
    - 保持与原脚本一致的字段
    """
    def __init__(self, cookie: Optional[str] = None) -> None:
        ck = cookie if cookie is not None else load_cookie()
        self.session = BiliSession(cookie=ck)

    def _fetch(self, url: str, params: dict) -> dict:
        r = self.session.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def _fetch_sub_comments(self, oid: str, type_val: str, root: int, ps: int = 20) -> List[Dict]:
        """获取子评论"""
        sub_comments: List[Dict] = []
        pn = 1
        while True:
            params = {
                'oid': oid, 'type': type_val, 'root': root, 'ps': ps, 'pn': pn, 'web_location': '333.788'
            }
            data = self._fetch(SUB_API, params)
            if not data.get("data") or not data["data"].get("replies"):
                break

            for reply in data["data"]["replies"]:
                ctime = reply.get('ctime')
                like_count = reply.get('like', 0)
                content = reply.get('content', {})
                reply_control = reply.get('reply_control', {})
                member = reply.get('member', {})
                comment = {
                    'uid': member.get('mid', ''),
                    '昵称': member.get('uname', ''),
                    '性别': member.get('sex', ''),
                    '地区': reply_control.get('location', '').replace('IP属地：', '').strip(),
                    '签名': member.get('sign', ''),
                    '等级': member.get('level_info', {}).get('current_level', ''),
                    '评论内容': content.get('message', ''),
                    '评论时间': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ctime)) if ctime else "未知时间",
                    '点赞数': like_count,
                    '评论等级': '二级评论',
                    '父评论ID': root,
                }
                sub_comments.append(comment)

            page = data["data"].get("page") or {}
            count = page.get("count", 0)
            size = page.get("size", ps) or ps
            if size <= 0:
                break
            page_count = (count + size - 1) // size
            if pn >= page_count:
                break
            pn += 1
            time.sleep(0.5)
        return sub_comments

    def _parse_comments(self, json_data: dict, oid: str, type_val: str) -> Tuple[List[Dict], Optional[str]]:
        """解析评论数据"""
        comments: List[Dict] = []
        data = json_data.get("data") or {}
        replies = data.get("replies") or []
        if not replies:
            if data.get("cursor", {}).get("is_end", True):
                return comments, None
            return comments, None

        for item in replies:
            ctime = item.get('ctime')
            like_count = item.get('like', 0)
            content = item.get('content', {})
            reply_control = item.get('reply_control', {})
            member = item.get('member', {})
            rpid = item.get('rpid', 0)
            reply_count = item.get('count', 0)

            comment = {
                'uid': member.get('mid', ''),
                '昵称': member.get('uname', ''),
                '性别': member.get('sex', ''),
                '地区': reply_control.get('location', '').replace('IP属地：', '').strip(),
                '签名': member.get('sign', ''),
                '等级': member.get('level_info', {}).get('current_level', ''),
                '评论内容': content.get('message', ''),
                '评论时间': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ctime)) if ctime else "未知时间",
                '点赞数': like_count,
                '评论等级': '一级评论',
                '父评论ID': '',
            }
            comments.append(comment)

            if reply_count and rpid:
                comments.extend(self._fetch_sub_comments(oid, type_val, rpid, ps=20))

        next_offset = (data.get('cursor') or {}).get('pagination_reply', {}).get('next_offset')
        return comments, next_offset

    def fetch_all(self, video_id_or_url: str, max_pages: Optional[int] = None) -> List[Dict]:
        """获取视频所有评论"""
        oid = video_id_or_url.strip()
        if oid.startswith("https://"):
            from urllib.parse import urlparse
            parsed = urlparse(oid)
            if parsed.netloc in ["www.bilibili.com", "m.bilibili.com"]:
                parts = parsed.path.strip('/').split('/')
                for p in parts:
                    if p.startswith("BV") or p.startswith("AV") or p.startswith("av"):
                        oid = p
                        break

        base_params = {
            'oid': oid,
            'type': '1',
            'mode': '3',
            'plat': '1',
            'seek_rpid': '',
            'web_location': '1315875',
        }

        all_comments: List[Dict] = []
        next_offset: Optional[str] = ""
        page = 1

        while True:
            if max_pages and page > max_pages:
                break

            pagination_str = json.dumps({"offset": next_offset}, separators=(',', ':'))
            params = dict(base_params)
            params['pagination_str'] = pagination_str

            wts = int(time.time())
            params['wts'] = wts
            params['w_rid'] = compute_w_rid(params, wts)

            data = self._fetch(MAIN_API, params)
            comments, next_offset = self._parse_comments(data, oid, '1')
            if not comments:
                break

            all_comments.extend(comments)

            if next_offset is None:
                break
            page += 1
            time.sleep(1)

        return all_comments

    def save_to_csv(self, rows: List[Dict], filename: str):
        """保存评论到CSV文件"""
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)