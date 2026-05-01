# -*- coding: utf-8 -*-
"""
B站可视化大屏
完整实现，支持弹幕、评论、省份分布等
"""

from .registry import VizRegistry


@VizRegistry.register('bilibili')
class BilibiliVisualization:
    """
    B站视频可视化大屏

    支持的图表：
    - 三色环：评论数/弹幕数/播放量
    - 四色环：点赞/投币/收藏/转发
    - 省份热力地图
    - 情感分析（弹幕/评论）
    - 用户等级分布
    - 性别比例
    - 热度趋势折线图
    - 时间线视图（评论+弹幕联合）
    - 弹幕分段分析（动态分段）
    - 词云（弹幕/评论）
    """

    # 省份映射（简写 → 全称）
    PROV_MAP = {
        '北京': '北京市', '天津': '天津市', '上海': '上海市', '重庆': '重庆市',
        '河北': '河北省', '山西': '山西省', '内蒙古': '内蒙古自治区',
        '辽宁': '辽宁省', '吉林': '吉林省', '黑龙江': '黑龙江省',
        '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省', '福建': '福建省',
        '江西': '江西省', '山东': '山东省', '河南': '河南省', '湖北': '湖北省',
        '湖南': '湖南省', '广东': '广东省', '广西': '广西壮族自治区', '海南': '海南省',
        '四川': '四川省', '贵州': '贵州省', '云南': '云南省', '西藏': '西藏自治区',
        '陕西': '陕西省', '甘肃': '甘肃省', '青海': '青海省', '宁夏': '宁夏回族自治区',
        '新疆': '新疆维吾尔自治区', '香港': '香港特别行政区', '澳门': '澳门特别行政区', '台湾': '台湾省'
    }

    # 小区域省份
    MINOR_PROVS = ['北京', '上海', '天津', '重庆', '香港', '澳门', '台湾']

    # 中国省份列表（用于地图）
    CHINA_PROVINCES = [
        '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
        '江苏', '浙江', '安徽', '福建', '江西', '山东',
        '河南', '湖北', '湖南', '广东', '广西', '海南',
        '四川', '贵州', '云南', '西藏', '陕西', '甘肃',
        '青海', '宁夏', '新疆', '北京', '天津', '上海', '重庆',
        '香港', '澳门', '台湾'
    ]

    def __init__(self):
        self.platform = 'bilibili'

    def get_summary(self, video, conn):
        """获取视频概览数据"""
        from sqlalchemy import text

        vid = video.id
        comments_cnt = conn.execute(
            text("SELECT COUNT(*) FROM comments WHERE video_id=:vid"),
            {"vid": vid}
        ).scalar() or 0
        danmaku_cnt = conn.execute(
            text("SELECT COUNT(*) FROM danmaku WHERE video_id=:vid"),
            {"vid": vid}
        ).scalar() or 0

        stats = video.stats.first()
        return {
            "tri": {
                "评论数": int(comments_cnt),
                "弹幕数": int(danmaku_cnt),
                "播放量": int(stats.view_count if stats else 0)
            },
            "quad": {
                "点赞": int(stats.like_count if stats else 0),
                "投币": int(stats.coin_count if stats else 0),
                "收藏": int(stats.collect_count if stats else 0),
                "转发": int(stats.share_count if stats else 0)
            }
        }

    def get_region_map(self, video, conn):
        """获取省份分布数据"""
        from collections import Counter
        from sqlalchemy import text

        vid = video.id
        prov_counter = Counter()
        foreign_counter = Counter()

        rows = conn.execute(
            text("SELECT region FROM comments WHERE video_id=:vid AND region IS NOT NULL AND region != ''"),
            {"vid": vid}
        ).fetchall()

        for (r,) in rows:
            typ, name = self._normalize_region(r)
            if typ == "province":
                prov_counter[name] += 1
            elif typ == "foreign":
                foreign_counter[name] += 1

        provinces = [
            {"name": self.PROV_MAP.get(p, p), "value": int(prov_counter.get(p, 0))}
            for p in self.CHINA_PROVINCES
        ]
        minor = [
            {"name": self.PROV_MAP.get(p, p), "value": int(prov_counter.get(p, 0))}
            for p in self.MINOR_PROVS if prov_counter.get(p, 0) > 0
        ]
        minor.sort(key=lambda x: x["value"], reverse=True)

        foreign = [
            {"name": k, "value": int(v)}
            for k, v in foreign_counter.most_common(20)
        ]

        # 检查是否有有效region数据
        has_region_data = sum(prov_counter.values()) > 0 or sum(foreign_counter.values()) > 0

        return {
            "provinces": provinces,
            "minor": minor,
            "foreign": foreign,
            "unknown": sum(1 for r, in rows if not self._normalize_region(r)[1]),
            "has_region_data": has_region_data,
            "message": "B站API已停止返回IP属地数据，地图暂无评论区域分布" if not has_region_data else None
        }

    def _normalize_region(self, name):
        """标准化地区名称"""
        if not name:
            return "unknown", None

        # 去掉"IP属地："前缀（如果有）
        if '：' in name:
            name = name.split('：')[-1]
        elif ':' in name:
            name = name.split(':')[-1]

        # 已知省份
        for prov in self.CHINA_PROVINCES:
            if prov in name or name in prov:
                return "province", prov

        # 国外
        foreign_keywords = ['美国', '日本', '韩国', '英国', '法国', '德国', '俄罗斯', '加拿大',
                          '澳大利亚', '印度', '巴西', '东南亚', '美国', '日本', '韩国']
        for kw in foreign_keywords:
            if kw in name:
                return "foreign", name

        return "unknown", name

    def get_sentiment(self, video, conn, limit=5000, region=None):
        """获取情感分析数据"""
        from collections import Counter
        from sqlalchemy import text

        vid = video.id
        region_filter = self._build_region_filter(region)

        com = Counter({-1: 0, 0: 0, 1: 0})
        query = f"SELECT content FROM comments WHERE video_id=:vid{region_filter} LIMIT :lim"
        rows = conn.execute(
            text(query),
            {"vid": vid, "lim": limit}
        ).fetchall()
        for (txt,) in rows:
            com[self._classify_sentiment(txt or "")] += 1

        dm = Counter({-1: 0, 0: 0, 1: 0})
        rows = conn.execute(
            text("SELECT content FROM danmaku WHERE video_id=:vid LIMIT :lim"),
            {"vid": vid, "lim": limit}
        ).fetchall()
        for (txt,) in rows:
            dm[self._classify_sentiment(txt or "")] += 1

        pack = lambda c: {"负面": int(c[-1]), "中性": int(c[0]), "正面": int(c[1])}
        return {"comments": pack(com), "danmaku": pack(dm)}

    def get_sentiment_examples(self, video, conn, limit=100):
        """获取情感分析示例（各一条正面、中性、负面评论）"""
        from sqlalchemy import text

        vid = video.id
        examples = {"正面": None, "中性": None, "负面": None}

        rows = conn.execute(
            text("SELECT content, sentiment FROM comments WHERE video_id=:vid AND sentiment IS NOT NULL ORDER BY RAND() LIMIT :lim"),
            {"vid": vid, "lim": limit}
        ).fetchall()

        for txt, sen in rows:
            if not txt:
                continue
            if sen == 1 and not examples["正面"]:
                examples["正面"] = txt
            elif sen == 0 and not examples["中性"]:
                examples["中性"] = txt
            elif sen == -1 and not examples["负面"]:
                examples["负面"] = txt
            if all(examples.values()):
                break

        # 如果样本不够，随机补充
        if not all(examples.values()):
            rows = conn.execute(
                text("SELECT content FROM comments WHERE video_id=:vid ORDER BY RAND() LIMIT :lim"),
                {"vid": vid, "lim": limit}
            ).fetchall()
            for (txt,) in rows:
                if not txt:
                    continue
                sentiment = self._classify_sentiment(txt)
                label = {1: "正面", 0: "中性", -1: "负面"}[sentiment]
                if not examples[label]:
                    examples[label] = txt
                if all(examples.values()):
                    break

        return examples

    def _build_region_filter(self, region):
        """构建地区过滤SQL条件"""
        if not region:
            return ""
        # 省份名称映射 - 支持简称和全称
        matched_keys = [region]  # 保留原始输入

        for k, v in self.PROV_MAP.items():
            if region == k or region == v:
                matched_keys.append(k)
                matched_keys.append(v)
                break

        # 构建OR条件
        conditions = " OR ".join([f"region LIKE '%{k}%'" for k in matched_keys])
        return f" AND ({conditions})"

    def _classify_sentiment(self, text):
        """简单情感分类"""
        if not text:
            return 0
        try:
            from snownlp import SnowNLP
            score = SnowNLP(text).sentiments
            if score > 0.6:
                return 1
            elif score < 0.4:
                return -1
            return 0
        except:
            return 0

    def get_level_pie(self, video, conn, region=None):
        """获取用户等级分布"""
        from sqlalchemy import text

        vid = video.id
        region_filter = self._build_region_filter(region)
        rows = conn.execute(
            text(f"SELECT COALESCE(user_level,0) AS lvl, COUNT(*) FROM comments WHERE video_id=:vid{region_filter} GROUP BY lvl"),
            {"vid": vid}
        ).fetchall()
        return [
            {"name": f"Lv{int(l)}" if int(l) > 0 else "未知", "value": int(c)}
            for l, c in rows
        ]

    def get_gender_pie(self, video, conn, region=None):
        """获取性别比例"""
        from collections import Counter
        from sqlalchemy import text

        vid = video.id
        region_filter = self._build_region_filter(region)
        rows = conn.execute(
            text(f"SELECT COALESCE(gender,'中立') AS g, COUNT(*) FROM comments WHERE video_id=:vid{region_filter} GROUP BY g"),
            {"vid": vid}
        ).fetchall()

        def norm(g):
            g = (g or '').strip()
            return g if g in ('男', '女') else '中立'

        agg = Counter()
        for g, c in rows:
            agg[norm(g)] += int(c)
        return [{"name": k, "value": v} for k, v in agg.items()]

    def get_realtime_series(self, video, conn, bins=100):
        """获取评论+弹幕时间线"""
        from collections import defaultdict
        import datetime as dt
        from sqlalchemy import text

        vid = video.id

        # 获取时间范围 (使用 created_at 字段)
        cm_min = conn.execute(
            text("SELECT MIN(created_at) FROM comments WHERE video_id=:vid AND created_at IS NOT NULL"),
            {"vid": vid}
        ).scalar()
        cm_max = conn.execute(
            text("SELECT MAX(created_at) FROM comments WHERE video_id=:vid AND created_at IS NOT NULL"),
            {"vid": vid}
        ).scalar()
        dm_min = conn.execute(
            text("SELECT MIN(created_at) FROM danmaku WHERE video_id=:vid AND created_at IS NOT NULL"),
            {"vid": vid}
        ).scalar()
        dm_max = conn.execute(
            text("SELECT MAX(created_at) FROM danmaku WHERE video_id=:vid AND created_at IS NOT NULL"),
            {"vid": vid}
        ).scalar()

        times = [t for t in [cm_min, dm_min, cm_max, dm_max] if t]
        if not times:
            # 如果没有时间数据，尝试使用视频发布时间作为起始点
            pubdate = video.pubdate
            if pubdate:
                # 使用视频发布到现在的时间范围
                from datetime import datetime
                t0 = datetime.fromtimestamp(pubdate)
                t1 = datetime.utcnow()
                if t1 <= t0:
                    t1 = t0 + dt.timedelta(days=1)
                total = (t1 - t0).total_seconds() or 1
                bins = min(100, max(10, int(total // 3600)))
                edges = [t0 + dt.timedelta(seconds=i * total / bins) for i in range(bins + 1)]
                fmt = "%m-%d %H:%M"
                x = [edges[i].strftime(fmt) for i in range(bins)]
                return {"x": x, "comments": [0] * bins, "danmaku": [0] * bins}
            return {"x": [], "comments": [], "danmaku": []}

        t0, t1 = min(times), max(times)
        total = (t1 - t0).total_seconds() or 1
        bins = min(100, max(10, int(total // 3600)))
        edges = [t0 + dt.timedelta(seconds=i * total / bins) for i in range(bins + 1)]
        fmt = "%m-%d %H:%M"

        cm = [0] * bins
        if cm_min and cm_max:
            rows = conn.execute(
                text("SELECT created_at FROM comments WHERE video_id=:vid AND created_at IS NOT NULL"),
                {"vid": vid}
            ).fetchall()
            for (ts,) in rows:
                if not ts:
                    continue
                idx = min(bins - 1, int(((ts - t0).total_seconds()) * bins / total))
                cm[idx] += 1

        dm = [0] * bins
        if dm_min and dm_max:
            rows = conn.execute(
                text("SELECT created_at FROM danmaku WHERE video_id=:vid AND created_at IS NOT NULL"),
                {"vid": vid}
            ).fetchall()
            for (ts,) in rows:
                if not ts:
                    continue
                idx = min(bins - 1, int(((ts - t0).total_seconds()) * bins / total))
                dm[idx] += 1

        x = [edges[i].strftime(fmt) for i in range(bins)]
        return {"x": x, "comments": cm, "danmaku": dm}

    def get_invideo_series(self, video, conn, bins=100):
        """获取弹幕在视频内的时间分布"""
        from sqlalchemy import text

        vid = video.id
        row = conn.execute(
            text("SELECT MIN(FLOOR(progress_ms/1000)), MAX(FLOOR(progress_ms/1000)) FROM danmaku WHERE video_id=:vid AND progress_ms IS NOT NULL"),
            {"vid": vid}
        ).first()

        if not row or row[0] is None or row[1] is None or int(row[1]) <= int(row[0]):
            return {"x": [], "danmaku": []}

        t0, t1 = int(row[0]), int(row[1])
        span = max(1, t1 - t0)
        bins = min(100, max(10, span // 5))
        edges = [t0 + int(i * span / bins) for i in range(bins + 1)]
        dm = [0] * bins

        rows = conn.execute(
            text("SELECT FLOOR(progress_ms/1000) AS s FROM danmaku WHERE video_id=:vid AND progress_ms IS NOT NULL"),
            {"vid": vid}
        ).fetchall()
        for (sec,) in rows:
            s = int(sec)
            idx = min(bins - 1, int((s - t0) * bins / span))
            if 0 <= idx < bins:
                dm[idx] += 1

        fmt = lambda s: f"{int(s // 60):02d}:{int(s % 60):02d}"
        x = [fmt(edges[i]) for i in range(bins)]
        return {"x": x, "danmaku": dm}

    def get_danmaku_segments(self, video, conn, max_segments=10, min_danmaku=5):
        """
        动态分段弹幕分析

        算法：
        1. 根据弹幕密度自动分段时间线
        2. 高密度区域自动切分为更短片段
        3. 低密度区域合并为更长片段
        4. 保证每个分段有足够样本
        """
        from collections import Counter
        from sqlalchemy import text

        vid = video.id

        # 获取弹幕 progress_ms 范围
        row = conn.execute(
            text("SELECT MIN(progress_ms), MAX(progress_ms), COUNT(*) FROM danmaku WHERE video_id=:vid AND progress_ms IS NOT NULL"),
            {"vid": vid}
        ).first()

        if not row or row[0] is None or row[1] is None or row[2] < min_danmaku:
            return {"segments": [], "total": 0}

        t0, t1, total = int(row[0]), int(row[1]), int(row[2])
        span = max(1, t1 - t0)

        # 计算理想分段数（根据弹幕密度）
        density = total / span  # 弹幕密度（个/毫秒）
        ideal_segments = min(max_segments, max(3, int(density * span / 1000 / 10)))  # 每10秒一段

        # 计算每个分段的弹幕数
        segment_size = span / ideal_segments
        segment_counts = [0] * ideal_segments

        rows = conn.execute(
            text("SELECT FLOOR(progress_ms/1000) AS s FROM danmaku WHERE video_id=:vid AND progress_ms IS NOT NULL"),
            {"vid": vid}
        ).fetchall()

        for (sec,) in rows:
            s = int(sec) * 1000  # 转回毫秒
            idx = min(ideal_segments - 1, int((s - t0) / segment_size))
            if 0 <= idx < ideal_segments:
                segment_counts[idx] += 1

        # 动态调整：合并小分段
        adjusted = []
        current = []
        for i, count in enumerate(segment_counts):
            current.append(i)
            if count >= min_danmaku or len(current) >= 3:
                adjusted.append(current)
                current = []

        if current:
            if adjusted:
                # 合并到前一个
                adjusted[-1].extend(current)
            else:
                adjusted.append(current)

        # 生成segments
        segments = []
        for seg_indices in adjusted:
            t_start = t0 + int(seg_indices[0] * segment_size)
            t_end = t0 + int((seg_indices[-1] + 1) * segment_size)
            seg_danmaku = segment_counts[seg_indices[0]:seg_indices[-1] + 1]

            # 获取该时间段的弹幕
            dm_rows = conn.execute(
                text("SELECT content FROM danmaku WHERE video_id=:vid AND progress_ms BETWEEN :s AND :e"),
                {"vid": vid, "s": t_start, "e": t_end}
            ).fetchall()

            # 情感分析
            sentiment = Counter({-1: 0, 0: 0, 1: 0})
            texts = []
            for (txt,) in dm_rows:
                if txt:
                    texts.append(txt)
                    sentiment[self._classify_sentiment(txt)] += 1

            # 关键词提取
            keywords = self._extract_keywords(texts)

            segments.append({
                "time_start": t_start // 1000,
                "time_end": t_end // 1000,
                "time_start_str": self._fmt_time(t_start // 1000),
                "time_end_str": self._fmt_time(t_end // 1000),
                "count": sum(seg_danmaku),
                "sentiment": {
                    "正面": sentiment[1],
                    "中性": sentiment[0],
                    "负面": sentiment[-1]
                },
                "keywords": keywords[:5]
            })

        return {"segments": segments, "total": total}

    def _fmt_time(self, seconds):
        """格式化时间"""
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    def _extract_keywords(self, texts, topK=5):
        """提取关键词"""
        if not texts:
            return []
        try:
            import jieba.analyse
            text = " ".join(texts[:1000])  # 限制数量
            keywords = jieba.analyse.extract_tags(text, topK=topK, withWeight=False)
            return keywords
        except:
            return []

    def get_heat_trend(self, video, conn):
        """获取热度趋势"""
        from sqlalchemy import text
        from datetime import datetime, timedelta
        from ..analysis.heat import calc_peak_and_trend, estimate_heat_trend

        vid = video.id

        # 获取视频发布时间用于计算实际日期
        pubdate_timestamp = video.pubdate
        if pubdate_timestamp:
            # 将Unix时间戳转换为日期
            pubdate_date = datetime.fromtimestamp(pubdate_timestamp)
        else:
            pubdate_date = datetime.utcnow()

        # 获取历史统计数据
        rows = conn.execute(
            text("""
                SELECT stat_date, view_count, like_count, coin_count,
                       collect_count, share_count, comment_count, danmaku_count,
                       heat_score
                FROM video_stats
                WHERE video_id=:vid
                ORDER BY stat_date
            """),
            {"vid": vid}
        ).fetchall()

        # 构建统计数据列表
        stats_list = []
        for r in rows:
            stats_list.append({
                'stat_date': r[0],
                'view_count': r[1] or 0,
                'like_count': r[2] or 0,
                'coin_count': r[3] or 0,
                'collect_count': r[4] or 0,
                'share_count': r[5] or 0,
                'comment_count': r[6] or 0,
                'danmaku_count': r[7] or 0,
            })

        # 查询评论和弹幕的实际每日活动量（基于created_at）
        # 始终获取，用于热度计算参考
        activity_rows = conn.execute(
            text("""
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM (
                    SELECT created_at FROM comments WHERE video_id=:vid AND created_at IS NOT NULL
                    UNION ALL
                    SELECT created_at FROM danmaku WHERE video_id=:vid AND created_at IS NOT NULL
                ) AS all_activity
                GROUP BY DATE(created_at)
                ORDER BY day
            """),
            {"vid": vid}
        ).fetchall()

        # 构建每日活动量字典（相对于发布日的偏移天数）
        # 注意：只使用日期部分，忽略时间差异
        activity_by_day = {}
        for row in activity_rows:
            day_str = row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0])
            try:
                day_date = datetime.strptime(day_str, '%Y-%m-%d')
                # 使用date()忽略时间，只计算天数差异后+1使发布日=Day1
                day_offset = (day_date.date() - pubdate_date.date()).days + 1
                if day_offset > 0:
                    activity_by_day[day_offset] = row[1]
            except:
                pass

        # 始终优先使用基于评论/弹幕活动的热度估算
        # 因为用户要求热度与评论/弹幕的实际发布时间相关
        if activity_by_day:
            days_old = video.pubdate_days_ago
            # 找出活动量最大的日期
            peak_activity_day = max(activity_by_day, key=activity_by_day.get)
            # 使用当前最新统计
            if stats_list:
                current_stats = stats_list[-1]
            else:
                current_stats = {
                    'view_count': 0, 'like_count': 0, 'coin_count': 0,
                    'collect_count': 0, 'share_count': 0, 'comment_count': 0, 'danmaku_count': 0
                }
            result = estimate_heat_trend(current_stats, days_old, peak_day=peak_activity_day, activity_by_day=activity_by_day)
        elif len(stats_list) >= 2:
            # 没有活动数据时，使用传统统计计算
            result = calc_peak_and_trend(stats_list)
        else:
            # 完全没有数据
            result = {'peak_value': 0, 'peak_day': 1, 'current_heat': 0, 'trend': [], 'days_total': 0}

        # 转换日期为实际日期（用于估算曲线）
        trend = result.get('trend', [])
        if result.get('estimated') and trend:
            # 计算视频发布起始日期
            start_date = pubdate_date
            for t in trend:
                day = t.get('day', 0)
                if day > 0:
                    actual_date = start_date + timedelta(days=day - 1)
                    t['date'] = actual_date.strftime('%m-%d')

        return {
            "current": result.get('current_heat', 0),
            "peak": result.get('peak_value', 0),
            "peak_day": result.get('peak_day', 0),
            "peak_date": result.get('peak_date', None),
            "dates": [t['date'] for t in result.get('trend', [])],
            "scores": [t['heat'] for t in result.get('trend', [])],
            "days_total": result.get('days_total', 0),
            "estimated": result.get('estimated', False),
            "pubdate": pubdate_timestamp  # 返回发布的时间戳供前端使用
        }
