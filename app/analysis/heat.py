# -*- coding: utf-8 -*-
"""
热度算法

模型：单日热度 = 基础互动分 × 增长趋势分 × 时间衰减分

参考文档：/mnt/d/Notebck/heat_model.md
"""

import math
from datetime import datetime, timedelta


# 权重配置
WEIGHTS = {
    'like': 1,
    'coin': 2,
    'collect': 2,
    'share': 5,
    'comment': 2,
    'danmaku': 1,
}


def calc_interaction_base(stats):
    """
    计算基础互动分（对数加权和）

    Args:
        stats: dict 包含各互动指标

    Returns:
        float 基础互动分
    """
    total = (
        stats.get('like_count', 0) * WEIGHTS['like'] +
        stats.get('coin_count', 0) * WEIGHTS['coin'] +
        stats.get('collect_count', 0) * WEIGHTS['collect'] +
        stats.get('share_count', 0) * WEIGHTS['share'] +
        stats.get('comment_count', 0) * WEIGHTS['comment'] +
        stats.get('danmaku_count', 0) * WEIGHTS['danmaku']
    )
    return math.log(1 + total)


def calc_trend_score(daily_increment, historical_avg):
    """
    计算增长趋势分

    Args:
        daily_increment: 当日增量
        historical_avg: 历史日均增量

    Returns:
        float 趋势分，>1表示加速，<1表示减速
    """
    if historical_avg <= 0:
        return 1.5  # 新内容加权
    ratio = daily_increment / historical_avg
    return 1 + (ratio - 1) * 0.3


def calc_decay(days_old, base=7):
    """
    计算时间衰减分

    Args:
        days_old: 视频发布天数
        base: 衰减基准天数

    Returns:
        float 衰减系数，越小衰减越严重
    """
    return 1 / (1 + math.log(1 + days_old / base))


def calc_daily_heat(stats, days_old=1, daily_increment=0, historical_avg=0):
    """
    计算单日热度

    Args:
        stats: dict 包含 view_count, like_count, coin_count, collect_count,
               share_count, comment_count, danmaku_count
        days_old: int 视频发布天数
        daily_increment: int 当日互动增量
        historical_avg: float 历史日均互动量

    Returns:
        float 当日热度分数
    """
    base = calc_interaction_base(stats)
    trend = calc_trend_score(daily_increment, historical_avg)
    decay = calc_decay(days_old)

    heat = base * trend * decay
    return round(heat, 2)


def calc_peak_and_trend(video_stats_list):
    """
    根据历史统计数据计算峰值和趋势曲线

    Args:
        video_stats_list: list of dict，按日期排序的统计数据
            每项包含 stat_date, view_count, like_count, coin_count,
            collect_count, share_count, comment_count, danmaku_count

    Returns:
        dict: {
            'peak_value': 峰值热度,
            'peak_day': 峰值发生在第几天,
            'peak_date': 峰值日期,
            'current_heat': 当前热度,
            'trend': [{'date': str, 'heat': float}, ...],
            'days_total': 总天数
        }
    """
    if not video_stats_list:
        return None

    trend_data = []
    for i, stat in enumerate(video_stats_list):
        days = i + 1  # 第几天
        # 计算当日增量
        if i == 0:
            daily_inc = 0
            hist_avg = 0
        else:
            prev = video_stats_list[i - 1]
            daily_inc = _get_total_interaction(stat) - _get_total_interaction(prev)
            hist_avg = _get_total_interaction(stat) / days
            daily_inc = max(0, daily_inc)  # 防止负数

        heat = calc_daily_heat(
            stats={
                'view_count': stat.get('view_count', 0),
                'like_count': stat.get('like_count', 0),
                'coin_count': stat.get('coin_count', 0),
                'collect_count': stat.get('collect_count', 0),
                'share_count': stat.get('share_count', 0),
                'comment_count': stat.get('comment_count', 0),
                'danmaku_count': stat.get('danmaku_count', 0),
            },
            days_old=days,
            daily_increment=daily_inc,
            historical_avg=hist_avg
        )
        trend_data.append({
            'date': str(stat.get('stat_date', '')),
            'heat': heat,
            'day': days
        })

    # 找峰值
    peak = max(trend_data, key=lambda x: x['heat'])
    current = trend_data[-1] if trend_data else {'heat': 0, 'day': 1}

    return {
        'peak_value': peak['heat'],
        'peak_day': peak['day'],
        'peak_date': peak['date'],
        'current_heat': current['heat'],
        'trend': trend_data,
        'days_total': len(trend_data)
    }


def estimate_heat_trend(stats, days_old, peak_day=None, decay_rate=0.08, activity_by_day=None):
    """
    估算热度趋势（当历史数据不足时使用）

    根据当前统计数据，估算从视频发布到现在每一天的热度曲线
    如果提供了activity_by_day（评论/弹幕每日活动量），则基于实际活动数据计算

    Args:
        stats: dict 当前统计数据
        days_old: int 视频发布天数
        peak_day: int 预估峰值在第几天，默认根据视频类型自动估算
        decay_rate: float 衰减率
        activity_by_day: dict {day_offset: count} 基于实际评论/弹幕发布时间

    Returns:
        dict: {
            'peak_value': 峰值热度,
            'peak_day': 峰值发生在第几天,
            'peak_date': 峰值日期描述,
            'current_heat': 当前热度,
            'trend': [{'date': str, 'heat': float, 'day': int}, ...],
            'days_total': 总天数
        }
    """
    base_heat = calc_interaction_base(stats)

    # 计算最大活动量用于归一化
    max_activity = 1
    if activity_by_day:
        max_activity = max(activity_by_day.values()) if activity_by_day else 1
        if max_activity == 0:
            max_activity = 1
        # 如果有实际活动数据，用实际数据确定峰值日
        max_act_val = max_activity
        for d, c in activity_by_day.items():
            if c == max_act_val:
                peak_day = d
                break

    if peak_day is None:
        # 根据视频热度规模自动估算峰值日
        view_count = stats.get('view_count', 0)
        if view_count > 1000000:  # 百万播放以上
            peak_day = 3
        elif view_count > 100000:  # 十万以上
            peak_day = 5
        else:
            peak_day = 7

    # 计算峰值热度
    # 峰值时：基础分 × 趋势加成(1.5) × 衰减(峰值日)
    peak_heat = base_heat * 1.5 * calc_decay(peak_day)

    # 构建每日热度曲线
    trend = []
    for day in range(1, days_old + 1):
        # 获取当天的活动量因子（基于实际评论/弹幕发布时间）
        activity_factor = 1.0
        if activity_by_day and day in activity_by_day:
            # 活动因子范围: 0.5 ~ 1.5，基于归一化的活动量
            activity_factor = 0.5 + 1.0 * (activity_by_day[day] / max_activity)
            # 限制在合理范围
            activity_factor = max(0.3, min(1.5, activity_factor))

        # 获取当天基础互动分（如果有每日统计数据）
        day_base = base_heat

        if day <= peak_day:
            # 上升期：从0增长到峰值
            progress = day / peak_day if peak_day > 0 else 1
            # 使用加速增长曲线（前期慢，后期快）
            # 热度 = 峰值热度 × 进度因子 × 活动因子
            heat = peak_heat * (progress ** 0.7) * activity_factor
        else:
            # 衰减期：从峰值指数衰减
            # 热度 = 峰值热度 × 衰减系数 × 活动因子
            heat = peak_heat * math.exp(-decay_rate * (day - peak_day)) * activity_factor

        trend.append({
            'date': f'Day{day}',
            'heat': round(heat, 2),
            'day': day
        })

    peak = max(trend, key=lambda x: x['heat'])
    current = trend[-1] if trend else {'heat': 0, 'day': 1}

    return {
        'peak_value': round(peak['heat'], 2),
        'peak_day': peak['day'],
        'peak_date': peak['date'],
        'current_heat': round(current['heat'], 2),
        'trend': trend,
        'days_total': days_old,
        'estimated': True
    }


def _get_total_interaction(stat):
    """计算总互动量"""
    return (
        stat.get('like_count', 0) +
        stat.get('coin_count', 0) * 2 +
        stat.get('collect_count', 0) * 2 +
        stat.get('share_count', 0) * 5 +
        stat.get('comment_count', 0) * 2 +
        stat.get('danmaku_count', 0)
    )


# 兼容旧接口
def calc_heat_score(stats, sentiment_score=0.5, days_old=7, alpha=0.6, beta=0.4, lamb=0.1):
    """
    旧版热度计算（保留兼容）

    Returns:
        float 热度分数
    """
    base = calc_interaction_base(stats)
    decay = calc_decay(days_old)
    return round(base * decay, 4)


def calc_sentiment_ratio(pos_count, neg_count, neu_count):
    """
    计算情感比率

    Returns:
        float 情感极性分数 (0-1)，0.5为中性
    """
    total = pos_count + neg_count + neu_count
    if total == 0:
        return 0.5

    # 正面权重为正，负面权重为负
    score = (pos_count - neg_count) / total + 0.5
    return max(0, min(1, score))


def detect_hotspots(interaction_stream, threshold_percentile=75, k=3):
    """
    热点检测算法

    识别时间段内互动量超过阈值的热点

    Args:
        interaction_stream: list of dict [(timestamp, count), ...]
        threshold_percentile: int 百分位阈值
        k: int 连续k个时间点超过阈值才认定为热点

    Returns:
        list of hotspot segments [(start_idx, end_idx), ...]
    """
    if not interaction_stream:
        return []

    counts = [item['count'] for item in interaction_stream]

    # 计算阈值
    import numpy as np
    threshold = np.percentile(counts, threshold_percentile)

    # 找出连续超过阈值的段
    hotspots = []
    current = []

    for i, count in enumerate(counts):
        if count >= threshold:
            current.append(i)
        else:
            if len(current) >= k:
                hotspots.append((current[0], current[-1]))
            current = []

    # 处理末尾
    if len(current) >= k:
        hotspots.append((current[0], current[-1]))

    return hotspots


def get_top_keywords(texts, topK=5):
    """
    从文本列表提取Top关键词

    Args:
        texts: list of str
        topK: int 返回数量

    Returns:
        list of str
    """
    if not texts:
        return []

    try:
        import jieba.analyse
        text = ' '.join(texts[:5000])  # 限制数量
        return jieba.analyse.extract_tags(text, topK=topK, withWeight=False)
    except Exception as e:
        print(f"关键词提取错误: {e}")
        return []
