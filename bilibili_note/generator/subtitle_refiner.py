"""字幕 LLM 预处理层。

在笔记生成前，用 LLM 对 ASR 转录的字幕做校对：
修正识别错误（术语错认、同音字）、繁体转简体、添加标点。
输出优化后的字幕文本，保留时间戳格式。
"""

from __future__ import annotations

from pathlib import Path

from ..fetcher.video_info import VideoInfo
from ..log import progress, progress_done
from ..processor.subtitle_cleaner import SubtitleSegment, format_segment_for_prompt
from .llm_client import LLMClient


REFINE_SYSTEM_PROMPT = """你是一位专业的字幕校对专家。你的任务是校对 ASR（语音识别）转录的字幕文本，修正识别错误。

校对规则：
1. 修正 ASR 识别错误：术语错认（如"匯邊"应为"汇编"、"含住"应为"函数"、"計存器"应为"寄存器"、"辨量"应为"变量"、"歪爾"应为"while"）、同音字错误等。基于上下文判断正确含义。
2. 繁体中文统一转为简体中文。
3. 适当添加标点（句号、逗号），使文本可读，但不改变原意。
4. 保留时间戳标记 [mm:ss] 的格式和位置，每条字幕独占一行。
5. 不增删内容，只做校对和格式优化，不添加任何解释或注释。
6. 直接输出校对后的字幕文本，保持 [mm:ss] 文本 的逐行格式。"""


def build_refine_prompt(seg_text: str, video_info: VideoInfo) -> str:
    """构建单段字幕校对的用户提示。"""
    return (
        f"以下是视频《{video_info.title}》（UP主：{video_info.up}）的一段 ASR 转录字幕。"
        f"请校对修正后直接输出，保持 [mm:ss] 文本 的逐行格式。\n\n"
        f"字幕内容：\n\n{seg_text}"
    )


class SubtitleRefiner:
    """用 LLM 对分段字幕做逐段校对。"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def refine(
        self, segments: list[SubtitleSegment], video_info: VideoInfo
    ) -> list[str]:
        """对每段字幕做 LLM 校对，返回优化后的文本列表（每段一个字符串）。

        Returns:
            优化后的文本列表，保留 [mm:ss] 时间戳格式。
        """
        refined: list[str] = []
        total = len(segments)
        for i, seg in enumerate(segments):
            bar = _progress_bar(i + 1, total)
            progress(f"校对字幕  {bar} {i+1}/{total}")
            seg_text = format_segment_for_prompt(seg)
            prompt = build_refine_prompt(seg_text, video_info)
            result = self.llm.chat(
                REFINE_SYSTEM_PROMPT, prompt, temperature=0.3
            ).strip()
            refined.append(result)
        progress_done(f"校对字幕  {_progress_bar(total, total)} {total}/{total}")
        return refined


def _progress_bar(current: int, total: int, width: int = 24) -> str:
    filled = round(current / total * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def write_refined_subtitle(
    texts: list[str], output_path: str
) -> str:
    """把优化后的字幕文本写入文件，返回路径。"""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n\n===\n\n".join(texts) + "\n", encoding="utf-8")
    return str(p)
