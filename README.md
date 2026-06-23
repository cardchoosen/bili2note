# bili2note

Turn online course videos into well-structured markdown notes that capture every key point — so you can read instead of watch.

## Overview

输入一个 B站视频 URL，端到端生成一篇 Markdown 学习笔记，信息完整度对齐原视频。笔记采用专业段落叙述风格，保留全部知识点与推导细节，省略无关闲聊。

字幕获取以 B站 API 为主，CC 字幕优先、AI 字幕兜底。遇到字幕不可用或质量差的视频，自动降级到 ASR 转录（whisper），也可通过 `--asr` 参数强制走 ASR。ASR 产出的字幕会经过一轮 LLM 校对——修正识别错误、繁简统一、补标点——再送入笔记生成。

长视频按 10 分钟分段处理，逐段生成后合并。API 模式下输出完整 token 用量统计。

## Installation

```bash
bash setup.sh
```

需要 Python 3.10+、yt-dlp、ffmpeg。脚本会自动安装 yt-dlp。

## Usage

### Agent 模式（默认，零配置）

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

CLI 抓取字幕并预处理，输出结构化字幕文件到 notes/。将字幕文件交给 AI agent 生成最终笔记。

### API 模式（全自动）

在 config.yaml 填入 LLM 配置（base_url / api_key / model）后，CLI 端到端完成字幕获取、LLM 校对、笔记生成、输出 md，无需人工介入。

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

### 强制 ASR

跳过 B站字幕，直接下载音频用 whisper 转录。适用于字幕不可用或质量差的视频。

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx" --asr
```

## Configuration

见 `config.yaml`。`llm` 配置 OpenAI 兼容接口，留空走 agent 模式，填入后走 API 模式。`bilibili.cookies_path` 指向 cookies 文件（JSON 或 Netscape 格式），AI 字幕需要登录态。`subtitle.asr_model` 控制 whisper 模型大小，默认 small。

## Cookies

部分视频的 AI 字幕需要登录态。用浏览器登录 B站后，导出 cookies 文件（JSON 数组格式或 Netscape 格式均可），在 `config.yaml` 的 `bilibili.cookies_path` 填入路径。

## Documentation

`docs/Features.md` 是产品功能与代码结构总览，`docs/ChangeLog.md` 记录每次验证通过后的改动，`docs/Plans.md` 记录待办与规划。

## License

MIT
