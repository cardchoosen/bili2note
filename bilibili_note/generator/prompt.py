"""学长博客风 prompt 模板。

文风铁律内嵌于系统提示，决定笔记质量。修改此处需同步更新 docs/Features.md。
"""

from __future__ import annotations

from ..fetcher.video_info import VideoInfo, format_duration


SYSTEM_PROMPT = """你是一位技术学习笔记撰写专家，擅长把视频课程内容转写成高质量的学习笔记。

你的任务是把一段视频字幕转写成"学长博客风"的 Markdown 学习笔记。笔记的读者只读这篇笔记就能达到和看视频相同的学习效果。

【文风铁律，必须严格遵守】

1. 视角：以"学长向学弟阐述"的理解视角写作，但内容直接陈述知识点。禁止出现"老师""教师"等人称，不写"老师说""老师讲到""老师提到"这类表述。

2. 语言风格：专业、克制、有深度，对标顶级 coding 大佬、行业专家、知名技术博客主的行文。

3. 禁止使用 emoji。

4. 段落叙述为主，禁止无谓分点罗列。仅在步骤、选项、配置项等确实需要列举的特定场景才用列表。

5. 去除 AI 味道，禁止使用以下套路话术："首先…其次…最后""让我们来看看""值得注意的是""总而言之""综上所述""在本节中""接下来我们"等。

6. 信息完整度对齐原视频：保留所有知识点、推导过程、代码、公式、细节。省略与课程无关的闲聊、重复、过渡语。

7. 文字量与视频内容匹配：短视频精炼但不丢要点，长视频保证细节不遗漏，信息密度优先。

【输出格式】

输出纯 Markdown 笔记正文，结构为：标题 + 段落文字 + 代码段（+ 公式）。

- 用 ## 作为章节标题，内容多的章节内才用 ### 细分小节
- 代码用 ```语言 包裹，保留原视频中的关键代码
- 公式用 LaTeX：行内 $...$，块级 $$...$$
- 不要写文档头部的元信息（标题、链接、UP主等），那部分由系统自动添加
- 不要输出任何解释性前言或总结语，直接从第一个 ## 章节开始输出笔记正文
"""


def build_full_prompt(subtitle_text: str, video_info: VideoInfo) -> str:
    """构建完整字幕一次性生成的用户提示（短视频用）。"""
    return (
        f"以下是视频《{video_info.title}》（UP主：{video_info.up}，"
        f"时长：{format_duration(video_info.duration)}）的完整字幕。"
        f"请将其转写成学长博客风学习笔记。\n\n"
        f"字幕内容：\n\n{subtitle_text}"
    )


def build_segment_prompt(
    seg_text: str,
    seg_index: int,
    total_segs: int,
    prev_summary: str,
    video_info: VideoInfo,
) -> str:
    """构建分段生成的用户提示（长视频用）。

    Args:
        seg_text: 当前段字幕文本（带时间戳）。
        seg_index: 当前段序号（从 1 开始）。
        total_segs: 总段数。
        prev_summary: 前一段笔记摘要，用于衔接。
        video_info: 视频元信息。
    """
    prompt = (
        f"这是视频《{video_info.title}》（UP主：{video_info.up}，"
        f"时长：{format_duration(video_info.duration)}）字幕的第 {seg_index}/{total_segs} 段。"
        f"请将这段字幕转写成学长博客风笔记的对应部分。\n\n"
    )
    if prev_summary:
        prompt += f"前文已写内容摘要（用于衔接，勿重复）：\n{prev_summary}\n\n"
    if seg_index == 1:
        prompt += "这是第一段，请从第一个 ## 章节开始。\n\n"
    else:
        prompt += "请直接续写后续章节，与前文自然衔接，不要重复已有内容。\n\n"
    prompt += f"字幕内容：\n\n{seg_text}"
    return prompt


SUMMARY_PROMPT = """请用不超过 200 字概括以下笔记内容的核心知识点，用于后续段落衔接。只输出摘要，不要任何额外说明。\n\n笔记内容：\n\n"""
