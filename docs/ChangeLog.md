# ChangeLog

记录每次「修改完成 + 用户验证通过」后的改动。

## 格式

每条记录含日期、摘要、改动点列表。最新记录在最上方。

```
### YYYY-MM-DD · 摘要
- 改动点1
- 改动点2
```

---

### 2026-06-24 · 精简为纯 ASR 路径
- 删除 fetcher/subtitle.py（B站 API 字幕、yt-dlp 备选字幕）
- 删除 cookies 相关逻辑（video_info.load_cookies、asr._ensure_netscape_cookies、--bilibili-sub 参数）
- asr.py 重命名入口函数 fetch_subtitle_via_asr → fetch_subtitle，代码分段加注释
- 精简 cli.py：字幕获取直走 ASR，无分支
- 精简 config.yaml：移除 bilibili 配置段
- 同步更新 Features.md、ChangeLog.md、README.md

### 2026-06-24 · 分 P 下载修复 + LLM 自动重试
- 修复合集分 P 视频音频下载：`_download_audio` URL 遗漏 `?p=N` 导致 yt-dlp 始终下载 p=1；VideoInfo 新增 page 字段，文件名区分分 P
- LLM 客户端新增自动重试：瞬时错误（RemoteProtocolError、ReadTimeout、ConnectError）最多重试 3 次，指数退避 2/4/8s

### 2026-06-23 · 字幕默认 ASR + 进度条优化
- 字幕获取默认改为 ASR（whisper 转录），原 `--asr` 改为 `--bilibili-sub` 使用 B站 API 字幕
- 字幕校对与笔记生成添加进度条（████░░░░ 样式），LLM 调用期间显示当前段落进度
- ASR 下载/转录添加进度提示；whisper 模型下载接管为干净百分比进度，SHA256 校验防止损坏缓存触发 tqdm 刷屏
- 音频下载中断/失败时自动清理残留文件（.part、.ytdl 等）
- 修复 httpx SOCKS 代理兼容性（socksio），requirements.txt 补全依赖

### 2026-06-23 · LLM 字幕校对与分段策略调整
- 新增 generator/subtitle_refiner.py：LLM 逐段校对 ASR 字幕（纠错+繁简转换+加标点），输出 .refined.txt 优化字幕文件
- note_writer.py 新增 generate_from_texts()：基于预处理后文本生成笔记
- cli.py API 模式增加预处理步骤：先校对字幕再生成笔记
- 分段策略调整：默认每段 10 分钟（原 6 分钟），不分视频长短统一分段
- 真实长视频验证：88 分钟操作系统课程，ASR 转录 7 分 33 秒（whisper small），笔记 6802 字

### 2026-06-23 · ASR 兜底实现与 token 统计
- 新增 fetcher/asr.py：B站字幕不可用时，用 yt-dlp 下载音频 + openai-whisper 转录生成字幕
- asr.py 支持 JSON cookies 自动转 Netscape 格式（yt-dlp 要求），音频已下载则复用
- cli.py 新增 --asr 参数强制走 ASR，B站字幕失败时自动降级 ASR
- llm_client.py 新增 token 用量统计（get_usage），cli.py API 模式输出 token 统计
- config.yaml 新增 subtitle.asr_model 配置（默认 small）
- 已知限制：B站部分视频 AI 字幕内容错误（跨视频关联 bug），ASR 是唯一兜底

### 2026-06-23 · 字幕获取方案调整与真实联调
- 字幕获取层改为 B站 player/v2 API 为主（CC 优先 → AI 兜底），yt-dlp 备选；原因：yt-dlp 被 B站 412 反爬
- video_info.py 新增合集分 P 支持（?p=N 参数提取对应 cid 与标题）
- load_cookies 支持 JSON 数组格式（兼容 Netscape 格式）
- subtitle.py 修复：CC/AI 判断改用 lan 字段（ai- 前缀区分），字幕下载加重试机制应对 auth_key 偶发失效
- processor 合并逻辑优化：加时间跨度和文本长度限制，避免无标点 AI 字幕无限合并
- config.yaml 配置 cookies_path 指向 bilibili_cookies.json
- 真实视频联调通过：BV1hU4y1M7NA?p=3（Qt Creator 教程），端到端字幕获取+预处理+笔记生成

### 2026-06-23 · 初始工程搭建
- 创建工程目录结构与包骨架
- 初始化 docs/ 三文档（Features.md、ChangeLog.md、Plans.md）
- 配置文件 config.yaml（双模式：agent 模式与 API 模式）
- 一键安装脚本 setup.sh
- 笔记结构模板 templates/note_structure.md
- 实现各层模块（fetcher / processor / generator / output / cli）
