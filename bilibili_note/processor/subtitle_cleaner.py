"""字幕预处理层。

解析 SRT/VTT 字幕文件，清洗语气词，合并碎片句，按时长分段并保留时间戳。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SubtitleCue:
    """单条字幕：起止时间与文本。"""
    start: float  # 秒
    end: float    # 秒
    text: str


@dataclass
class SubtitleSegment:
    """字幕分段：一批连续 cue 组成一个生成单元。"""
    start: float
    end: float
    cues: list[SubtitleCue] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.cues)


# 语气词：连续的嗯/啊/呃/哦/哈
_FILLER = re.compile(r"(嗯+|啊+|呃+|哦+|哈+)\s*")
# 句末标点
_SENTENCE_END = re.compile(r"[。！？!?…\.]\s*$")
# 时间戳：兼容 SRT(,) 和 VTT(.)，小时位可选
_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})")


def _ts_to_sec(g: tuple) -> float:
    h = int(g[0]) if g[0] else 0
    return h * 3600 + int(g[1]) * 60 + int(g[2]) + int(g[3]) / 1000


def parse_subtitle(file_path: str) -> list[SubtitleCue]:
    """解析 SRT 或 VTT 字幕文件为 cue 列表。同时兼容两种格式。"""
    raw = Path(file_path).read_text(encoding="utf-8-sig")
    cues: list[SubtitleCue] = []
    for block in re.split(r"\n\s*\n", raw):
        block = block.strip()
        if not block or block.startswith("WEBVTT") or block.startswith("NOTE"):
            continue
        ts_line = None
        text_lines: list[str] = []
        for line in block.splitlines():
            line = line.strip()
            if "-->" in line:
                ts_line = line
            elif line and not line.isdigit():
                text_lines.append(line)
        if not ts_line:
            continue
        times = _TS.findall(ts_line)
        if len(times) < 2:
            continue
        start = _ts_to_sec(times[0])
        end = _ts_to_sec(times[1])
        text = "".join(text_lines).strip()
        if text:
            cues.append(SubtitleCue(start, end, text))
    return cues


def _remove_filler(text: str) -> str:
    return _FILLER.sub("", text)


def _ends_with_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.strip()))


def clean_cues(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    """去语气词，合并相邻碎片句为完整句（保留时间范围）。

    合并条件：间隔短 + 未到句末 + 文本不超长 + 时间跨度有限。
    B站 AI 字幕无标点，靠时间跨度和文本长度兜底断开。
    """
    for c in cues:
        c.text = _remove_filler(c.text).strip()

    merged: list[SubtitleCue] = []
    buf: SubtitleCue | None = None
    for c in cues:
        if not c.text:
            continue
        if buf is None:
            buf = SubtitleCue(c.start, c.end, c.text)
            continue
        gap = c.start - buf.end
        span = c.end - buf.start
        if (
            gap < 1.0
            and not _ends_with_sentence(buf.text)
            and len(buf.text) < 60
            and span < 20
        ):
            buf.end = c.end
            buf.text += c.text
        else:
            merged.append(buf)
            buf = SubtitleCue(c.start, c.end, c.text)
    if buf:
        merged.append(buf)
    return merged


def segment_cues(
    cues: list[SubtitleCue], segment_seconds: int = 360
) -> list[SubtitleSegment]:
    """按时长把 cue 切成分段，默认每段约 6 分钟。"""
    if not cues:
        return []
    segments: list[SubtitleSegment] = []
    seg_start = cues[0].start
    seg_cues: list[SubtitleCue] = []
    for c in cues:
        seg_cues.append(c)
        if c.end - seg_start >= segment_seconds:
            segments.append(SubtitleSegment(seg_start, c.end, seg_cues))
            seg_cues = []
            seg_start = c.end
    if seg_cues:
        segments.append(SubtitleSegment(seg_start, seg_cues[-1].end, seg_cues))
    return segments


def format_segment_for_prompt(seg: SubtitleSegment) -> str:
    """把分段格式化为带时间戳的文本，供 LLM prompt 使用。"""
    lines: list[str] = []
    for c in seg.cues:
        mm, ss = divmod(int(c.start), 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {c.text}")
    return "\n".join(lines)


def process_subtitle(
    file_path: str, segment_seconds: int = 360
) -> tuple[list[SubtitleCue], list[SubtitleSegment]]:
    """端到端处理：解析 → 清洗 → 分段。

    Returns:
        (清洗后的 cue 列表, 分段列表)
    """
    cues = parse_subtitle(file_path)
    cues = clean_cues(cues)
    segments = segment_cues(cues, segment_seconds)
    return cues, segments
