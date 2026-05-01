# -*- coding: utf-8 -*-
"""
Flask 应用工厂
"""

from flask import Flask
from flask_apscheduler import APScheduler

from .config import Config
from .models import db, User
from .routes.api import api_bp
from .routes.web import web_bp
from .routes.admin import admin_bp
from .routes.auth import auth_bp


scheduler = APScheduler()


def create_app(config_class=Config):
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)

    # 初始化扩展
    db.init_app(app)

    # 注册蓝图
    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)

    # 初始化调度器
    scheduler.init_app(app)

    # 添加定时任务
    @scheduler.task('cron', id='bilibili_hot', day_of_week='mon', hour=0, minute=0)
    def crawl_bilibili_hot():
        """每周一爬取B站热门"""
        with app.app_context():
            from .spiders.bilibili import BilibiliSpider
            from datetime import date
            from .models import Video, VideoStats

            spider = BilibiliSpider()
            # TODO: 实现热门榜单爬取
            pass

    @scheduler.task('cron', id='calc_heat', day_of_week='tue', hour=1, minute=0)
    def calc_heat():
        """每周二计算热度"""
        with app.app_context():
            from .analysis.heat import calc_heat_score, calc_sentiment_ratio
            from sqlalchemy import desc

            videos = Video.query.all()
            for video in videos:
                latest_stat = video.stats.order_by(desc(VideoStats.stat_date)).first()
                if not latest_stat:
                    continue

                from .models import Comment
                comments = Comment.query.filter_by(video_id=video.id).all()
                pos = sum(1 for c in comments if c.sentiment == 1)
                neg = sum(1 for c in comments if c.sentiment == -1)
                neu = sum(1 for c in comments if c.sentiment == 0)

                sentiment_score = calc_sentiment_ratio(pos, neg, neu)

                from datetime import date
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

    scheduler.start()

    # 创建数据库表
    with app.app_context():
        db.create_all()
        init_admin_users()

    return app


def init_admin_users():
    """初始化管理员账号"""
    admins = [
        {'username': 'admin', 'email': 'admin@example.com', 'password': '12345678'},
        {'username': 'lyp', 'email': 'lyp@example.com', 'password': '12345678'},
    ]

    for data in admins:
        existing = User.query.filter_by(username=data['username']).first()
        if not existing:
            user = User(
                username=data['username'],
                email=data['email'],
                role='admin'
            )
            user.set_password(data['password'])
            db.session.add(user)
            print(f"Created admin user: {data['username']}")

    db.session.commit()
