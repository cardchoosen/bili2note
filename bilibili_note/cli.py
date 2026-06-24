"""CLI 入口：抓取元信息 → ASR 转录 → 字幕预处理 → LLM 校对/生成 → 输出。

双模式：
  agent 模式（默认，零配置）：仅完成字幕获取与预处理，输出字幕 JSON 文件，
      由外部 agent 接力生成笔记。
  API 模式（config.yaml 填入 llm 配置后启用）：端到端全自动生成笔记。

产物统一输出到 notes/{标题}/ 文件夹，包含 note.md、original.srt、refined.txt。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .fetcher.asr import fetch_subtitle
from .fetcher.video_info import fetch_video_info, format_duration
from .generator.llm_client import LLMClient, is_api_configured
from .generator.note_writer import NoteWriter
from .generator.subtitle_refiner import SubtitleRefiner
from .log import info
from .output.markdown import write_output
from .processor.subtitle_cleaner import format_segment_for_prompt, process_subtitle


def _default_config_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "config.yaml")


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_output_dir(notes_dir: str, video_info) -> Path:
    """构建输出目录路径。合集: notes/系列名/分集名/, 单集: notes/标题/。"""
    import re
    _illegal = re.compile(r'[\\/:*?"<>|\n\r\t]')

    def safe(name: str) -> str:
        return _illegal.sub(" ", name).strip()

    out = Path(notes_dir)
    if video_info.series_title:
        out = out / safe(video_info.series_title)
    dir_name = safe(video_info.episode_title or video_info.title)
    return out / dir_name


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bilibili_note",
        description="B站视频转学长博客风学习笔记",
    )
    parser.add_argument("url", help="B站视频 URL 或 BV 号")
    parser.add_argument(
        "-c", "--config", default=_default_config_path(), help="配置文件路径"
    )
    parser.add_argument(
        "--segment-seconds",
        type=int,
        default=0,
        help="字幕分段时长（秒），0 表示默认 10 分钟",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    sub_cfg = config.get("subtitle", {})
    out_cfg = config.get("output", {})

    # 1. 视频元信息
    info("抓取视频元信息...")
    video_info = fetch_video_info(args.url)
    info(
        f"《{video_info.title}》 UP主:{video_info.up} "
        f"时长:{format_duration(video_info.duration)}"
    )

    # 2. ASR 转录字幕
    info("ASR 转录：下载音频 + whisper 转录...")
    sub_path, sub_source = fetch_subtitle(
        video_info,
        work_dir=sub_cfg.get("work_dir", ".cache"),
        model_name=sub_cfg.get("asr_model", "small"),
    )
    info(f"字幕来源：{sub_source}")

    # 3. 字幕预处理
    info("预处理字幕...")
    seg_seconds = args.segment_seconds if args.segment_seconds > 0 else 600
    cues, segments = process_subtitle(sub_path, seg_seconds)
    info(f"字幕 {len(cues)} 条，分为 {len(segments)} 段")

    notes_dir = out_cfg.get("notes_dir", "notes")

    # 4. 笔记生成
    if is_api_configured(config):
        llm = LLMClient.from_config(config)

        # 4a. LLM 校对字幕
        info("API 模式：LLM 校对字幕（纠错+简繁转换）...")
        refiner = SubtitleRefiner(llm)
        refined_texts = refiner.refine(segments, video_info)

        # 4b. 生成笔记
        info("API 模式：调用 LLM 生成笔记...")
        writer = NoteWriter(llm)
        body = writer.generate_from_texts(refined_texts, video_info)
        usage = llm.get_usage()
        info(
            f"token 统计: 输入 {usage['prompt_tokens']} + "
            f"输出 {usage['completion_tokens']} = "
            f"总计 {usage['total_tokens']}"
        )

        # 4c. 输出所有产物到视频文件夹
        note_path = write_output(
            notes_dir, video_info, sub_source,
            srt_path=sub_path,
            refined_texts=refined_texts,
            note_body=body,
        )
        info(f"笔记已生成：file://{Path(note_path).resolve()}")
    else:
        # agent 模式：输出字幕 JSON 到视频文件夹
        out_dir = _build_output_dir(notes_dir, video_info)
        out_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "video": video_info.to_dict(),
            "subtitle_source": sub_source,
            "segments": [
                {
                    "index": i + 1,
                    "start": s.start,
                    "end": s.end,
                    "text": format_segment_for_prompt(s),
                }
                for i, s in enumerate(segments)
            ],
        }
        json_path = out_dir / "subtitles.json"
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        info(f"字幕文件已输出：{json_path}")
        info("请将此文件内容提供给外部 agent：先预处理纠错，再生成笔记")


if __name__ == "__main__":
    main()
