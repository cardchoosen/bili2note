# Features

B站课程视频转学习笔记 Agent 的功能与代码结构总览。

## 功能

输入一个 B 站视频 URL，端到端生成一篇 Markdown 学习笔记。笔记采用"学长博客风"：专业段落叙述为主，禁用 emoji 与分点罗列，信息完整度对齐原视频，只读笔记即可替代看视频学习。

视频元信息抓取：通过 B 站 view API 获取标题、UP 主、时长、简介、cid。

字幕获取：默认走 ASR 转录（yt-dlp 下载音频 + whisper），质量更可靠。也可通过 --bilibili-sub 使用 B站 player/v2 API 字幕（CC 优先、AI 兜底），yt-dlp 备选，支持 cookies 登录态。

字幕预处理：清洗语气词、合并碎片句、按主题分段、保留时间戳。ASR 字幕额外经过 LLM 校对（subtitle_refiner）：修正识别错误、繁体转简体、添加标点，输出优化字幕文件。字幕校对和笔记生成均有进度条展示。

笔记生成：学长博客风 prompt 驱动 LLM，基于优化后字幕生成，长视频分段生成后合并。文风铁律内嵌于 prompt：禁 emoji、禁"老师"人称、禁分点罗列、禁 AI 套路话术、段落叙述为主。

双模式运行：agent 模式（零配置，WorkBuddy agent 接力生成）与 API 模式（填配置全自动）。

字幕分段：默认每段 10 分钟，可通过 --segment-seconds 参数调整。长视频分段生成后合并。

token 统计：API 模式下累计 LLM 调用的 prompt/completion/total token，生成完毕后输出。

## 代码结构

```
bilibili_note/
  cli.py                 CLI 入口，端到端串联
  fetcher/
    video_info.py        B 站 API 元信息抓取
    subtitle.py          B站 API 字幕获取为主，yt-dlp 备选（CC 优先 → AI 兜底）
    asr.py               ASR 兜底（yt-dlp 下载音频 + whisper 转录）
  processor/
    subtitle_cleaner.py  字幕清洗、合并、分段、时间戳对齐
  generator/
    prompt.py            学长博客风 prompt 模板（文风铁律）
    subtitle_refiner.py  LLM 字幕校对（纠错+简繁转换+加标点）
    llm_client.py        OpenAI 兼容 LLM 客户端 + token 统计
    note_writer.py       分段生成与笔记组装（支持预处理文本输入）
  output/
    markdown.py          md 文件写入
docs/                    Features.md / ChangeLog.md / Plans.md
notes/                   生成的笔记输出目录
templates/               note_structure.md 笔记结构模板
config.yaml              配置文件
setup.sh                 一键安装脚本
```

## 模块职责

fetcher/video_info 输入 B 站 URL，输出 {title, up 主, 时长, 简介, cid, 封面}，依赖 httpx + B 站 API。

fetcher/subtitle 输入 video_info，输出字幕文件路径与来源标记，通过 B站 API 获取（--bilibili-sub 启用）。

fetcher/asr 输入 video_info，输出 SRT 字幕文件，默认字幕来源，依赖 yt-dlp 下载音频 + whisper 转录。

processor/subtitle_cleaner 输入字幕文件，按 10 分钟分段输出结构化段落列表，无外部依赖。

generator/prompt 输入视频元信息与字幕段落，输出学长博客风 prompt，纯模板。

generator/subtitle_refiner 输入分段字幕，逐段 LLM 校对输出优化文本，依赖 llm_client。

generator/llm_client 输入 prompt，输出 LLM 生成文本，累计 token 用量，依赖 OpenAI 兼容接口。

generator/note_writer 输入字幕段或预处理文本，输出完整笔记 md 文本，依赖 llm_client。

output/markdown 输入笔记文本与元信息，写入 notes/{标题}.md。
