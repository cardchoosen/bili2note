# B站课程视频转学习笔记 Agent

输入一个 B 站视频 URL，生成一篇"学长博客风"的 Markdown 学习笔记，只读笔记即可替代看视频学习。

## 安装

```bash
bash setup.sh
```

需要 Python 3.10+ 和 yt-dlp（脚本会自动安装 yt-dlp）。

## 使用

### agent 模式（默认，零配置）

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

CLI 抓取字幕并预处理，输出结构化字幕文件到 notes/ 目录。将字幕文件交给 WorkBuddy agent，由其生成最终笔记 md。

### API 模式（全自动）

在 config.yaml 填入 llm 配置（base_url / api_key / model）后：

```bash
python -m bilibili_note "https://www.bilibili.com/video/BVxxxxx"
```

CLI 端到端全自动生成笔记 md。

## 配置

见 config.yaml。主要配置项：

llm：OpenAI 兼容接口，留空走 agent 模式，填入后走 API 模式。

bilibili.cookies_path：登录视频需要 cookies（Netscape 格式）。

subtitle.preferred_langs：字幕语言优先级。

## cookies 获取

部分视频需要登录态。用浏览器登录 B 站后，用扩展（如 Get cookies.txt）导出 Netscape 格式 cookies 文件，在 config.yaml 的 bilibili.cookies_path 填入路径。

## 文档

docs/Features.md 产品功能与代码结构总览。

docs/ChangeLog.md 每次验证通过后的修改记录。

docs/Plans.md 待办事项与规划。
