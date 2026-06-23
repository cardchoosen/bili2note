# bili2note

Turn online course videos into well-structured markdown notes that capture every key point — so you can read instead of watch.

## Features

- 输入 B站视频 URL，端到端生成 Markdown 学习笔记，信息完整度对齐原视频
- 字幕获取：B站 API 优先（CC 字幕 → AI 字幕），不可用时自动降级 ASR 转录（whisper）
- LLM 字幕校对：修正 ASR 识别错误、繁简转换、添加标点
- 笔记文风：专业段落叙述，无 emoji，无分点罗列，去 AI 套路话术
- 长视频支持：按 10 分钟分段处理，逐段生成后合并
- 双模式：agent 模式（零配置）与 API 模式（填 LLM 配置全自动）
- token 统计：API 模式下输出完整 token 用量

## Installation

```bash
bash setup.sh
```

Requires Python 3.10+, yt-dlp and ffmpeg（脚本自动安装 yt-dlp）。

## Usage

### Agent Mode (default, zero config)

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

CLI 抓取字幕并预处理，输出结构化字幕文件到 notes/。将字幕文件交给 AI agent 生成最终笔记。

### API Mode (fully automated)

Fill in LLM config in config.yaml (base_url / api_key / model), then:

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

CLI 端到端全自动：字幕获取 → LLM 校对 → 笔记生成 → 输出 md。

### Force ASR

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx" --asr
```

跳过 B站字幕，直接下载音频用 whisper 转录。适用于字幕不可用或质量差的视频。

## Configuration

See `config.yaml`:

| Config | Description |
|---|---|
| `llm` | OpenAI 兼容接口，留空走 agent 模式，填入后走 API 模式 |
| `bilibili.cookies_path` | cookies 文件路径（JSON 或 Netscape 格式），AI 字幕需要登录态 |
| `subtitle.preferred_langs` | 字幕语言优先级 |
| `subtitle.asr_model` | whisper 模型（tiny/base/small/medium/large），默认 small |

## Cookies

部分视频的 AI 字幕需要登录态。用浏览器登录 B站后，导出 cookies 文件（JSON 数组格式或 Netscape 格式），在 `config.yaml` 的 `bilibili.cookies_path` 填入路径。

## Documentation

| File | Description |
|---|---|
| `docs/Features.md` | 产品功能与代码结构总览 |
| `docs/ChangeLog.md` | 修改记录 |
| `docs/Plans.md` | 待办与规划 |

## License

MIT
