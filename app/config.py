# -*- coding: utf-8 -*-
import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-me')

    # MySQL
    MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '123456')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'kui_db')

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
        "?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 3600
    SQLALCHEMY_POOL_PRE_PING = True

    # Redis
    REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # Spider
    BILIBILI_COOKIE = os.getenv('BILIBILI_COOKIE', 'enable_web_push=DISABLE; buvid4=0EDA306C-B28D-E3B0-55D0-6AC8E5FDFC9920844-024102510-MlH4VqHA4NyA4yHMiHmbKQ%3D%3D; buvid_fp_plain=undefined; enable_feed_channel=ENABLE; fingerprint=3112bae24efb5a398f53400dcb52fd97; buvid_fp=2f4fa3123ec28136f28d0a2c39152dc9; header_theme_version=OPEN; theme-tip-show=SHOWED; theme-avatar-tip-show=SHOWED; DedeUserID=332703800; DedeUserID__ckMd5=f634fcb2d8bbf828; theme-switch-show=SHOWED; theme_style=dark; buvid3=6F0D7D41-35DB-CADA-A5EA-F8D342B64FD738038infoc; b_nut=1761453738; _uuid=A683B43D-2856-527F-7413-D57CCA41E58E38999infoc; rpdid=%7C%28kR%29km%7CuYR0J%27u%7EYRRkRRlu; hit-dyn-v2=1; LIVE_BUVID=AUTO5717658834545832; ogv_device_support_hdr=0; ogv_device_support_dolby=0; home_feed_column=5; CURRENT_QUALITY=32; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NzUxMjg4OTcsImlhdCI6MTc3NDg2OTYzNywicGx0IjotMX0.UG2LDI2KQRP7_7Of5utPvENWxKT-5Z7MtgckPn2BeDY; bili_ticket_expires=1775128837; SESSDATA=92b1a85c%2C1790421697%2Ca0556%2A31CjDJDJq9xnGA_7IUIGZigE8-Y43aBN1C6yg5FVE96WPMdkBR7-BLSBV7HRKLj17VBVgSVjlVZU1ieFF4UGRnZmJLbEFZMkxFZTRlX3M1WWRyREZMcHJhYXh5aG1CVTh0dzBtMVl1RDZmak5wR0h5d3dISEN5ZGhfbFBUQnN0OUxuZFhmbk1FQjR3IIEC; bili_jct=ce347fa2974c8b65bc06a3286cb57831; sid=85n4xroi; PVID=2; browser_resolution=1912-994; CURRENT_FNVAL=4048; bp_t_offset_332703800=1186629408673234944; b_lsid=6B257B9F_19D4D89ACD1')
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    # Sentiment
    FONT_PATH = os.getenv('FONT_PATH', '/usr/share/fonts/truetype/simhei.ttf')

    # Scheduler
    SCHEDULER_API_ENABLED = True
