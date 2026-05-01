# -*- coding: utf-8 -*-
"""
页面路由
"""

from flask import Blueprint, render_template, redirect, url_for, session
from sqlalchemy import desc
from ..models import Video, VideoStats

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """首页 - 热度排行榜"""
    return render_template('index.html')


@web_bp.route('/video/<int:video_id>')
def video_detail(video_id):
    """视频详情页 - Vue 3版本"""
    video = Video.query.get_or_404(video_id)
    return render_template('video_vue3.html', video=video)


@web_bp.route('/analyze')
def analyze():
    """分析页 - 用户输入链接"""
    return render_template('analyze.html')


@web_bp.route('/admin')
def admin():
    """管理页"""
    return render_template('admin.html')


@web_bp.route('/login')
def login():
    """登录页"""
    # 如果已登录，根据角色跳转
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect('/admin')
        return redirect('/')
    return render_template('auth.html')
