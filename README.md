# bili2note

Turn online course videos into well-structured markdown notes that capture every key point — so you can read instead of watch.

## Overview

输入一个 B站视频 URL，端到端生成一篇 Markdown 学习笔记，信息完整度对齐原视频。笔记采用专业段落叙述风格，保留全部知识点与推导细节，省略无关闲聊。长视频自动分段处理，逐段生成后合并。

支持两种运行模式。agent 模式零配置开箱即用，CLI 完成字幕获取与预处理后输出中间文件，由 AI agent 接力生成笔记。API 模式填入 LLM 配置后全自动运行，一条命令出笔记。两种模式下都输出 token 用量统计。

## Installation

```bash
bash setup.sh
```

需要 Python 3.10+、yt-dlp、ffmpeg。脚本会自动安装 yt-dlp。

## Usage

### 快速开始

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

默认零配置运行，输出字幕文件到 notes/ 目录。将文件内容交给 AI agent 即可生成最终笔记。

### 全自动模式

在 config.yaml 填入 LLM 配置后，一条命令端到端出笔记，无需人工介入：

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

### 强制 ASR

字幕不可用或质量差时，加 `--asr` 直接转录音频：

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx" --asr
```

## Configuration

见 `config.yaml`。`llm` 配置 OpenAI 兼容接口，留空走 agent 模式，填入后走 API 模式。`bilibili.cookies_path` 指向 cookies 文件，部分视频的 AI 字幕需要登录态。`subtitle.asr_model` 控制 whisper 模型大小，默认 small。

Cookies 文件支持 JSON 数组格式和 Netscape 格式。用浏览器登录 B站后导出即可。

## License

MIT
