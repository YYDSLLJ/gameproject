# -*- coding: utf-8 -*-
"""
API 路由
"""

from flask import Blueprint, jsonify, request, session, current_app
from functools import wraps
from sqlalchemy import text, desc
from ..models import db, Video, VideoStats, Comment, Danmaku, PlatformCookie, ProxyIP
from ..spiders import parse_video_url, SpiderRegistry
from ..spiders.bilibili import BilibiliSpider
from ..visualization import get_platform_viz
from ..analysis.heat import calc_heat_score, calc_sentiment_ratio
from ..analysis.sentiment import classify_sentiment

api_bp = Blueprint('api', __name__, url_prefix='/api')


def login_required(f):
    """登录Required装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user_id():
    """获取当前登录用户ID（未登录返回None）"""
    return session.get('user_id')


def is_admin():
    """是否管理员"""
    return session.get('role') == 'admin'


def get_user_cookie():
    """获取当前用户的Cookie（随机从池中选择）"""
    from ..models import PlatformCookie
    user_id = get_current_user_id()
    if user_id:
        # 从用户的Cookie池中随机选择一个
        cookies = PlatformCookie.query.filter_by(
            user_id=user_id,
            platform='bilibili'
        ).all()
        if cookies:
            import random
            selected = random.choice(cookies)
            return selected.cookie
    return current_app.config.get('BILIBILI_COOKIE', '')


def get_random_proxy():
    """随机获取一个可用代理"""
    user_id = get_current_user_id()
    if user_id:
        proxies = ProxyIP.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        if proxies:
            import random
            selected = random.choice(proxies)
            return selected.proxy_url
    return None


@api_bp.route('/videos', methods=['GET'])
def get_videos():
    """获取视频列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    platform = request.args.get('platform', None)
    order_by = request.args.get('order_by', 'heat_score')

    user_id = get_current_user_id()

    # 管理员看所有视频，普通用户只看自己添加的+无主的
    if is_admin():
        query = Video.query
    elif user_id:
        query = Video.query.filter(
            (Video.user_id == user_id) | (Video.user_id == None)
        )
    else:
        # 未登录用户只能看无主的（系统爬的）
        query = Video.query.filter(Video.user_id == None)

    if platform:
        query = query.filter_by(platform=platform)

    # 按最新统计排序
    if order_by == 'heat_score':
        query = query.join(Video.stats).order_by(VideoStats.heat_score.desc())
    else:
        query = query.order_by(Video.created_at.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    videos = []
    for v in pagination.items:
        latest_stat = v.stats.first()
        videos.append({
            'id': v.id,
            'platform': v.platform,
            'title': v.title,
            'author': v.author,
            'cover': v.cover,
            'url': v.url,
            'heat_score': latest_stat.heat_score if latest_stat else 0,
            'is_mine': v.user_id == user_id if user_id else False,
            'is_admin': is_admin(),
        })

    return jsonify({
        'videos': videos,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


@api_bp.route('/videos/<int:video_id>', methods=['GET'])
def get_video(video_id):
    """获取单个视频详情"""
    video = Video.query.get_or_404(video_id)

    # 权限检查：视频所有者或管理员可以操作，普通用户只能查看
    user_id = get_current_user_id()
    if video.user_id and video.user_id != user_id and not is_admin():
        # 非所有者可以查看，但某些操作可能受限（取决于前端隐藏操作按钮）
        pass  # 允许查看，只是不能操作

    latest_stat = video.stats.first()

    current_user_id = get_current_user_id()
    video_is_mine = video.user_id == current_user_id if current_user_id else False
    video_is_admin = is_admin()

    return jsonify({
        'id': video.id,
        'platform': video.platform,
        'platform_id': video.platform_id,
        'title': video.title,
        'author': video.author,
        'author_face': video.author_face,
        'cover': video.cover,
        'url': video.url,
        'duration_ms': video.duration_ms,
        'extra_data': video.extra_data,
        'stats': {
            'view_count': latest_stat.view_count if latest_stat else 0,
            'like_count': latest_stat.like_count if latest_stat else 0,
            'coin_count': latest_stat.coin_count if latest_stat else 0,
            'collect_count': latest_stat.collect_count if latest_stat else 0,
            'share_count': latest_stat.share_count if latest_stat else 0,
            'comment_count': latest_stat.comment_count if latest_stat else 0,
            'danmaku_count': latest_stat.danmaku_count if latest_stat else 0,
            'heat_score': latest_stat.heat_score if latest_stat else 0,
        } if latest_stat else None,
        'is_mine': video_is_mine,
        'is_admin': video_is_admin,
    })


@api_bp.route('/videos/<int:video_id>/refresh', methods=['POST'])
def refresh_video(video_id):
    """刷新视频数据（从源头重新爬取）

    Query params:
        force_crawl: 1 表示强制重新爬取评论和弹幕（用于修复之前爬取失败的数据）
    """
    from datetime import date

    video = Video.query.get_or_404(video_id)

    # 权限检查：视频所有者或管理员可以刷新
    user_id = get_current_user_id()
    if video.user_id and video.user_id != user_id and not is_admin():
        return jsonify({'error': '无权限操作'}), 403

    if video.platform != 'bilibili':
        return jsonify({'error': '暂只支持B站视频刷新'}), 400

    # 是否强制爬取评论弹幕
    force_crawl = request.args.get('force_crawl', '0') == '1'

    # 使用随机Cookie和代理
    cookie = get_user_cookie()
    proxy = get_random_proxy()
    spider = BilibiliSpider(cookie=cookie, proxy=proxy)

    try:
        # 1. 更新视频基本信息
        info = spider.get_video_info(video.platform_id)
        video.title = info['title']
        video.author = info['author']
        video.cover = info['cover']
        video.author_face = info['author_face']
        db.session.commit()

        # 2. 获取最新统计
        stats = spider.get_video_stats(video.platform_id)

        # 3. 更新或创建今日统计
        today = date.today()
        latest_stat = video.stats.filter_by(stat_date=today).first()

        if latest_stat:
            # 更新现有记录
            latest_stat.view_count = stats['view_count']
            latest_stat.like_count = stats['like_count']
            latest_stat.coin_count = stats['coin_count']
            latest_stat.collect_count = stats['collect_count']
            latest_stat.share_count = stats['share_count']
            latest_stat.comment_count = stats['comment_count']
            latest_stat.danmaku_count = stats['danmaku_count']
        else:
            # 创建新记录
            latest_stat = VideoStats(
                video_id=video.id,
                stat_date=today,
                **stats
            )
            db.session.add(latest_stat)

        # 4. 重新计算热度
        sentiment_data = get_sentiment_data(video.id)
        sentiment_score = calc_sentiment_ratio(
            sentiment_data['pos'],
            sentiment_data['neg'],
            sentiment_data['neu']
        )

        days_old = (date.today() - video.created_at.date()).days if video.created_at else 0
        heat_score = calc_heat_score({
            'view_count': stats['view_count'],
            'like_count': stats['like_count'],
            'coin_count': stats['coin_count'],
            'collect_count': stats['collect_count'],
            'share_count': stats['share_count'],
            'comment_count': stats['comment_count'],
        }, sentiment_score=sentiment_score, days_old=days_old)

        latest_stat.heat_score = heat_score
        latest_stat.sentiment_pos = sentiment_data['pos']
        latest_stat.sentiment_neg = sentiment_data['neg']
        latest_stat.sentiment_neu = sentiment_data['neu']

        # 5. 爬取评论和弹幕（动态上限：基于视频统计数据）
        from app.models import Comment, Danmaku

        # 根据视频统计数据动态确定爬取上限
        actual_comment_count = stats.get('comment_count', 0)
        actual_danmaku_count = stats.get('danmaku_count', 0)

        # 设置合理的爬取上限（留有余量）
        max_comments = min(actual_comment_count + 100, 3000)  # 实际评论数+100，上限3000
        max_danmaku = min(actual_danmaku_count + 200, 8000)  # 实际弹幕数+200，上限8000

        crawl_result = {}
        if force_crawl:
            # 强制爬取：先删除旧数据，再重新爬取
            Comment.query.filter_by(video_id=video.id).delete()
            Danmaku.query.filter_by(video_id=video.id).delete()
            try:
                crawl_data = spider.crawl_comments_and_danmaku(
                    video.platform_id,
                    max_comments=max_comments,
                    max_danmaku=max_danmaku
                )
                _save_comments_and_danmaku(video.id, crawl_data)
                crawl_result['comments'] = len(crawl_data.get('comments', []))
                crawl_result['danmaku'] = len(crawl_data.get('danmaku', []))
            except Exception as e:
                crawl_result['error'] = str(e)
        else:
            # 普通刷新：只爬取还没有的数据
            existing_comments = Comment.query.filter_by(video_id=video.id).count()
            existing_danmaku = Danmaku.query.filter_by(video_id=video.id).count()

            try:
                crawl_data = spider.crawl_comments_and_danmaku(
                    video.platform_id,
                    max_comments=max_comments,
                    max_danmaku=max_danmaku
                )

                # 增量保存评论：检查是否已存在，避免重复
                saved_comments = 0
                for c in crawl_data.get('comments', []):
                    # 检查评论是否已存在（基于 content 和 user_name 粗略判断）
                    existing = Comment.query.filter_by(
                        video_id=video.id,
                        content=c.get('content', ''),
                        user_name=c.get('user_name', '')
                    ).first()
                    if existing:
                        continue

                    from datetime import datetime
                    created_at = None
                    if c.get('created_at'):
                        try:
                            created_at = datetime.fromtimestamp(c['created_at'])
                        except:
                            pass
                    comment = Comment(
                        video_id=video.id,
                        content=c.get('content', ''),
                        user_name=c.get('user_name', ''),
                        user_level=c.get('user_level', 0),
                        gender=c.get('gender', ''),
                        region=c.get('region', ''),
                        sentiment=classify_sentiment(c.get('content', '')),
                        created_at=created_at,
                    )
                    db.session.add(comment)
                    saved_comments += 1
                crawl_result['comments'] = saved_comments

                # 增量保存弹幕：检查 (content, progress_ms) 是否已存在
                seen = set()
                saved_danmaku = 0
                for d in crawl_data.get('danmaku', []):
                    content = d.get('content', '')
                    progress_ms = d.get('progress_ms', 0)
                    key = (content, progress_ms)
                    if key in seen:
                        continue
                    seen.add(key)

                    # 检查是否已存在
                    exists = Danmaku.query.filter_by(
                        video_id=video.id,
                        content=content,
                        progress_ms=progress_ms
                    ).first()
                    if exists:
                        continue

                    from datetime import datetime
                    created_at = None
                    if d.get('created_at'):
                        try:
                            created_at = datetime.fromtimestamp(d['created_at'])
                        except:
                            pass
                    danmaku = Danmaku(
                        video_id=video.id,
                        content=content,
                        progress_ms=progress_ms,
                        sentiment=classify_sentiment(content),
                        created_at=created_at,
                    )
                    db.session.add(danmaku)
                    saved_danmaku += 1
                crawl_result['danmaku'] = saved_danmaku
            except Exception as e:
                crawl_result['error'] = str(e)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': '数据刷新成功',
            'stats': {
                'view_count': stats['view_count'],
                'like_count': stats['like_count'],
                'coin_count': stats['coin_count'],
                'collect_count': stats['collect_count'],
                'share_count': stats['share_count'],
                'heat_score': heat_score,
            },
            'crawled': crawl_result
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刷新失败: {str(e)}'}), 500


def get_sentiment_data(video_id):
    """获取视频的情感统计数据"""
    comments = Comment.query.filter_by(video_id=video_id).all()
    pos = sum(1 for c in comments if c.sentiment == 1)
    neg = sum(1 for c in comments if c.sentiment == -1)
    neu = sum(1 for c in comments if c.sentiment == 0)
    return {'pos': pos, 'neg': neg, 'neu': neu}


@api_bp.route('/analyze', methods=['POST'])
def analyze_url():
    """
    用户提交链接分析

    Body: { "url": "https://www.bilibili.com/video/BVxxx" }
    """
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': '缺少url参数'}), 400

    # 获取当前用户ID（可选）
    user_id = get_current_user_id()

    # 优先使用用户自己的Cookie
    cookie = get_user_cookie()

    try:
        platform, platform_id = parse_video_url(url)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    # 检查数据库是否已有
    video = Video.query.filter_by(platform=platform, platform_id=platform_id).first()

    if not video:
        # 调用爬虫获取
        spider_cls = SpiderRegistry.get_spider(platform)
        if not spider_cls:
            return jsonify({'error': f'不支持的平台: {platform}'}), 400

        proxy = get_random_proxy()
        spider = spider_cls(cookie=cookie, proxy=proxy)

        try:
            info = spider.get_video_info(platform_id)
            stats = spider.get_video_stats(platform_id)

            # 创建视频记录（关联用户）
            video = Video(**info, user_id=user_id)
            db.session.add(video)
            db.session.flush()  # 获取id

            # 创建初始统计
            from datetime import date
            stat = VideoStats(
                video_id=video.id,
                stat_date=date.today(),
                **stats
            )
            db.session.add(stat)

            # 爬取评论和弹幕（动态上限）
            if platform == 'bilibili':
                try:
                    actual_comment = stats.get('comment_count', 0)
                    actual_danmaku = stats.get('danmaku_count', 0)
                    max_comments = min(actual_comment + 100, 3000)
                    max_danmaku = min(actual_danmaku + 200, 8000)
                    crawl_data = spider.crawl_comments_and_danmaku(
                        platform_id,
                        max_comments=max_comments,
                        max_danmaku=max_danmaku
                    )
                    _save_comments_and_danmaku(video.id, crawl_data)
                except Exception as e:
                    print(f"评论/弹幕爬取失败: {e}")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'爬取失败: {str(e)}'}), 500

    return jsonify({
        'id': video.id,
        'platform': video.platform,
        'title': video.title,
        'author': video.author,
        'cover': video.cover,
        'url': video.url,
    })


def _save_comments_and_danmaku(video_id, crawl_data):
    """保存评论和弹幕到数据库"""
    from datetime import datetime

    # 保存评论
    for c in crawl_data.get('comments', []):
        created_at = None
        if c.get('created_at'):
            try:
                created_at = datetime.fromtimestamp(c['created_at'])
            except:
                pass

        comment = Comment(
            video_id=video_id,
            content=c.get('content', ''),
            user_name=c.get('user_name', ''),
            user_level=c.get('user_level', 0),
            gender=c.get('gender', ''),
            region=c.get('region', ''),
            sentiment=classify_sentiment(c.get('content', '')),
            created_at=created_at,
        )
        db.session.add(comment)

    # 保存弹幕
    for d in crawl_data.get('danmaku', []):
        created_at = None
        if d.get('created_at'):
            try:
                created_at = datetime.fromtimestamp(d['created_at'])
            except:
                pass

        danmaku = Danmaku(
            video_id=video_id,
            content=d.get('content', ''),
            progress_ms=d.get('progress_ms', 0),
            sentiment=classify_sentiment(d.get('content', '')),
            created_at=created_at,
        )
        db.session.add(danmaku)


@api_bp.route('/videos/<int:video_id>/summary', methods=['GET'])
def api_video_summary(video_id):
    """获取视频可视化摘要数据"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        summary = viz.get_summary(video, conn)

    return jsonify(summary)


@api_bp.route('/videos/<int:video_id>/region', methods=['GET'])
def api_video_region(video_id):
    """获取省份分布"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        region = viz.get_region_map(video, conn)

    return jsonify(region)


@api_bp.route('/videos/<int:video_id>/sentiment', methods=['GET'])
def api_video_sentiment(video_id):
    """获取情感分析"""
    video = Video.query.get_or_404(video_id)
    region = request.args.get('region', None)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        sentiment = viz.get_sentiment(video, conn, region=region)

    return jsonify(sentiment)


@api_bp.route('/videos/<int:video_id>/sentiment-examples', methods=['GET'])
def api_video_sentiment_examples(video_id):
    """获取情感分析示例"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        examples = viz.get_sentiment_examples(video, conn)

    return jsonify(examples)


@api_bp.route('/videos/<int:video_id>/levels', methods=['GET'])
def api_video_levels(video_id):
    """获取用户等级分布"""
    video = Video.query.get_or_404(video_id)
    region = request.args.get('region', None)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        levels = viz.get_level_pie(video, conn, region=region)

    return jsonify(levels)


@api_bp.route('/videos/<int:video_id>/gender', methods=['GET'])
def api_video_gender(video_id):
    """获取性别比例"""
    video = Video.query.get_or_404(video_id)
    region = request.args.get('region', None)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        gender = viz.get_gender_pie(video, conn, region=region)

    return jsonify(gender)


@api_bp.route('/videos/<int:video_id>/timeline', methods=['GET'])
def api_video_timeline(video_id):
    """获取时间线数据"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        timeline = viz.get_realtime_series(video, conn)

    return jsonify(timeline)


@api_bp.route('/videos/<int:video_id>/invideo', methods=['GET'])
def api_video_invideo(video_id):
    """获取视频内弹幕分布"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        invideo = viz.get_invideo_series(video, conn)

    return jsonify(invideo)


@api_bp.route('/videos/<int:video_id>/segments', methods=['GET'])
def api_video_segments(video_id):
    """获取弹幕分段分析"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        segments = viz.get_danmaku_segments(video, conn)

    return jsonify(segments)


@api_bp.route('/videos/<int:video_id>/heat-trend', methods=['GET'])
def api_video_heat_trend(video_id):
    """获取热度趋势"""
    video = Video.query.get_or_404(video_id)

    viz = get_platform_viz(video.platform)

    with db.session.connection() as conn:
        trend = viz.get_heat_trend(video, conn)

    return jsonify(trend)


@api_bp.route('/videos/<int:video_id>/comments', methods=['GET'])
def api_video_comments(video_id):
    """获取评论列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)
    region = request.args.get('region', None)

    video = Video.query.get_or_404(video_id)

    query = Comment.query.filter_by(video_id=video_id)

    # 按地区筛选
    if region:
        # 处理省份名称匹配
        from ..visualization.bilibili import BilibiliVisualization
        viz = BilibiliVisualization()
        prov_map = viz.PROV_MAP
        # 反向映射：全称 -> 简称
        reverse_map = {v: k for k, v in prov_map.items()}
        # 用户输入可能是全称或简称
        matched_key = region
        for k, v in prov_map.items():
            if region == k or region == v:
                matched_key = k
                break
        query = query.filter(Comment.region.like(f'%{matched_key}%'))

    pagination = query.order_by(Comment.created_at.desc())\
        .paginate(page=page, per_page=page_size, error_out=False)

    comments = [{
        'id': c.id,
        'content': c.content,
        'sentiment': c.sentiment,
        'user_name': c.user_name,
        'user_level': c.user_level,
        'gender': c.gender,
        'region': c.region,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    } for c in pagination.items]

    return jsonify({
        'comments': comments,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


@api_bp.route('/videos/<int:video_id>/danmaku', methods=['GET'])
def api_video_danmaku(video_id):
    """获取弹幕列表"""
    video = Video.query.get_or_404(video_id)

    danmaku_list = Danmaku.query.filter_by(video_id=video_id)\
        .order_by(Danmaku.progress_ms.asc()).all()

    return jsonify([{
        'id': d.id,
        'content': d.content,
        'progress_ms': d.progress_ms,
        'sentiment': d.sentiment,
    } for d in danmaku_list])


@api_bp.route('/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    """删除视频"""
    video = Video.query.get_or_404(video_id)

    # 权限检查：视频所有者或管理员可以删除
    user_id = get_current_user_id()
    if video.user_id and video.user_id != user_id and not is_admin():
        return jsonify({'error': '无权限删除'}), 403

    try:
        # 删除关联的评论、弹幕、统计
        Comment.query.filter_by(video_id=video.id).delete()
        Danmaku.query.filter_by(video_id=video.id).delete()
        VideoStats.query.filter_by(video_id=video.id).delete()
        db.session.delete(video)
        db.session.commit()
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除失败: {str(e)}'}), 500


@api_bp.route('/my/videos', methods=['GET'])
def get_my_videos():
    """获取当前用户添加的视频"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'videos': [], 'total': 0})

    videos = Video.query.filter_by(user_id=user_id).order_by(Video.created_at.desc()).all()
    return jsonify({
        'videos': [{
            'id': v.id,
            'platform': v.platform,
            'title': v.title,
            'author': v.author,
            'cover': v.cover,
            'url': v.url,
            'created_at': v.created_at.isoformat() if v.created_at else None,
        } for v in videos],
        'total': len(videos)
    })
