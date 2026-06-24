# bili2note

Turn B站 course videos into well-structured markdown notes — read instead of watch.

## Overview

输入一个 B站视频 URL，端到端生成一篇 Markdown 学习笔记，信息完整度对齐原视频。笔记采用专业段落叙述风格，保留全部知识点与推导细节，省略无关闲聊。

字幕通过 ASR 转录（whisper 本地识别），无需登录态，质量可靠。长视频自动分段处理，逐段 LLM 生成后合并。

支持两种运行模式：agent 模式零配置开箱即用，CLI 输出中间文件由外部 agent 接力生成；API 模式填入 LLM 配置后全自动一条命令出笔记。

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

需要 Python 3.10+、ffmpeg、yt-dlp：

```bash
brew install ffmpeg yt-dlp
```

首次运行会自动下载 whisper 模型（~460MB），缓存于 `~/.cache/whisper/`。

## Usage

```bash
source .venv/bin/activate
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

API 模式下全自动：下载音频 → whisper 转录 → LLM 校对字幕 → LLM 生成笔记 → 输出 token 统计。

可选参数：

```
--segment-seconds N   字幕分段时长（秒），默认 600（10分钟）
-c / --config PATH    指定配置文件路径，默认 config.yaml
```

## Configuration

见 `config.yaml`。`llm` 填入 OpenAI 兼容接口配置后启用 API 模式，留空走 agent 模式。`subtitle.asr_model` 控制 whisper 模型大小，默认 small。

## License

MIT
