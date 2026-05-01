# -*- coding: utf-8 -*-
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin / user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    videos = db.relationship('Video', backref='owner', lazy='dynamic')
    cookies = db.relationship('PlatformCookie', backref='owner', lazy='dynamic')
    proxies = db.relationship('ProxyIP', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'


class PlatformCookie(db.Model):
    __tablename__ = 'platform_cookies'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform = db.Column(db.String(20), nullable=False)  # bilibili/douyin
    name = db.Column(db.String(50), nullable=False)      # 命名，如bilibili-01
    cookie = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ProxyIP(db.Model):
    """代理IP池"""
    __tablename__ = 'proxy_ips'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(50), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(10), default='http')  # http/https
    username = db.Column(db.String(50), nullable=True)   # 代理用户名（可选）
    password = db.Column(db.String(50), nullable=True)   # 代理密码（可选）
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    success_count = db.Column(db.Integer, default=0)   # 成功次数
    fail_count = db.Column(db.Integer, default=0)       # 失败次数
    last_used = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def proxy_url(self):
        """返回代理URL，自动包含认证信息"""
        if self.username and self.password:
            return f'{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}'
        return f'{self.protocol}://{self.ip}:{self.port}'


class Video(db.Model):
    __tablename__ = 'videos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform = db.Column(db.String(20), nullable=False)  # bilibili/douyin
    platform_id = db.Column(db.String(50), nullable=False)  # bvid or douyin_id
    title = db.Column(db.String(255))
    author = db.Column(db.String(100))
    author_face = db.Column(db.String(255))
    cover = db.Column(db.String(255))
    url = db.Column(db.String(255))
    duration_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # 视频所有者

    # 平台特定数据存为 JSON
    extra_data = db.Column(db.JSON)

    stats = db.relationship('VideoStats', backref='video', lazy='dynamic', order_by='desc(VideoStats.stat_date)')
    comments = db.relationship('Comment', backref='video', lazy='dynamic')
    danmaku = db.relationship('Danmaku', backref='video', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('platform', 'platform_id', name='uq_platform_platform_id'),
    )

    @property
    def pubdate(self):
        """获取视频发布时间的Unix时间戳"""
        if self.extra_data and 'pubdate' in self.extra_data:
            return self.extra_data['pubdate']
        return None

    @property
    def pubdate_days_ago(self):
        """获取视频发布至今的天数"""
        import time
        if self.pubdate:
            now = int(time.time())
            seconds_ago = now - self.pubdate
            return max(1, seconds_ago // 86400)  # 至少1天
        # 没有pubdate用created_at
        if self.created_at:
            from datetime import datetime
            delta = datetime.utcnow() - self.created_at
            return max(1, delta.days)
        return 1


class VideoStats(db.Model):
    """每周热度快照"""
    __tablename__ = 'video_stats'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    stat_date = db.Column(db.Date, nullable=False)

    # 通用字段
    view_count = db.Column(db.BigInteger, default=0)
    like_count = db.Column(db.BigInteger, default=0)
    coin_count = db.Column(db.BigInteger, default=0)
    collect_count = db.Column(db.BigInteger, default=0)
    share_count = db.Column(db.BigInteger, default=0)
    comment_count = db.Column(db.BigInteger, default=0)
    danmaku_count = db.Column(db.BigInteger, default=0)

    # 计算后的热度值
    heat_score = db.Column(db.Float, default=0.0)

    # 情感统计
    sentiment_pos = db.Column(db.Integer, default=0)
    sentiment_neg = db.Column(db.Integer, default=0)
    sentiment_neu = db.Column(db.Integer, default=0)

    # 平台特定字段
    extra_stats = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('video_id', 'stat_date', name='uq_video_stat_date'),
    )


class Comment(db.Model):
    """评论表"""
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    content = db.Column(db.Text)
    sentiment = db.Column(db.Integer, default=0)  # -1负面 0中性 1正面

    # 用户信息
    user_name = db.Column(db.String(100))
    user_level = db.Column(db.Integer, default=0)
    gender = db.Column(db.String(10))  # 男/女/
    region = db.Column(db.String(50))

    created_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('idx_video_sentiment', 'video_id', 'sentiment'),
        db.Index('idx_video_region', 'video_id', 'region'),
    )


class Danmaku(db.Model):
    """弹幕表（仅B站）"""
    __tablename__ = 'danmaku'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    video_id = db.Column(db.Integer, db.ForeignKey('videos.id'), nullable=False)
    content = db.Column(db.String(255))
    progress_ms = db.Column(db.Integer)  # 视频内时间（毫秒）
    sentiment = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('idx_video_progress', 'video_id', 'progress_ms'),
    )
