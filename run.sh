#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "==> 创建虚拟环境..."
    python3 -m venv .venv
fi

source .venv/bin/activate

if [ $# -eq 0 ]; then
    echo "用法: ./run.sh <B站视频URL> [额外参数]"
    echo "示例: ./run.sh 'https://www.bilibili.com/video/BVxxxxx?p=7'"
    exit 1
fi

if ! python3 -c "import httpx" 2>/dev/null; then
    echo "==> 安装依赖..."
    pip install -r requirements.txt
fi

python3 -m bilibili_note "$@"
