"""CLI 入口，端到端串联 fetcher → processor → generator → output。

双模式：
  agent 模式（默认，零配置）：抓取字幕+预处理，输出结构化字幕 JSON，由 WorkBuddy agent 接力生成笔记。
  API 模式（config.yaml 填入 llm 配置后启用）：端到端全自动生成笔记 md。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .fetcher.subtitle import fetch_subtitle
from .fetcher.video_info import fetch_video_info, format_duration
from .generator.llm_client import LLMClient, is_api_configured
from .generator.note_writer import NoteWriter
from .generator.subtitle_refiner import SubtitleRefiner, write_refined_subtitle
from .output.markdown import write_note
from .processor.subtitle_cleaner import format_segment_for_prompt, process_subtitle


def _default_config_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "config.yaml")


def _log(msg: str) -> None:
    print(f"[bilibili-note] {msg}", file=sys.stderr)


def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_subtitles_json(
    notes_dir: str, video_info, subtitle_source: str, segments
) -> str:
    """agent 模式：输出结构化字幕 JSON 供 WorkBuddy agent 接力。"""
    out_dir = Path(notes_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "video": video_info.to_dict(),
        "subtitle_source": subtitle_source,
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
    path = out_dir / f"{video_info.title}.subtitles.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


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
        help="字幕分段时长（秒），0 表示按视频时长自动决定",
    )
    parser.add_argument(
        "--bilibili-sub",
        action="store_true",
        help="优先使用 B站 API 字幕（默认走 ASR whisper 转录）",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    bili_cfg = config.get("bilibili", {})
    sub_cfg = config.get("subtitle", {})
    out_cfg = config.get("output", {})
    cookies_path = bili_cfg.get("cookies_path", "")

    # 1. 视频元信息
    _log("抓取视频元信息...")
    video_info = fetch_video_info(args.url, cookies_path)
    _log(
        f"《{video_info.title}》 UP主:{video_info.up} "
        f"时长:{format_duration(video_info.duration)}"
    )

    # 2. 字幕获取
    from .fetcher.asr import fetch_subtitle_via_asr

    if args.bilibili_sub:
        _log("获取 B站字幕...")
        try:
            sub_path, sub_source = fetch_subtitle(
                video_info,
                sub_cfg.get("preferred_langs", ["zh-Hans", "zh-CN", "ai-zh"]),
                sub_cfg.get("work_dir", ".cache"),
                cookies_path,
            )
        except RuntimeError as e:
            _log(f"B站字幕不可用: {e}")
            _log("降级到 ASR 转录...")
            sub_path, sub_source = fetch_subtitle_via_asr(
                video_info,
                sub_cfg.get("work_dir", ".cache"),
                cookies_path,
                sub_cfg.get("asr_model", "small"),
            )
    else:
        _log("ASR 模式：下载音频 + whisper 转录...")
        sub_path, sub_source = fetch_subtitle_via_asr(
            video_info,
            sub_cfg.get("work_dir", ".cache"),
            cookies_path,
            sub_cfg.get("asr_model", "small"),
        )
    _log(f"字幕来源：{sub_source}")

    # 3. 字幕预处理
    _log("预处理字幕...")
    seg_seconds = args.segment_seconds
    if seg_seconds <= 0:
        # 默认每段 10 分钟
        seg_seconds = 600
    cues, segments = process_subtitle(sub_path, seg_seconds)
    _log(f"字幕 {len(cues)} 条，分为 {len(segments)} 段")

    notes_dir = out_cfg.get("notes_dir", "notes")

    # 4. 笔记生成
    if is_api_configured(config):
        llm = LLMClient.from_config(config)

        # 4a. LLM 预处理字幕（纠错+简繁转换+加标点）
        _log("API 模式：LLM 预处理字幕（纠错+简繁转换）...")
        refiner = SubtitleRefiner(llm)
        refined_texts = refiner.refine(segments, video_info)
        work_dir = sub_cfg.get("work_dir", ".cache")
        refined_path = write_refined_subtitle(
            refined_texts, f"{work_dir}/{video_info.bvid}.refined.txt"
        )
        _log(f"优化字幕已输出：{refined_path}")

        # 4b. 生成笔记
        _log("API 模式：调用 LLM 生成笔记...")
        writer = NoteWriter(llm)
        body = writer.generate_from_texts(refined_texts, video_info)
        usage = llm.get_usage()
        _log(
            f"token 统计: 输入 {usage['prompt_tokens']} + "
            f"输出 {usage['completion_tokens']} = "
            f"总计 {usage['total_tokens']}"
        )
        path = write_note(notes_dir, video_info, sub_source, body)
        _log(f"笔记已生成：{path}")
    else:
        _log("agent 模式：输出结构化字幕文件，交由 WorkBuddy agent 生成笔记")
        path = _write_subtitles_json(notes_dir, video_info, sub_source, segments)
        _log(f"字幕文件已输出：{path}")
        _log("请将此文件内容提供给 WorkBuddy agent：先预处理纠错，再生成笔记")


if __name__ == "__main__":
    main()
