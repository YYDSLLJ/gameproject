# -*- coding: utf-8 -*-
"""
B站爬虫

参考 bilibili_spider_view 项目，使用WBI签名获取完整数据
"""

import re
import time
import zlib
import json
import hashlib
import requests
from urllib.parse import quote
from . import BaseSpider, SpiderRegistry


# WBI签名盐
_WBI_SECRET = "ea1db124af3c7062474693fa704f4ff8"


def compute_w_rid(params, wts):
    """计算WBI签名 w_rid"""
    keys_order = ['mode', 'oid', 'pagination_str', 'plat', 'seek_rpid', 'type', 'web_location']
    items = []
    for key in keys_order:
        val = params.get(key, '')
        if key == 'pagination_str':
            val = quote(str(val), safe='')
        items.append(f"{key}={val}")
    items.append(f"wts={wts}")
    s = '&'.join(items) + _WBI_SECRET
    return hashlib.md5(s.encode('utf-8')).hexdigest()


class BilibiliSpider(BaseSpider):
    """B站爬虫"""

    URL_PATTERNS = [
        r'bilibili\.com/video/(BV[\w]+)',
        r'bilibili\.com/video/(bv[\w]+)',
        r'BV[\w]{10}',
    ]

    BASE_URL = 'https://api.bilibili.com'

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
    }

    def __init__(self, cookie='', proxy=None, use_proxy=True):
        self.cookie = cookie
        self.proxy = proxy
        self.use_proxy = use_proxy
        self.HEADERS = self.HEADERS.copy()
        if cookie:
            self.HEADERS['Cookie'] = cookie

    def _get_proxies(self):
        """获取代理配置"""
        if self.use_proxy and self.proxy:
            return {
                'http': self.proxy,
                'https': self.proxy,
            }
        return None

    def _requests_with_fallback(self, url, method='get', **kwargs):
        """发送请求，代理失败时回退到直接连接"""
        proxies = kwargs.pop('proxies', None)

        # 先尝试带代理
        if proxies:
            try:
                if method == 'get':
                    resp = requests.get(url, **kwargs)
                else:
                    resp = requests.post(url, **kwargs)
                return resp
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                # 代理失败，回退到不带代理
                print(f"代理失败，回退到直接连接: {e}")
                if method == 'get':
                    return requests.get(url, **kwargs)
                else:
                    return requests.post(url, **kwargs)
        else:
            if method == 'get':
                return requests.get(url, **kwargs)
            else:
                return requests.post(url, **kwargs)

    @classmethod
    def extract_bvid(cls, url):
        """从URL提取BV号"""
        match = re.search(r'(BV[\w]{10})', url)
        if match:
            return match.group(1)
        return None

    def get_video_info(self, bvid, retries=3):
        """获取视频基本信息"""
        import time
        url = f'{self.BASE_URL}/x/web-interface/view'
        params = {'bvid': bvid}

        for attempt in range(retries):
            try:
                resp = self._requests_with_fallback(url, params=params, headers=self.HEADERS, proxies=self._get_proxies(), timeout=15)
                if resp.status_code == 412:
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    raise Exception("B站API被拦截(412)")
                data = resp.json()
                break
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                raise Exception(f"网络错误: {e}")

        if data['code'] != 0:
            raise Exception(f"B站API错误: {data.get('message', 'unknown')}")

        detail = data['data']

        return {
            'platform': 'bilibili',
            'platform_id': bvid,
            'title': detail.get('title', ''),
            'author': detail.get('owner', {}).get('name', ''),
            'author_face': detail.get('owner', {}).get('face', ''),
            'cover': detail.get('pic', ''),
            'url': f'https://www.bilibili.com/video/{bvid}',
            'duration_ms': detail.get('duration', 0) * 1000,
            'extra_data': {
                'desc': detail.get('desc', ''),
                'tname': detail.get('tname', ''),
                'pubdate': detail.get('pubdate', 0),
            }
        }

    def get_video_stats(self, bvid, retries=3):
        """获取视频统计数据"""
        import time
        url = f'{self.BASE_URL}/x/web-interface/view'
        params = {'bvid': bvid}

        for attempt in range(retries):
            try:
                resp = self._requests_with_fallback(url, params=params, headers=self.HEADERS, proxies=self._get_proxies(), timeout=15)
                if resp.status_code == 412:
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    raise Exception("B站API被拦截(412)")
                data = resp.json()
                break
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                raise Exception(f"网络错误: {e}")

        if data['code'] != 0:
            raise Exception(f"B站API错误: {data.get('message', 'unknown')}")

        stat = data['data'].get('stat', {})

        return {
            'view_count': stat.get('view', 0),
            'like_count': stat.get('like', 0),
            'coin_count': stat.get('coin', 0),
            'collect_count': stat.get('favorite', 0),
            'share_count': stat.get('share', 0),
            'comment_count': stat.get('reply', 0),
            'danmaku_count': stat.get('danmaku', 0),
        }

    def get_comments(self, bvid, page=1, page_size=20, retries=3):
        """获取评论列表（使用WBI签名）"""
        # 获取视频信息（aid）
        info = self._get_video_info_basic(bvid)
        if not info:
            return []

        oid = str(info.get('aid', ''))
        if not oid:
            return []

        all_comments = []
        next_offset = ""
        max_pages = page

        base_params = {
            'oid': oid,
            'type': '1',
            'mode': '3',
            'plat': '1',
            'seek_rpid': '',
            'web_location': '1315875',
        }

        page_num = 1
        while True:
            if max_pages and page_num > max_pages:
                break

            pagination_str = json.dumps({"offset": next_offset}, separators=(',', ':'))
            params = dict(base_params)
            params['pagination_str'] = pagination_str
            wts = int(time.time())
            params['wts'] = wts
            params['w_rid'] = compute_w_rid(params, wts)

            data = None
            for attempt in range(retries):
                try:
                    resp = self._requests_with_fallback(
                        f'{self.BASE_URL}/x/v2/reply/wbi/main',
                        params=params,
                        headers=self.HEADERS,
                        proxies=self._get_proxies(),
                        timeout=15
                    )
                    if resp.status_code == 412:
                        if attempt < retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        break
                    data = resp.json()
                    break
                except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                    if attempt < retries - 1:
                        time.sleep(1)
                        continue
                    return []

            if data is None or data.get('code') != 0:
                break

            replies = data.get('data', {}).get('replies', []) or []
            if not replies:
                break

            for item in replies:
                ctime = item.get('ctime', 0)
                content = item.get('content', {})
                reply_control = item.get('reply_control', {})
                member = item.get('member', {})
                rpid = item.get('rpid', 0)
                reply_count = item.get('count', 0)

                comment = {
                    'content': content.get('message', ''),
                    'user_name': member.get('uname', ''),
                    'user_level': member.get('level_info', {}).get('current_level', 0),
                    'gender': member.get('sex', ''),
                    'region': reply_control.get('location', ''),
                    'created_at': ctime,
                }
                all_comments.append(comment)

                # 获取子评论
                if reply_count > 0 and rpid:
                    sub_comments = self._get_sub_comments(oid, rpid)
                    all_comments.extend(sub_comments)

            # 获取下一页offset
            cursor = data.get('data', {}).get('cursor', {}) or {}
            next_offset = cursor.get('pagination_reply', {}).get('next_offset')
            if not next_offset:
                break

            page_num += 1
            time.sleep(1.5)

        return all_comments

    def _get_sub_comments(self, oid, root, ps=20):
        """获取子评论"""
        sub_comments = []
        pn = 1

        while True:
            params = {
                'oid': oid,
                'type': '1',
                'root': root,
                'ps': ps,
                'pn': pn,
                'web_location': '333.788',
            }

            try:
                resp = self._requests_with_fallback(
                    'https://api.bilibili.com/x/v2/reply/reply',
                    params=params,
                    headers=self.HEADERS,
                    proxies=self._get_proxies(),
                    timeout=15
                )
                data = resp.json()
            except:
                break

            if not data.get('data') or not data['data'].get('replies'):
                break

            for reply in data['data']['replies']:
                ctime = reply.get('ctime', 0)
                like_count = reply.get('like', 0)
                content = reply.get('content', {})
                reply_control = reply.get('reply_control', {})
                member = reply.get('member', {})

                sub_comments.append({
                    'content': content.get('message', ''),
                    'user_name': member.get('uname', ''),
                    'user_level': member.get('level_info', {}).get('current_level', 0),
                    'gender': member.get('sex', ''),
                    'region': reply_control.get('location', ''),
                    'created_at': ctime,
                })

            page = data['data'].get('page', {})
            count = page.get('count', 0)
            size = page.get('size', ps) or ps
            if size <= 0:
                break
            page_count = (count + size - 1) // size
            if pn >= page_count:
                break
            pn += 1
            time.sleep(1.5)

        return sub_comments

    def get_danmaku(self, bvid, retries=3):
        """获取弹幕列表（使用WBI签名分段API）

        参考 test_movie/danmaku_crawler.py 的实现，逻辑完全一致
        """
        # 导入protobuf
        try:
            from .dm_pb2 import DmSegDanmaku
            has_pb2 = True
        except ImportError:
            has_pb2 = False

        # 获取视频信息（cid, pid, duration）
        info = self._get_video_info_basic(bvid)
        if not info:
            return self._get_danmaku_xml(bvid, retries)

        oid = info['cid']
        pid = info.get('aid', 0)

        all_danmaku = []
        seen_ids = set()
        seg_index = 1

        # 基准URL
        base_url = "https://api.bilibili.com/x/v2/dm/wbi/web/seg.so"

        # 无上限循环，直到没有新数据才退出（与测试代码一致）
        while True:
            any_data = False

            # 每段20分钟，分3个时间段请求（0-120000ms, 120000-240000ms, 240000-360000ms）
            for ps in range(0, 20 * 60 * 1000, 120000):
                pe = ps + 120000

                wts = int(time.time())
                params = {
                    "type": 1,
                    "oid": oid,
                    "pid": pid,
                    "segment_index": seg_index,
                    "pull_mode": 1 if seg_index == 1 and ps == 0 else 0,
                    "ps": ps,
                    "pe": pe,
                    "web_location": 1315873,
                    "mode": 0,
                    "pagination_str": "",
                    "plat": 0,
                    "seek_rpid": "",
                    "wts": wts,
                }
                params["w_rid"] = compute_w_rid(params, wts)

                try:
                    resp = self._requests_with_fallback(
                        base_url,
                        params=params,
                        headers=self.HEADERS,
                        proxies=self._get_proxies(),
                        timeout=15
                    )
                    if resp.status_code == 200 and has_pb2:
                        try:
                            dm_data = DmSegDanmaku().parse(resp.content)
                            for d in dm_data.elems or []:
                                if d.id not in seen_ids:
                                    all_danmaku.append({
                                        'id': d.id,
                                        'content': d.content,
                                        'progress': d.progress,
                                        'color': d.color,
                                        'progress_ms': d.progress,  # 毫秒
                                        'ctime': d.ctime,
                                        'created_at': d.ctime,
                                    })
                                    seen_ids.add(d.id)
                                    any_data = True
                        except Exception as e:
                            # Protobuf解析失败，尝试回退到XML
                            print(f"弹幕Protobuf解析错误 [{seg_index}/{ps}]: {e}")
                            xml_result = self._get_danmaku_xml(bvid, retries)
                            if xml_result:
                                return xml_result
                    elif resp.status_code == 200 and not has_pb2:
                        # 没有protobuf模块，回退到XML
                        print("Protobuf模块不可用，回退到XML方式")
                        return self._get_danmaku_xml(bvid, retries)
                except Exception:
                    pass

                time.sleep(1.5)

            if not any_data:
                break

            seg_index += 1
            time.sleep(1.5)

        # 如果protobuf方式失败或没有数据，回退到XML方式
        if not all_danmaku:
            return self._get_danmaku_xml(bvid, retries)

        return all_danmaku

    def _get_danmaku_xml(self, bvid, retries=3):
        """获取弹幕列表（旧版XML方式，备用）"""
        import xml.etree.ElementTree as ET

        # 先获取cid
        info = self._get_video_info_basic(bvid)
        if not info:
            return []

        cid = info['cid']
        if not cid:
            return []

        # 获取弹幕
        danmaku_url = f'https://api.bilibili.com/x/v1/dm/list.so'
        params = {'oid': cid}

        for attempt in range(retries):
            try:
                resp = self._requests_with_fallback(danmaku_url, params=params, headers=self.HEADERS, proxies=self._get_proxies(), timeout=15)
                if resp.status_code == 412:
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return []
                break
            except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as e:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return []

        # 处理压缩数据
        content = resp.content
        content_encoding = resp.headers.get('Content-Encoding', '').lower()

        if content_encoding == 'deflate':
            try:
                content = zlib.decompress(resp.content)
            except zlib.error:
                try:
                    content = zlib.decompress(resp.content, -zlib.MAX_WBITS)
                except:
                    pass
        elif content_encoding == 'gzip':
            try:
                content = zlib.decompress(resp.content, 16 + zlib.MAX_WBITS)
            except:
                pass

        # 解析XML
        danmaku_list = []
        try:
            xml_text = content.decode('utf-8') if isinstance(content, bytes) else content
            root = ET.fromstring(xml_text)
            for d in root.findall('.//d'):
                p_parts = d.get('p', '0').split(',')
                progress_sec = float(p_parts[0])
                danmaku_list.append({
                    'content': d.text or '',
                    'progress_ms': int(progress_sec * 1000),
                    'created_at': int(p_parts[4]) if len(p_parts) > 4 else 0,
                })
        except Exception as e:
            print(f"弹幕XML解析错误: {e}")

        return danmaku_list

    def _get_video_info_basic(self, bvid):
        """获取视频基本信息（cid, aid, duration）"""
        url = f'{self.BASE_URL}/x/web-interface/view'
        params = {'bvid': bvid}

        try:
            resp = self._requests_with_fallback(url, params=params, headers=self.HEADERS, proxies=self._get_proxies(), timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 0:
                    return {
                        'cid': data['data'].get('cid'),
                        'aid': data['data'].get('aid'),
                        'duration': data['data'].get('duration', 0),
                    }
        except:
            pass
        return None

    def crawl_comments_and_danmaku(self, bvid, max_comments=2000, max_danmaku=5000):
        """
        爬取视频的全部评论和弹幕

        Args:
            bvid: 视频BV号
            max_comments: 最大评论数（默认2000）
            max_danmaku: 最大弹幕数（默认5000）

        Returns:
            dict: {'comments': [...], 'danmaku': [...]}
        """
        # 爬取评论（使用WBI签名API，自动分页）
        all_comments = []
        page = 1
        page_size = 20
        consecutive_empty = 0

        while len(all_comments) < max_comments:
            comments = self.get_comments(bvid, page=page, page_size=page_size)
            if not comments:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
            else:
                consecutive_empty = 0
                all_comments.extend(comments)
            page += 1
            time.sleep(1.5)

        all_comments = all_comments[:max_comments]

        # 爬取弹幕（使用WBI签名分段API）
        danmaku = self.get_danmaku(bvid)
        all_danmaku = danmaku[:max_danmaku]

        return {
            'comments': all_comments,
            'danmaku': all_danmaku
        }


# 注册爬虫
SpiderRegistry.register('bilibili', BilibiliSpider)
