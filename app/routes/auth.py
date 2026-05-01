# -*- coding: utf-8 -*-
"""
认证路由 - 注册/登录/密码找回
"""

import re
import random
import string
import time
from flask import Blueprint, request, jsonify, session
from ..models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def send_email_code(email, code):
    """发送验证码到邮箱"""
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    from email.utils import formataddr

    # 邮件配置
    SMTP_SERVER = 'smtp.qq.com'
    SMTP_PORT = 587
    SENDER_EMAIL = '320782268@qq.com'
    SENDER_PASSWORD = 'oaulcjvaeauqbigj'  # QQ邮箱授权码（16位）

    # 调试模式：同时在控制台打印验证码
    print(f"\n{'='*50}")
    print(f"验证码邮件 - 收件人: {email}")
    print(f"验证码: {code}")
    print(f"{'='*50}\n")

    try:
        msg = MIMEText(f'【视频热度分析系统】您的验证码是：{code}，5分钟内有效。', 'plain', 'utf-8')
        msg['From'] = formataddr(('视频热度分析系统', SENDER_EMAIL))
        msg['To'] = formataddr(('', email))
        msg['Subject'] = Header('验证码', 'utf-8')

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [email], msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"邮件发送失败 - 认证错误: 授权码可能不正确。请到QQ邮箱设置中重新生成授权码。")
        return False
    except smtplib.SMTPException as e:
        print(f"邮件发送失败 - SMTP错误: {e}")
        return False
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def generate_code(length=6):
    """生成数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


# 存储验证码（生产环境用Redis）
email_codes = {}  # {email: {'code': xxx, 'expire': timestamp}}


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    用户注册

    Body: { "username": "xxx", "email": "xxx@xxx.com", "password": "xxx", "code": "验证码" }
    """
    data = request.get_json()

    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    code = data.get('code', '')

    # 基础验证
    if not username or not email or not password:
        return jsonify({'error': '请填写完整信息'}), 400

    if len(password) < 6:
        return jsonify({'error': '密码至少6位'}), 400

    if not re.match(r'^[\w\-\.]+@([\w\-]+\.)+[\w\-]+$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    # 验证验证码
    if email in email_codes:
        stored = email_codes[email]
        if stored['code'] != code:
            return jsonify({'error': '验证码错误'}), 400
        if time.time() > stored['expire']:
            del email_codes[email]
            return jsonify({'error': '验证码已过期'}), 400
        del email_codes[email]  # 验证成功后删除
    else:
        return jsonify({'error': '请先获取验证码'}), 400

    # 检查用户名/邮箱是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '用户名已存在'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': '邮箱已被注册'}), 400

    # 创建用户
    user = User(username=username, email=email, role='user')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '注册成功',
        'user': {'id': user.id, 'username': user.username, 'role': user.role}
    })


@auth_bp.route('/send_code', methods=['POST'])
def send_code():
    """
    发送邮箱验证码（注册/找回密码）

    Body: { "email": "xxx@xxx.com", "type": "register|reset" }
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code_type = data.get('type', 'register')

    if not re.match(r'^[\w\-\.]+@([\w\-]+\.)+[\w\-]+$', email):
        return jsonify({'error': '邮箱格式不正确'}), 400

    # 检查邮箱是否已注册（注册时不能已存在，找回密码时必须存在）
    existing_user = User.query.filter_by(email=email).first()
    if code_type == 'register' and existing_user:
        return jsonify({'error': '该邮箱已注册'}), 400
    if code_type == 'reset' and not existing_user:
        return jsonify({'error': '该邮箱未注册'}), 400

    # 生成并发送验证码
    code = generate_code()
    email_codes[email] = {'code': code, 'expire': time.time() + 300}  # 5分钟有效期

    # 先打印到控制台（调试用）
    print(f"\n{'='*50}")
    print(f"验证码 - 收件人: {email}")
    print(f"验证码: {code}")
    print(f"{'='*50}\n")

    if send_email_code(email, code):
        return jsonify({'success': True, 'message': '验证码已发送'})
    else:
        # 邮件发送失败，但验证码已打印到控制台
        return jsonify({
            'success': True,
            'message': '验证码已生成（邮件发送失败，请查看服务器控制台）',
            'code': code  # 调试模式下直接返回验证码
        })


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录

    Body: { "username": "xxx", "password": "xxx" }
    """
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '请填写用户名和密码'}), 400

    # 支持用户名或邮箱登录
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 400

    if not user.is_active:
        return jsonify({'error': '账号已被禁用'}), 400

    # 设置session
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role

    return jsonify({
        'success': True,
        'message': '登录成功',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """退出登录"""
    session.clear()
    return jsonify({'success': True, 'message': '已退出'})


@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    """
    重置密码

    Body: { "email": "xxx@xxx.com", "code": "xxx", "new_password": "xxx" }
    """
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    code = data.get('code', '')
    new_password = data.get('new_password', '')

    if not all([email, code, new_password]):
        return jsonify({'error': '请填写完整信息'}), 400

    if len(new_password) < 6:
        return jsonify({'error': '密码至少6位'}), 400

    # 验证验证码
    if email in email_codes:
        stored = email_codes[email]
        if stored['code'] != code:
            return jsonify({'error': '验证码错误'}), 400
        if time.time() > stored['expire']:
            del email_codes[email]
            return jsonify({'error': '验证码已过期'}), 400
        del email_codes[email]
    else:
        return jsonify({'error': '请先获取验证码'}), 400

    # 更新密码
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': '用户不存在'}), 400

    user.set_password(new_password)
    db.session.commit()

    return jsonify({'success': True, 'message': '密码重置成功'})


@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """获取当前登录用户信息"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None})

    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({'user': None})

    return jsonify({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }
    })


@auth_bp.route('/check_admin', methods=['GET'])
def check_admin():
    """检查当前用户是否为管理员"""
    role = session.get('role')
    return jsonify({'is_admin': role == 'admin'})


# ==================== B站扫码登录 ====================

@auth_bp.route('/bilibili/qrcode', methods=['GET'])
def get_bilibili_qrcode():
    """
    获取B站扫码登录二维码

    Returns: {
        'oauth_key': 'xxx',
        'qrcode_url': 'https://...'
    }
    """
    import urllib.parse

    try:
        import requests
        url = 'https://passport.bilibili.com/qrcode/h5/generate'
        data = {
            'oauthKey': '',
            'source': 'main_web',
            'appkey': '6f6c09e0795b40a3',
            'TS': int(time.time()),
        }

        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()

        if result.get('code') == 0:
            oauth_key = result['data']['oauthKey']
            raw_url = result['data']['url']
            # 生成二维码内容（URL编码）
            qrcode_url = urllib.parse.quote(raw_url)

            # 存储oauth_key到session用于后续验证
            session['bilibili_oauth_key'] = oauth_key

            return jsonify({
                'success': True,
                'oauth_key': oauth_key,
                'qrcode_url': f'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qrcode_url}'
            })

        return jsonify({'success': False, 'error': result.get('message', '生成二维码失败')})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@auth_bp.route('/bilibili/qrcode/query', methods=['POST'])
def query_bilibili_qrcode():
    """
    查询B站扫码状态

    Body: { "oauth_key": "xxx" }
    Returns: {
        'status': 'waiting' | 'scanned' | 'confirmed' | 'expired',
        'cookie': '...' (confirmed时)
    }
    """
    try:
        data = request.get_json()
        oauth_key = data.get('oauth_key') or session.get('bilibili_oauth_key')

        if not oauth_key:
            return jsonify({'status': 'error', 'error': '缺少oauth_key'})

        url = 'https://passport.bilibili.com/qrcode/h5/query'
        post_data = {
            'oauthKey': oauth_key,
            'source': 'main_web',
            'appkey': '6f6c09e0795b40a3',
            'TS': int(time.time()),
        }

        resp = requests.post(url, data=post_data, timeout=10)
        result = resp.json()

        if result.get('code') == 0:
            status_data = result['data']
            status = status_data.get('status')

            if status == 'confirmed':
                # 登录成功，提取cookie
                cookie_str = status_data.get('cookie', '')
                return jsonify({
                    'status': 'confirmed',
                    'cookie': cookie_str,
                    'message': '扫码成功'
                })
            elif status == 'scanned':
                return jsonify({'status': 'scanned', 'message': '已扫码，请确认'})
            elif status == 'waiting':
                return jsonify({'status': 'waiting', 'message': '等待扫码'})
            else:
                return jsonify({'status': 'expired', 'message': '二维码已过期'})

        return jsonify({'status': 'error', 'error': result.get('message', '查询失败')})

    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})
