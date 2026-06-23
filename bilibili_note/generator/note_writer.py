"""笔记组装层。

负责分段生成、衔接合并，产出完整笔记正文（不含元信息头）。
"""

from __future__ import annotations

import sys

from ..fetcher.video_info import VideoInfo
from ..processor.subtitle_cleaner import SubtitleSegment, format_segment_for_prompt
from .llm_client import LLMClient
from .prompt import (
    SYSTEM_PROMPT,
    SUMMARY_PROMPT,
    build_full_prompt,
    build_segment_prompt,
)


def _progress_bar(current: int, total: int, width: int = 24) -> str:
    filled = round(current / total * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


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
        total = len(segments)
        for i, seg in enumerate(segments):
            seg_text = format_segment_for_prompt(seg)
            bar = _progress_bar(i + 1, total)
            print(
                f"\r[bilibili-note] 生成笔记  {bar} {i+1}/{total}",
                file=sys.stderr, end="", flush=True,
            )
            user_prompt = build_segment_prompt(
                seg_text, i + 1, total, prev_summary, video_info
            )
            note_part = self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()
            parts.append(note_part)
            if i < total - 1:
                print(file=sys.stderr)
                print(
                    f"\r[bilibili-note] 生成摘要  {bar} {i+1}/{total}",
                    file=sys.stderr, end="", flush=True,
                )
                prev_summary = self._summarize(note_part)
        print(file=sys.stderr)
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
        total = len(texts)
        for i, text in enumerate(texts):
            bar = _progress_bar(i + 1, total)
            print(
                f"\r[bilibili-note] 生成笔记  {bar} {i+1}/{total}",
                file=sys.stderr, end="", flush=True,
            )
            user_prompt = build_segment_prompt(
                text, i + 1, total, prev_summary, video_info
            )
            note_part = self.llm.chat(SYSTEM_PROMPT, user_prompt).strip()
            parts.append(note_part)
            if i < total - 1:
                print(file=sys.stderr)
                print(
                    f"\r[bilibili-note] 生成摘要  {bar} {i+1}/{total}",
                    file=sys.stderr, end="", flush=True,
                )
                prev_summary = self._summarize(note_part)
        print(file=sys.stderr)
        return "\n\n".join(parts)

    def _summarize(self, note_text: str) -> str:
        """让 LLM 生成笔记摘要，用于下一段衔接。"""
        return self.llm.chat(SUMMARY_PROMPT, note_text, temperature=0.3).strip()
