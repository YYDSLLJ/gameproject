# -*- coding: utf-8 -*-
"""
APScheduler 定时任务配置

运行方式：
    python scheduler.py
"""

from app import create_app
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import date

app = create_app()
scheduler = BlockingScheduler()


@scheduler.scheduled_task('cron', id='bilibili_hot', day_of_week='mon', hour=0, minute=0)
def crawl_bilibili_hot():
    """每周一爬取B站热门"""
    with app.app_context():
        print("开始爬取B站热门...")
        # TODO: 实现热门榜单爬取


@scheduler.scheduled_task('cron', id='douyin_hot', day_of_week='mon', hour=0, minute=30)
def crawl_douyin_hot():
    """每周一爬取抖音热门（预留）"""
    with app.app_context():
        print("抖音爬虫预留位置...")
        pass


@scheduler.scheduled_task('cron', id='calc_heat', day_of_week='tue', hour=1, minute=0)
def calc_heat():
    """每周二计算热度"""
    with app.app_context():
        print("计算热度分数...")
        from app.models import Video, VideoStats, Comment, db
        from app.analysis.heat import calc_heat_score, calc_sentiment_ratio
        from sqlalchemy import desc

        videos = Video.query.all()
        for video in videos:
            latest_stat = video.stats.order_by(desc(VideoStats.stat_date)).first()
            if not latest_stat:
                continue

            comments = Comment.query.filter_by(video_id=video.id).all()
            pos = sum(1 for c in comments if c.sentiment == 1)
            neg = sum(1 for c in comments if c.sentiment == -1)
            neu = sum(1 for c in comments if c.sentiment == 0)

            sentiment_score = calc_sentiment_ratio(pos, neg, neu)
            days_old = (date.today() - video.created_at.date()).days if video.created_at else 0

            heat = calc_heat_score(
                {
                    'view_count': latest_stat.view_count,
                    'like_count': latest_stat.like_count,
                    'coin_count': latest_stat.coin_count,
                    'collect_count': latest_stat.collect_count,
                    'share_count': latest_stat.share_count,
                    'comment_count': latest_stat.comment_count,
                },
                sentiment_score=sentiment_score,
                days_old=days_old
            )

            latest_stat.heat_score = heat
            db.session.commit()

        print("热度计算完成")


if __name__ == '__main__':
    print("启动定时任务调度器...")
    scheduler.start()
