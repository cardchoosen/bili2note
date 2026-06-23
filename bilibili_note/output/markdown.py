"""Markdown 输出层。

组装元信息头与笔记正文，写入 notes/ 目录。
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..fetcher.video_info import VideoInfo, format_duration

_ILLEGAL = re.compile(r'[\\/:*?"<>|\n\r\t]')


def _safe_filename(title: str) -> str:
    name = _ILLEGAL.sub(" ", title).strip()
    return name or "note"


def build_note_markdown(
    video_info: VideoInfo, subtitle_source: str, body: str
) -> str:
    """组装完整笔记 md：元信息头 + 正文。"""
    header = (
        f"# {video_info.title}\n\n"
        f"> 原视频：https://www.bilibili.com/video/{video_info.bvid}\n"
        f"> UP主：{video_info.up} · 时长：{format_duration(video_info.duration)}\n"
        f"> 笔记生成：{date.today().isoformat()} · 转写来源：{subtitle_source}\n\n"
    )
    return header + body.strip() + "\n"


def write_note(
    notes_dir: str,
    video_info: VideoInfo,
    subtitle_source: str,
    body: str,
) -> str:
    """写入笔记 md 文件，返回文件路径。"""
    out_dir = Path(notes_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(video_info.title) + ".md"
    path = out_dir / filename
    path.write_text(
        build_note_markdown(video_info, subtitle_source, body), encoding="utf-8"
    )
    return str(path)
