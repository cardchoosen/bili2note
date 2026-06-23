# bili2note

Turn online course videos into well-structured markdown notes that capture every key point — so you can read instead of watch.

## Overview

输入一个 B站视频 URL，端到端生成一篇 Markdown 学习笔记，信息完整度对齐原视频。笔记采用专业段落叙述风格，保留全部知识点与推导细节，省略无关闲聊。长视频自动分段处理，逐段生成后合并。

字幕获取默认走 ASR（whisper 本地转录），质量更可靠。也可通过 `--bilibili-sub` 使用 B站 API 字幕。

支持两种运行模式。agent 模式零配置开箱即用，CLI 完成字幕获取与预处理后输出中间文件，由 AI agent 接力生成笔记。API 模式填入 LLM 配置后全自动运行，一条命令出笔记。

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

需要 Python 3.10+、ffmpeg。系统工具通过 Homebrew 安装：

```bash
brew install ffmpeg yt-dlp
```

## Usage

```bash
source .venv/bin/activate
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

默认走 ASR 转录 + API 模式全自动生成笔记。

### 使用 B站 API 字幕

```bash
python -m bilibili_note --bilibili-sub "https://www.bilibili.com/video/BVxxxxx"
```

## Configuration

见 `config.yaml`。`llm` 配置 OpenAI 兼容接口，留空走 agent 模式，填入后走 API 模式。`bilibili.cookies_path` 指向 cookies 文件（JSON 数组格式），B站 API 字幕需要登录态。`subtitle.asr_model` 控制 whisper 模型大小，默认 small。

## License

MIT
