# -*- coding: utf-8 -*-
"""
管理/爬虫触发路由
"""

from flask import Blueprint, jsonify, request, current_app, session
from functools import wraps
from datetime import date, datetime, timedelta
from ..models import db, Video, VideoStats, Comment, Danmaku, User, PlatformCookie, ProxyIP
from ..spiders.bilibili import BilibiliSpider
from ..analysis.sentiment import classify_sentiment
from ..analysis.heat import calc_heat_score, calc_sentiment_ratio

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def login_required(f):
    """登录Required装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员Required装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/spider/bilibili/hot', methods=['POST'])
def crawl_bilibili_hot():
    """
    爬取B站热门视频

    实际项目中应该爬取热门榜单，这里简化处理
    """
    spider = BilibiliSpider(cookie=current_app.config.get('BILIBILI_COOKIE', ''))

    # TODO: 实现热门榜单爬取
    # 这里用一个示例BV号演示
    test_bvids = ['BV1xx411c7XZ', 'BV1CJ411m7SG']

    results = []
    for bvid in test_bvids:
        try:
            info = spider.get_video_info(bvid)
            stats = spider.get_video_stats(bvid)

            # 检查是否已存在
            video = Video.query.filter_by(platform='bilibili', platform_id=bvid).first()
            if video:
                video.title = info['title']
                video.author = info['author']
                video.cover = info['cover']
            else:
                video = Video(**info)
                db.session.add(video)
                db.session.flush()

                # 创建统计快照
                stat = VideoStats(
                    video_id=video.id,
                    stat_date=date.today(),
                    **stats
                )
                db.session.add(stat)

            db.session.commit()
            results.append({'bvid': bvid, 'status': 'success'})

        except Exception as e:
            db.session.rollback()
            results.append({'bvid': bvid, 'status': 'error', 'message': str(e)})

    return jsonify({'results': results})


@admin_bp.route('/spider/video/<int:video_id>/full', methods=['POST'])
def crawl_video_full(video_id):
    """
    爬取单个视频完整数据（评论+弹幕）
    """
    video = Video.query.get_or_404(video_id)

    if video.platform != 'bilibili':
        return jsonify({'error': '暂只支持B站'}), 400

    spider = BilibiliSpider(cookie=current_app.config.get('BILIBILI_COOKIE', ''))
    results = {'comments': 0, 'danmaku': 0, 'errors': []}

    # 爬取评论
    try:
        for page in range(1, 100):  # 最多100页
            comments = spider.get_comments(video.platform_id, page=page, page_size=20)
            if not comments:
                break

            for c in comments:
                existing = Comment.query.filter_by(
                    video_id=video_id,
                    content=c['content']
                ).first()
                if existing:
                    continue

                comment = Comment(
                    video_id=video_id,
                    content=c['content'],
                    sentiment=classify_sentiment(c['content']),
                    user_name=c['user_name'],
                    user_level=c['user_level'],
                    gender=c['gender'],
                    region=c['region'],
                    created_at=datetime.fromtimestamp(c['created_at']) if c['created_at'] else None
                )
                db.session.add(comment)
                results['comments'] += 1

            db.session.commit()

    except Exception as e:
        results['errors'].append(f"评论: {str(e)}")

    # 爬取弹幕
    try:
        danmaku_list = spider.get_danmaku(video.platform_id)
        for d in danmaku_list:
            existing = Danmaku.query.filter_by(
                video_id=video_id,
                content=d['content'],
                progress_ms=d['progress_ms']
            ).first()
            if existing:
                continue

            danmaku = Danmaku(
                video_id=video_id,
                content=d['content'],
                progress_ms=d['progress_ms'],
                sentiment=classify_sentiment(d['content']),
                created_at=datetime.fromtimestamp(d['created_at']) if d['created_at'] else None
            )
            db.session.add(danmaku)
            results['danmaku'] += 1

        db.session.commit()

    except Exception as e:
        results['errors'].append(f"弹幕: {str(e)}")

    return jsonify(results)


@admin_bp.route('/stats/calc', methods=['POST'])
def calc_stats():
    """
    重新计算所有视频的热度分数
    """
    videos = Video.query.all()
    results = []

    for video in videos:
        latest_stat = video.stats.order_by(desc(VideoStats.stat_date)).first()
        if not latest_stat:
            continue

        # 统计情感
        comments = Comment.query.filter_by(video_id=video.id).all()
        pos = sum(1 for c in comments if c.sentiment == 1)
        neg = sum(1 for c in comments if c.sentiment == -1)
        neu = sum(1 for c in comments if c.sentiment == 0)

        sentiment_score = calc_sentiment_ratio(pos, neg, neu)

        # 计算热度
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
        latest_stat.sentiment_pos = pos
        latest_stat.sentiment_neg = neg
        latest_stat.sentiment_neu = neu

        db.session.commit()
        results.append({'video_id': video.id, 'heat_score': heat})

    return jsonify({'results': results})


@admin_bp.route('/videos', methods=['GET'])
def list_videos():
    """列出所有视频"""
    videos = Video.query.order_by(Video.created_at.desc()).all()
    return jsonify([{
        'id': v.id,
        'platform': v.platform,
        'title': v.title,
        'author': v.author,
        'created_at': v.created_at.isoformat() if v.created_at else None,
    } for v in videos])


# ==================== 用户管理 ====================

@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    """列出所有用户（仅管理员）"""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.isoformat() if u.created_at else None,
    } for u in users])


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    """获取单个用户信息"""
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() if user.created_at else None,
    })


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """更新用户信息（角色、状态）"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    # 不能修改自己的管理员身份
    if user_id == session.get('user_id') and data.get('role') != 'admin':
        return jsonify({'error': '不能取消自己的管理员身份'}), 400

    if 'role' in data:
        user.role = data['role']
    if 'is_active' in data:
        user.is_active = data['is_active']
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return jsonify({'error': '密码至少6位'}), 400
        user.set_password(data['password'])

    db.session.commit()
    return jsonify({'success': True, 'message': '更新成功'})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """删除用户（仅管理员）"""
    if user_id == session.get('user_id'):
        return jsonify({'error': '不能删除自己'}), 400

    user = User.query.get_or_404(user_id)

    # 删除用户的所有视频（及其评论弹幕）
    videos = Video.query.filter_by(user_id=user_id).all()
    for v in videos:
        Comment.query.filter_by(video_id=v.id).delete()
        Danmaku.query.filter_by(video_id=v.id).delete()
        VideoStats.query.filter_by(video_id=v.id).delete()
        db.session.delete(v)

    # 删除用户的Cookie配置
    PlatformCookie.query.filter_by(user_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': '删除成功'})


@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user():
    """管理员添加用户"""
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'user')

    if not username or not email or not password:
        return jsonify({'error': '请填写完整信息'}), 400

    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已被注册'}), 400

    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '创建成功',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
    })


# ==================== Cookie管理 ====================

@admin_bp.route('/cookies', methods=['GET'])
@login_required
def list_cookies():
    """获取当前用户的Cookie配置"""
    user_id = session.get('user_id')
    cookies = PlatformCookie.query.filter_by(user_id=user_id).order_by(PlatformCookie.platform, PlatformCookie.name).all()
    return jsonify([{
        'id': c.id,
        'platform': c.platform,
        'name': c.name,
        'cookie': c.cookie,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    } for c in cookies])


@admin_bp.route('/cookies', methods=['POST'])
@login_required
def save_cookie():
    """保存Cookie配置（自动命名，不覆盖）"""
    user_id = session.get('user_id')
    data = request.get_json()
    platform = data.get('platform', 'bilibili')
    cookie = data.get('cookie', '')
    name = data.get('name', '')

    if not cookie:
        return jsonify({'error': 'Cookie不能为空'}), 400

    # 生成唯一名称
    if not name:
        # 自动生成：platform-01, platform-02...
        prefix = platform
        existing = PlatformCookie.query.filter_by(user_id=user_id, platform=platform).all()
        nums = set()
        for c in existing:
            try:
                num = int(c.name.split('-')[-1])
                nums.add(num)
            except:
                pass
        # 找最小可用数字
        num = 1
        while num in nums:
            num += 1
        name = f"{prefix}-{num:02d}"
    else:
        # 检查名称是否重复
        existing = PlatformCookie.query.filter_by(user_id=user_id, name=name).first()
        if existing:
            return jsonify({'error': f'名称"{name}"已存在，请使用其他名称'}), 400

    new_cookie = PlatformCookie(
        user_id=user_id,
        platform=platform,
        name=name,
        cookie=cookie
    )
    db.session.add(new_cookie)
    db.session.commit()

    return jsonify({'success': True, 'message': f'保存成功，命名：{name}'})


@admin_bp.route('/cookies/<int:cookie_id>', methods=['PUT'])
@login_required
def update_cookie(cookie_id):
    """更新Cookie（名称和cookie值）"""
    user_id = session.get('user_id')
    cookie = PlatformCookie.query.filter_by(id=cookie_id, user_id=user_id).first_or_404()
    data = request.get_json()

    new_name = data.get('name', '').strip()
    new_cookie = data.get('cookie', '').strip()

    # 检查名称是否与其他重复
    if new_name:
        existing = PlatformCookie.query.filter(
            PlatformCookie.user_id == user_id,
            PlatformCookie.name == new_name,
            PlatformCookie.id != cookie_id
        ).first()
        if existing:
            return jsonify({'error': f'名称"{new_name}"已被其他Cookie使用'}), 400
        cookie.name = new_name

    if new_cookie:
        cookie.cookie = new_cookie

    db.session.commit()
    return jsonify({'success': True, 'message': '更新成功', 'name': cookie.name})


@admin_bp.route('/cookies/<int:cookie_id>', methods=['DELETE'])
@login_required
def delete_cookie(cookie_id):
    """删除Cookie配置"""
    user_id = session.get('user_id')
    cookie_config = PlatformCookie.query.filter_by(
        id=cookie_id,
        user_id=user_id
    ).first_or_404()

    db.session.delete(cookie_config)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@admin_bp.route('/cookies/batch-delete', methods=['POST'])
@login_required
def batch_delete_cookies():
    """批量删除Cookie"""
    user_id = session.get('user_id')
    data = request.get_json()
    ids = data.get('ids', [])

    if not ids:
        return jsonify({'error': '请选择要删除的Cookie'}), 400

    deleted = PlatformCookie.query.filter(
        PlatformCookie.id.in_(ids),
        PlatformCookie.user_id == user_id
    ).delete(synchronize_session=False)
    db.session.commit()

    return jsonify({'success': True, 'message': f'删除了{deleted}个Cookie'})


@admin_bp.route('/cookies/test', methods=['POST'])
@login_required
def test_cookie():
    """测试Cookie是否有效"""
    data = request.get_json()
    url = data.get('url', '')
    cookie = data.get('cookie', '')

    if not url:
        return jsonify({'error': 'URL不能为空'}), 400
    if not cookie:
        return jsonify({'error': 'Cookie不能为空'}), 400

    # 提取BV号
    import re
    match = re.search(r'(BV[\w]{10})', url)
    if not match:
        return jsonify({'error': '无法从URL提取BV号'}), 400

    bvid = match.group(1)

    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': cookie
        }
        resp = requests.get(f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
                            headers=headers, timeout=10)
        result = resp.json()

        if result.get('code') == 0:
            return jsonify({
                'success': True,
                'message': 'Cookie有效',
                'data': {
                    'title': result['data'].get('title', ''),
                    'aid': result['data'].get('aid', '')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f"API返回错误: {result.get('message', 'unknown')}"
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def get_user_cookie(user_id, platform='bilibili'):
    """获取用户的Cookie（优先使用用户自己的，没有则用系统配置的）"""
    # 先查用户的
    user_cookie = PlatformCookie.query.filter_by(
        user_id=user_id,
        platform=platform
    ).first()

    if user_cookie and user_cookie.cookie:
        return user_cookie.cookie

    # 没有则用系统配置的
    return current_app.config.get('BILIBILI_COOKIE', '')


# ========== 代理池管理 API ==========

@admin_bp.route('/proxies', methods=['GET'])
@login_required
def list_proxies():
    """获取代理列表"""
    user_id = session.get('user_id')
    proxies = ProxyIP.query.filter_by(user_id=user_id).order_by(ProxyIP.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'ip': p.ip,
        'port': p.port,
        'protocol': p.protocol,
        'is_active': p.is_active,
        'success_count': p.success_count,
        'fail_count': p.fail_count,
        'last_used': p.last_used.isoformat() if p.last_used else None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    } for p in proxies])


@admin_bp.route('/proxies', methods=['POST'])
@login_required
def add_proxy():
    """添加单个代理"""
    user_id = session.get('user_id')
    data = request.get_json()
    ip = data.get('ip', '')
    port = data.get('port', 0)
    protocol = data.get('protocol', 'http')

    if not ip or not port:
        return jsonify({'error': 'IP和端口不能为空'}), 400

    # 检查是否已存在
    existing = ProxyIP.query.filter_by(user_id=user_id, ip=ip, port=port).first()
    if existing:
        return jsonify({'error': '该代理已存在'}), 400

    proxy = ProxyIP(
        user_id=user_id,
        ip=ip,
        port=int(port),
        protocol=protocol
    )
    db.session.add(proxy)
    db.session.commit()

    return jsonify({'success': True, 'message': '添加成功'})


@admin_bp.route('/proxies/fetch', methods=['POST'])
@login_required
def fetch_proxies():
    """从快代理API获取代理"""
    user_id = session.get('user_id')
    data = request.get_json()
    api_url = data.get('api_url', '')

    if not api_url:
        return jsonify({'error': 'API链接不能为空'}), 400

    try:
        import requests
        resp = requests.get(api_url, timeout=30)
        text = resp.text.strip()

        # 解析代理列表（格式：ip:port@protocol，一行一个）
        lines = text.split('\n')
        added = 0
        skipped = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 解析格式：ip:port 或 ip:port@protocol
            parts = line.split('@')
            addr = parts[0]
            protocol = parts[1] if len(parts) > 1 else 'http'

            if ':' not in addr:
                skipped += 1
                continue

            ip, port = addr.split(':', 1)
            try:
                port = int(port)
            except ValueError:
                skipped += 1
                continue

            # 检查是否已存在
            existing = ProxyIP.query.filter_by(user_id=user_id, ip=ip, port=port).first()
            if existing:
                skipped += 1
                continue

            proxy = ProxyIP(
                user_id=user_id,
                ip=ip,
                port=port,
                protocol=protocol
            )
            db.session.add(proxy)
            added += 1

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'获取成功，新增{added}个，跳过{skipped}个（已存在）'
        })

    except Exception as e:
        return jsonify({'error': f'获取失败: {str(e)}'}), 500


@admin_bp.route('/proxies/<int:proxy_id>', methods=['DELETE'])
@login_required
def delete_proxy(proxy_id):
    """删除代理"""
    user_id = session.get('user_id')
    proxy = ProxyIP.query.filter_by(id=proxy_id, user_id=user_id).first_or_404()

    db.session.delete(proxy)
    db.session.commit()
    return jsonify({'success': True, 'message': '删除成功'})


@admin_bp.route('/proxies/<int:proxy_id>/test', methods=['POST'])
@login_required
def test_proxy():
    """测试单个代理是否可用"""
    user_id = session.get('user_id')
    proxy = ProxyIP.query.filter_by(id=proxy_id, user_id=user_id).first_or_404()

    data = request.get_json()
    test_url = data.get('test_url', 'https://www.bilibili.com')

    proxy_url = f'{proxy.protocol}://{proxy.ip}:{proxy.port}'

    try:
        import requests
        resp = requests.get(test_url, proxies={
            'http': proxy_url,
            'https': proxy_url
        }, timeout=10)

        if resp.status_code == 200:
            proxy.success_count += 1
            proxy.last_used = datetime.utcnow()
            proxy.is_active = True
            db.session.commit()
            return jsonify({'success': True, 'message': '代理可用'})
        else:
            proxy.fail_count += 1
            db.session.commit()
            return jsonify({'success': False, 'error': f'返回状态码: {resp.status_code}'})
    except Exception as e:
        proxy.fail_count += 1
        if proxy.fail_count > 10:
            proxy.is_active = False
        db.session.commit()
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/proxies/batch-delete', methods=['POST'])
@login_required
def batch_delete_proxies():
    """批量删除代理"""
    user_id = session.get('user_id')
    data = request.get_json()
    ids = data.get('ids', [])

    if not ids:
        return jsonify({'error': '请选择要删除的代理'}), 400

    ProxyIP.query.filter(ProxyIP.id.in_(ids), ProxyIP.user_id == user_id).delete(
        synchronize_session=False
    )
    db.session.commit()
    return jsonify({'success': True, 'message': f'删除了{len(ids)}个代理'})
