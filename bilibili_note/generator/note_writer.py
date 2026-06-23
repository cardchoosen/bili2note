"""笔记组装层。

负责分段生成、衔接合并，产出完整笔记正文（不含元信息头）。
"""

from __future__ import annotations

from ..fetcher.video_info import VideoInfo
from ..processor.subtitle_cleaner import SubtitleSegment, format_segment_for_prompt
from .llm_client import LLMClient
from .prompt import (
    SYSTEM_PROMPT,
    SUMMARY_PROMPT,
    build_full_prompt,
    build_segment_prompt,
)


class NoteWriter:
    """根据字幕分段生成笔记，长视频分段生成后合并。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(
        self, segments: list[SubtitleSegment], video_info: VideoInfo
    ) -> str:
        """生成完整笔记正文（不含元信息头）。

        单段直接生成；多段逐段生成，每段后产出摘要供下一段衔接。
        """
        if len(segments) <= 1:
            seg_text = (
                format_segment_for_prompt(segments[0]) if segments else ""
            )
            user_prompt = build_full_prompt(seg_text, video_info)
            return self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()

        parts: list[str] = []
        prev_summary = ""
        for i, seg in enumerate(segments):
            seg_text = format_segment_for_prompt(seg)
            user_prompt = build_segment_prompt(
                seg_text, i + 1, len(segments), prev_summary, video_info
            )
            note_part = self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()
            parts.append(note_part)
            prev_summary = self._summarize(note_part)
        return "\n\n".join(parts)

    def generate_from_texts(
        self, texts: list[str], video_info: VideoInfo
    ) -> str:
        """用预处理后的文本列表生成笔记（文本已校对，无需再从 segment 提取）。

        单段直接生成；多段逐段生成，每段后产出摘要供下一段衔接。
        """
        if len(texts) <= 1:
            seg_text = texts[0] if texts else ""
            user_prompt = build_full_prompt(seg_text, video_info)
            return self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()

        parts: list[str] = []
        prev_summary = ""
        for i, text in enumerate(texts):
            user_prompt = build_segment_prompt(
                text, i + 1, len(texts), prev_summary, video_info
            )
            note_part = self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()
            parts.append(note_part)
            prev_summary = self._summarize(note_part)
        return "\n\n".join(parts)

    def _summarize(self, note_text: str) -> str:
        """让 LLM 生成笔记摘要，用于下一段衔接。"""
        return self.llm.chat(SUMMARY_PROMPT, note_text, temperature=0.3).strip()
