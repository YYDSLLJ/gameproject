#!/bin/bash
# -*- coding: utf-8 -*-
"""
部署脚本
将项目部署到远程服务器

用法:
    ./deploy.sh                    # 交互式部署
    ./deploy.sh --server 120.24.224.245 --user root  # 非交互式
"""

set -e

# 默认配置
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_DIR="/root/kui_project"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --server <IP>       服务器IP"
    echo "  --user <用户>       SSH用户 (默认: root)"
    echo "  --dir <目录>        远程目录 (默认: /root/kui_project)"
    echo "  --help              显示帮助"
    exit 1
}

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --server)
            REMOTE_HOST="$2"
            shift 2
            ;;
        --user)
            REMOTE_USER="$2"
            shift 2
            ;;
        --dir)
            REMOTE_DIR="$2"
            shift 2
            ;;
        --help)
            usage
            ;;
        *)
            log_error "未知参数: $1"
            usage
            ;;
    esac
done

# 检查必填参数
if [ -z "$REMOTE_HOST" ]; then
    log_error "请指定服务器IP (--server)"
    usage
fi

echo "=== 部署配置 ==="
echo "服务器: $REMOTE_HOST"
echo "用户: $REMOTE_USER"
echo "远程目录: $REMOTE_DIR"
echo "本地目录: $LOCAL_DIR"
echo ""

log_info "开始部署..."

# 1. 打包项目
log_info "[1/4] 打包项目..."
cd "$LOCAL_DIR"
tar --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='venv' \
    --exclude='*.log' \
    --exclude='gunicorn*.log' \
    -czf /tmp/kui_project.tar.gz .

# 2. 上传到服务器
log_info "[2/4] 上传到服务器..."
ssh $REMOTE_USER@$REMOTE_HOST "mkdir -p $REMOTE_DIR"
scp /tmp/kui_project.tar.gz $REMOTE_USER@$REMOTE_HOST:/tmp/

# 3. 解压并安装
log_info "[3/4] 安装依赖..."
ssh $REMOTE_USER@$REMOTE_HOST << 'EOF'
cd /root/kui_project
tar -xzf /tmp/kui_project.tar.gz

# 安装Python依赖
pip3 install -r requirements.txt

# 复制环境变量示例
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "=========================================="
    echo "请编辑 .env 文件配置数据库等参数"
    echo "=========================================="
fi

echo "安装完成"
EOF

# 4. 重启服务
log_info "[4/4] 重启服务..."
ssh $REMOTE_USER@$REMOTE_HOST << 'EOF'
cd /root/kui_project

# 停止旧进程
pkill -f "gunicorn" || true
pkill -f "python.*run.py" || true
sleep 2

# 启动Gunicorn
nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &
sleep 2

# 检查进程
if pgrep -f "gunicorn" > /dev/null; then
    echo "Gunicorn 已启动"
    ps aux | grep gunicorn | grep -v grep
else
    echo "启动失败，查看日志："
    cat /root/kui_project/gunicorn_error.log
fi
EOF

echo ""
echo "=== 部署完成 ==="
echo ""
echo "下一步操作："
echo "1. SSH 登录服务器: ssh $REMOTE_USER@$REMOTE_HOST"
echo "2. 编辑 .env 文件配置数据库"
echo "3. 重启 Gunicorn: pkill -f gunicorn && nohup gunicorn -c gunicorn_config.py run:app > gunicorn.log 2>&1 &"
echo "4. 配置 Nginx (参考 视频数据项目部署指南.md)"
echo "5. 配置域名 DNS"
