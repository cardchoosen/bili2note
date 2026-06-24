"""输出层：将所有产物写入 notes/ 目录，每视频一个独立文件夹。

结构：
  单集视频:  notes/{标题}/note.md  original.srt  refined.txt
  合集视频:  notes/{系列名}/{分集名}/note.md  original.srt  refined.txt
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from ..fetcher.video_info import VideoInfo, format_duration

_ILLEGAL = re.compile(r'[\\/:*?"<>|\n\r\t]')


def _safe_filename(title: str) -> str:
    name = _ILLEGAL.sub(" ", title).strip()
    return name or "note"


def _build_note_md(
    video_info: VideoInfo, subtitle_source: str, body: str
) -> str:
    """组装笔记 md：元信息头 + 正文。"""
    display_title = video_info.episode_title or video_info.title
    url = f"https://www.bilibili.com/video/{video_info.bvid}"
    if video_info.page > 1:
        url += f"?p={video_info.page}"
    header = (
        f"# {display_title}\n\n"
        f"> 原视频：{url}\n"
        f"> UP主：{video_info.up}"
        f" · 时长：{format_duration(video_info.duration)}\n"
        f"> 笔记生成：{date.today().isoformat()}"
        f" · 转写来源：{subtitle_source}\n\n"
    )
    return header + body.strip() + "\n"


def write_output(
    notes_dir: str,
    video_info: VideoInfo,
    subtitle_source: str,
    srt_path: str,
    refined_texts: list[str],
    note_body: str,
) -> str:
    """将所有产物写入视频专属文件夹，返回笔记 md 路径。

    产物：
      note.md       - 最终笔记
      original.srt  - 原始 ASR 字幕
      refined.txt   - LLM 校对后的字幕
    """
    # 构建输出目录: notes/{系列名}/{分集名}/ 或 notes/{标题}/
    out_dir = Path(notes_dir)
    if video_info.series_title:
        out_dir = out_dir / _safe_filename(video_info.series_title)
    dir_name = _safe_filename(video_info.episode_title or video_info.title)
    out_dir = out_dir / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. 复制原始字幕
    srt_dest = out_dir / "original.srt"
    shutil.copy2(srt_path, srt_dest)

    # 2. 写入校对字幕
    refined_path = out_dir / "refined.txt"
    refined_path.write_text("\n\n===\n\n".join(refined_texts) + "\n", encoding="utf-8")

    # 3. 写入笔记
    note_path = out_dir / "note.md"
    note_path.write_text(
        _build_note_md(video_info, subtitle_source, note_body), encoding="utf-8"
    )

    return str(note_path)
