#!/usr/bin/env bash
set -e

echo "==> 安装 yt-dlp"
if ! command -v yt-dlp &>/dev/null; then
  if command -v brew &>/dev/null; then
    brew install yt-dlp
  else
    pip install -U yt-dlp
  fi
else
  echo "yt-dlp 已安装: $(yt-dlp --version)"
fi

echo "==> 安装 Python 依赖"
pip install -r requirements.txt

echo "==> 完成"
