# -*- coding: utf-8 -*-
"""
情感分析模块
"""

from snownlp import SnowNLP


def classify_sentiment(text):
    """
    情感分类

    Args:
        text: str 文本

    Returns:
        int -1(负面) 0(中性) 1(正面)
    """
    if not text or not text.strip():
        return 0

    try:
        score = SnowNLP(text).sentiments
        if score > 0.6:
            return 1
        elif score < 0.4:
            return -1
        return 0
    except Exception:
        return 0


def batch_classify(texts):
    """
    批量情感分类

    Args:
        texts: list of str

    Returns:
        list of int
    """
    return [classify_sentiment(t) for t in texts]


def get_sentiment_stats(texts):
    """
    获取情感统计

    Args:
        texts: list of str

    Returns:
        dict {'positive': int, 'neutral': int, 'negative': int}
    """
    from collections import Counter
    sentiments = batch_classify(texts)
    counter = Counter(sentiments)
    return {
        'positive': counter.get(1, 0),
        'neutral': counter.get(0, 0),
        'negative': counter.get(-1, 0),
    }
