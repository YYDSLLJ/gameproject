#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动文件
支持环境变量和 .env 配置文件
"""

import os
from dotenv import load_dotenv

# 尝试加载 .env 文件（如果存在）
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

from app import create_app

app = create_app()


def main():
    """生产环境启动（使用 gunicorn 时不需要此函数）"""
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    main()
