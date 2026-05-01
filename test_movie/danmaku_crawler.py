# -*- coding: utf-8 -*-
"""
弹幕爬虫 - 参考bilibili_spider_view/spider/danmaku.py
"""

import csv
import time
import datetime as _dt
import re
from typing import List, Set

import bili_http
import wbi
import dm_pb2
BiliSession = bili_http.BiliSession
load_cookie = bili_http.load_cookie
compute_w_rid = wbi.compute_w_rid
DmSegDanmaku = dm_pb2.DmSegDanmaku


class DanmakuCrawler:
    """
    B站弹幕爬虫
    - 使用WBI签名分段API
    - 自动重试和回退
    """
    BASE = "https://api.bilibili.com/x/v2/dm/wbi/web/seg.so"

    def __init__(self, video_url: str, cookie: str = None) -> None:
        self.bv_id = self._extract_bv_id(video_url)
        referer = f"https://www.bilibili.com/video/{self.bv_id}"
        self.session = BiliSession(referer=referer, cookie=cookie)
        self.oid, self.pid, self.duration = self._get_oid_pid_duration(self.bv_id)
        self.all_danmaku: List = []
        self._seen: Set[int] = set()

    @staticmethod
    def _extract_bv_id(url: str) -> str:
        m = re.search(r"/(BV\w+|av\d+)", url)
        if not m:
            raise ValueError("无法从链接中提取BV号或av号")
        return m.group(1)

    def _get_oid_pid_duration(self, bv: str):
        """获取视频cid、aid、时长"""
        if bv.startswith("BV"):
            url = f"https://api.bilibili.com/x/player/pagelist?bvid={bv}"
        else:
            url = f"https://api.bilibili.com/x/player/pagelist?aid={bv[2:]}"
        r = self.session.get(url)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0 or not data.get("data"):
            raise RuntimeError(f"B站接口返回错误: {data.get('message') or '空数据'}")
        cid = data["data"][0]["cid"]
        duration = data["data"][0].get("duration", 0)
        aid = data["data"][0].get("aid") or self._get_aid_from_bvid(bv)
        return cid, aid, duration

    def _get_aid_from_bvid(self, bv: str):
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv}"
        data = self.session.get_json(url)
        if data.get("code") == 0:
            return data["data"].get("aid")
        raise RuntimeError("无法通过bvid获取aid")

    def _fetch_segment(self, segment_index: int, ps: int, pe: int):
        """获取单个分段的弹幕"""
        wts = int(time.time())
        params = {
            "type": 1,
            "oid": self.oid,
            "pid": self.pid,
            "segment_index": segment_index,
            "pull_mode": 1 if segment_index == 1 and ps == 0 else 0,
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
        resp = self.session.get(self.BASE, params=params)
        if resp.status_code == 200:
            return DmSegDanmaku().parse(resp.content).elems
        return []

    def crawl_all_segments(self, sleep: float = 0.5):
        """爬取所有分段的弹幕"""
        seg_index = 1
        while True:
            any_data = False
            for ps in range(0, 20 * 60 * 1000, 120000):
                pe = ps + 120000
                elems = self._fetch_segment(seg_index, ps, pe)
                for d in elems or []:
                    if d.id not in self._seen:
                        self.all_danmaku.append(d)
                        self._seen.add(d.id)
                        any_data = True
                time.sleep(sleep)
            if not any_data:
                break
            seg_index += 1
            time.sleep(sleep)

    def save_to_csv(self, filename: str = "bilibili_danmaku.csv"):
        """保存弹幕到CSV文件"""
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["出现时间", "弹幕内容", "颜色", "发送时间"])
            for d in self.all_danmaku:
                appear = f"{d.progress // 60000:02d}:{(d.progress // 1000) % 60:02d}"
                color = f"#{d.color:06X}"
                send = _dt.datetime.fromtimestamp(d.ctime).strftime("%m-%d %H:%M")
                writer.writerow([appear, d.content, color, send])
        return len(self.all_danmaku)