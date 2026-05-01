# 视频数据项目 - 完整部署指南

## 项目简介

**many_movie** - 视频数据驾驶舱，支持 B站/抖音等平台的视频数据爬取、展示和热度计算。

---

## 目录

1. [项目结构](#1-项目结构)
2. [环境要求](#2-环境要求)
3. [快速部署（服务器）](#3-快速部署服务器)
4. [完整部署步骤](#4-完整部署步骤)
5. [配置说明](#5-配置说明)
6. [启动验证](#6-启动验证)
7. [Nginx 配置](#7-nginx-配置)
8. [故障排查](#8-故障排查)

---

## 1. 项目结构

```
many_movie/
├── run.py                    # 启动入口
├── requirements.txt          # Python 依赖
├── gunicorn_config.py        # Gunicorn 配置（生产环境）
├── .env.example             # 环境变量示例
├── deploy.sh                # 部署脚本
├── app/                     # 应用包
│   ├── __init__.py          # Flask 工厂、数据库初始化
│   ├── config.py            # 配置类
│   ├── models.py            # 数据模型
│   ├── routes/              # 路由
│   │   ├── api.py           # API 路由
│   │   ├── web.py           # 页面路由
│   │   ├── auth.py          # 认证路由
│   │   └── admin.py         # 管理员路由
│   ├── spiders/             # 爬虫
│   │   ├── bilibili.py      # B站爬虫
│   │   └── douyin.py        # 抖音爬虫
│   ├── analysis/            # 数据分析
│   │   ├── heat.py          # 热度算法
│   │   └── sentiment.py     # 情感分析
│   └── visualization/       # 可视化
│       ├── bilibili.py      # B站大屏
│       └── douyin.py        # 抖音大屏
├── templates/               # HTML 模板
│   ├── index.html          # 首页
│   ├── video_vue3.html     # 视频详情页（Vue3 大屏）
│   ├── admin.html          # 管理页
│   └── auth.html           # 登录注册页
└── static/                 # 静态资源
```

---

## 2. 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.8+ |
| MySQL | 5.7+ |
| Nginx | 1.18+ |
| 内存 | 1GB+（推荐 2GB+） |
| 系统 | Ubuntu 20.04+ / CentOS 7+ |

---

## 3. 快速部署（服务器）

### 3.1 一键部署脚本

```bash
# 在服务器上创建项目目录
mkdir -p /root/kui_project && cd /root/kui_project

# 上传项目文件（本地执行）
# scp -r /path/to/many_movie/* root@your-server:/root/kui_project/

# 安装依赖
pip3 install -r requirements.txt

# 创建环境变量文件
cat > .env << 'EOF'
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-mysql-password
MYSQL_DATABASE=kui_db
SECRET_KEY=your-random-secret-key
FLASK_ENV=production
EOF

# 启动 Gunicorn
nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &

# 验证
curl http://127.0.0.1:8080/
```

---

## 4. 完整部署步骤

### 4.1 服务器环境准备

#### Ubuntu/Debian:

```bash
# 更新系统
apt update && apt upgrade -y

# 安装基础软件
apt install -y python3 python3-pip nginx mysql-server git

# 安装 Python 开发库（编译依赖）
apt install -y libmysqlclient-dev python3-dev pkg-config
```

#### CentOS:

```bash
yum update -y
yum install -y python3 python3-pip nginx mysql-server git
yum install -y python3-devel mysql-devel gcc
```

### 4.2 MySQL 配置

```bash
# 启动 MySQL
systemctl start mysql  # Ubuntu
systemctl start mysqld  # CentOS

# 连接 MySQL
mysql -u root -p

# 在 MySQL 中执行：
CREATE DATABASE IF NOT EXISTS kui_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'kui_user'@'%' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON kui_db.* TO 'kui_user'@'%';
FLUSH PRIVILEGES;
EXIT;
```

### 4.3 上传项目

**方式一：SCP（本地执行）**
```bash
scp -r /path/to/many_movie root@your-server:/root/kui_project
```

**方式二：Git（如果用 Git 管理）**
```bash
git clone your-repo-url /root/kui_project
```

### 4.4 安装 Python 依赖

```bash
cd /root/kui_project
pip3 install -r requirements.txt
```

### 4.5 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置
nano .env
```

**必须修改的配置：**
```env
MYSQL_HOST=your-mysql-host          # MySQL 服务器地址
MYSQL_USER=kui_user                  # MySQL 用户名
MYSQL_PASSWORD=your-password          # MySQL 密码
MYSQL_DATABASE=kui_db                # 数据库名
SECRET_KEY=random-secret-key-here   # 随机密钥
```

### 4.6 启动 Gunicorn

```bash
cd /root/kui_project

# 启动（后台运行）
nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &

# 检查进程
ps aux | grep gunicorn

# 查看日志
tail -20 gunicorn.log
```

### 4.7 配置 Nginx

```bash
# 创建 Nginx 配置
cat > /etc/nginx/sites-available/kui_project << 'EOF'
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    access_log /var/log/nginx/kui_access.log;
    error_log /var/log/nginx/kui_error.log;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
EOF

# 启用站点
ln -sf /etc/nginx/sites-available/kui_project /etc/nginx/sites-enabled/kui_project

# 测试并重启
nginx -t && systemctl reload nginx
```

### 4.8 配置域名 DNS

在域名服务商添加 DNS 记录：
- **记录类型**: A
- **主机记录**: `@` 和 `www`
- **记录值**: `你的服务器IP`

### 4.9 SSL 证书（可选但推荐）

```bash
# 安装 Certbot
apt install -y certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d your-domain.com -d www.your-domain.com

# 自动续期（Certbot 会自动配置）
```

---

## 5. 配置说明

### 5.1 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MYSQL_HOST` | 127.0.0.1 | MySQL 服务器地址 |
| `MYSQL_PORT` | 3306 | MySQL 端口 |
| `MYSQL_USER` | root | MySQL 用户名 |
| `MYSQL_PASSWORD` | 123456 | MySQL 密码 |
| `MYSQL_DATABASE` | kui_db | 数据库名 |
| `SECRET_KEY` | - | Flask 密钥（必须修改） |
| `FLASK_ENV` | production | 运行环境 |
| `REDIS_HOST` | 127.0.0.1 | Redis 服务器（预留） |
| `REDIS_PORT` | 6379 | Redis 端口（预留） |

### 5.2 Gunicorn 配置

`gunicorn_config.py` 中的关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `workers` | 1 | Worker 进程数（内存 <= 2GB 时自动限制为 1） |
| `threads` | 2 | 每个 worker 的线程数 |
| `timeout` | 120 | 请求超时（秒） |
| `max_requests` | 500 | 单 worker 处理此数量后自动重启（防止内存泄漏） |
| `keepalive` | 5 | 保持连接时间 |

### 5.3 内存保护机制

1. **Worker 数量限制**：自动检测内存，<= 2GB 时只用 1 worker
2. **请求数限制**：每个 worker 处理 500 请求后重启，防止内存泄漏
3. **超时限制**：120 秒无响应则断开，防止僵尸进程

---

## 6. 启动验证

### 6.1 本地测试

```bash
# 直接启动 Flask（开发模式）
cd /root/kui_project
python3 run.py

# 访问 http://127.0.0.1:8080/
```

### 6.2 Gunicorn 测试

```bash
# 前台运行（查看日志）
gunicorn -c gunicorn_config.py run:app

# 后台运行
nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &

# 检查状态
ps aux | grep gunicorn
curl http://127.0.0.1:8080/
```

### 6.3 检查日志

```bash
# Gunicorn 日志
tail -50 gunicorn.log
tail -50 gunicorn_error.log

# Nginx 日志
tail -50 /var/log/nginx/kui_access.log
tail -50 /var/log/nginx/kui_error.log
```

---

## 7. Nginx 配置（生产环境推荐）

### 7.1 完整配置（内存保护版）

```nginx
# /etc/nginx/nginx.conf

user www-data;
worker_processes auto;
worker_rlimit_nofile 65535;
pid /run/nginx.pid;

events {
    worker_connections 256;
    multi_accept off;
    use epoll;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # 内存保护
    client_body_buffer_size     8k;
    client_header_buffer_size   1k;
    client_max_body_size       4m;
    large_client_header_buffers 2 4k;

    # 超时
    keepalive_timeout    20s;
    keepalive_requests  50;
    client_body_timeout  10s;
    client_header_timeout 10s;
    send_timeout        20s;

    # 代理配置
    proxy_buffering    on;
    proxy_buffer_size  2k;
    proxy_buffers      4 2k;
    proxy_busy_buffers_size 2k;
    proxy_connect_timeout 10s;
    proxy_read_timeout  45s;
    proxy_send_timeout  45s;

    # 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # 日志
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # 连接限制
    limit_conn_zone $binary_remote_addr zone=addr:10m;
    limit_conn addr 50;

    # 上游
    upstream kui_backend {
        server 127.0.0.1:8080;
        keepalive 16;
    }

    include /etc/nginx/sites-enabled/*;
}
```

### 7.2 站点配置

```nginx
# /etc/nginx/sites-available/kui_project

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # 限流
    limit_req zone=one burst=10 nodelay;

    access_log /var/log/nginx/kui_access.log;
    error_log /var/log/nginx/kui_error.log;

    location / {
        proxy_pass http://kui_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

---

## 8. 故障排查

### 8.1 502 Bad Gateway

```bash
# 检查 Gunicorn 是否运行
ps aux | grep gunicorn

# 检查端口
netstat -tlnp | grep 8080

# 查看错误日志
tail -50 gunicorn_error.log
```

### 8.2 连接 MySQL 失败

```bash
# 测试 MySQL 连接
mysql -h your-mysql-host -u kui_user -p kui_db

# 检查用户权限
mysql -u root -p -e "SHOW GRANTS FOR 'kui_user'@'%';"
```

### 8.3 内存不足（OOM）

```bash
# 查看内存使用
free -h

# 查看 OOM 日志
dmesg | grep -i "out of memory"
tail -100 /var/log/syslog | grep -i oom

# 解决：确保 gunicorn 只用 1 worker
pkill -f gunicorn
nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &
```

### 8.4 Nginx 502 但 Gunicorn 正常

```bash
# 检查 Nginx upstream 配置
nginx -t

# 检查 selinux（CentOS）
getenforce
setenforce 0

# 检查防火墙
ufw status
iptables -L
```

### 8.5 域名无法访问

1. 确认 DNS 记录已生效：`ping your-domain.com`
2. 确认服务器防火墙开放 80 端口
3. 确认 Nginx 已重载：`systemctl status nginx`

---

## 9. 常用管理命令

| 操作 | 命令 |
|------|------|
| 启动 Gunicorn | `gunicorn -c gunicorn_config.py run:app` |
| 重启 Gunicorn | `pkill -f gunicorn && nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &` |
| 查看 Gunicorn 日志 | `tail -f gunicorn.log` |
| 检查 Gunicorn 进程 | `ps aux \| grep gunicorn` |
| 重载 Nginx | `systemctl reload nginx` |
| 重启 Nginx | `systemctl restart nginx` |
| 查看 Nginx 日志 | `tail -f /var/log/nginx/access.log` |

---

## 10. 安全建议

1. **修改默认密码**：MySQL root 密码、Flask SECRET_KEY
2. **防火墙**：只开放 80/443 端口
3. **SSL**：生产环境务必使用 HTTPS
4. **定期备份**：数据库和上传的文件
5. **监控**：配置服务器监控，防止内存/磁盘耗尽

---

## 11. 联系与支持

如有问题，请检查：
1. `gunicorn_error.log` 日志
2. `/var/log/nginx/error.log` Nginx 错误日志
3. MySQL 错误日志
