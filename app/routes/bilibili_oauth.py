# -*- coding: utf-8 -*-
"""
B站扫码登录OAuth
"""

import requests
import time
import hashlib

BILIBILI_OAUTH_URL = 'https://passport.bilibili.com/qrcode'
BILIBILI_APP_KEY = '6f6c09e0795b40a3'
BILIBILI_APP_SECRET = ''


def generate_qrcode():
    """
    生成B站扫码登录二维码

    Returns:
        tuple: (oauth_key, qrcode_url) 或 (None, None)
    """
    try:
        # B站扫码登录API
        url = 'https://passport.bilibili.com/qrcode/h5/generate'
        data = {
            'oauth_key': '',
            'source': 'main_web',
            'appkey': BILIBILI_APP_KEY,
            'TS': int(time.time()),
        }

        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()

        if result.get('code') == 0:
            oauth_key = result['data']['oauthKey']
            # 生成扫码URL
            qr_url = result['data']['url']
            # 生成二维码内容（URL编码后的登录URL）
            import urllib.parse
            qr_content = urllib.parse.quote(qr_url)
            return oauth_key, qr_content

        print(f"B站二维码生成失败: {result}")
        return None, None

    except Exception as e:
        print(f"B站二维码生成异常: {e}")
        return None, None


def query_qrcode_status(oauth_key):
    """
    查询扫码状态

    Returns:
        dict: {
            'status': 'waiting' | 'scanned' | 'confirmed' | 'expired',
            'cookie': '...' (confirmed时返回),
            'url': '...' (扫码后的跳转URL)
        }
    """
    try:
        url = 'https://passport.bilibili.com/qrcode/h5/query'
        data = {
            'oauthKey': oauth_key,
            'source': 'main_web',
            'appkey': BILIBILI_APP_KEY,
            'TS': int(time.time()),
        }

        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()

        if result.get('code') == 0:
            status_data = result['data']
            status = status_data.get('status')

            if status == 'confirmed':
                # 登录成功，返回cookie
                return {
                    'status': 'confirmed',
                    'cookie': status_data.get('cookie', ''),
                    'url': status_data.get('url', '')
                }
            elif status == 'scanned':
                return {'status': 'scanned'}
            elif status == 'waiting':
                return {'status': 'waiting'}
            else:
                return {'status': 'expired'}

        return {'status': 'error', 'msg': result.get('message', 'unknown')}

    except Exception as e:
        return {'status': 'error', 'msg': str(e)}


if __name__ == '__main__':
    # 测试
    key, content = generate_qrcode()
    print(f"oauth_key: {key}")
    print(f"qr_content: {content}")
