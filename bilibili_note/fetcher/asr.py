"""ASR 字幕兜底层。

当 B站字幕不可用时，用 yt-dlp 下载音频 + openai-whisper 转录生成字幕。
whisper 在函数内延迟 import，未安装时不影响其他功能。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .video_info import VideoInfo


def _ensure_netscape_cookies(cookies_path: str) -> str:
    """JSON 格式 cookies 转 Netscape 格式（yt-dlp 需要），返回文件路径。"""
    if not cookies_path or not cookies_path.endswith(".json"):
        return cookies_path
    p = Path(cookies_path)
    if not p.exists():
        return cookies_path
    import json

    arr = json.loads(p.read_text(encoding="utf-8"))
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in arr:
        domain = c.get("domain", "")
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        exp = int(c.get("expirationDate", 0)) if c.get("expirationDate") else 0
        lines.append(
            f"{domain}\t{flag}\t{path}\t{secure}\t{exp}\t"
            f"{c.get('name', '')}\t{c.get('value', '')}"
        )
    netscape_path = p.with_suffix(".txt")
    netscape_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(netscape_path)


def _download_audio(
    video_info: VideoInfo, work_dir: Path, cookies_path: str
) -> str:
    """用 yt-dlp 下载音频，返回音频文件路径。已有则复用。"""
    for p in sorted(work_dir.glob(f"{video_info.bvid}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)
    url = f"https://www.bilibili.com/video/{video_info.bvid}"
    output_template = str(work_dir / f"{video_info.bvid}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--no-progress",
        "--no-playlist",
        "-o", output_template,
    ]
    if cookies_path:
        netscape_path = _ensure_netscape_cookies(cookies_path)
        cmd += ["--cookies", netscape_path]
    cmd.append(url)
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    for p in sorted(work_dir.glob(f"{video_info.bvid}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)
    raise RuntimeError("音频下载失败，文件未找到")


def _seconds_to_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _transcribe(
    audio_path: str, work_dir: Path, bvid: str, model_name: str
) -> str:
    """用 whisper 转录音频，输出 SRT 文件。"""
    import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path, language="zh", task="transcribe")

    srt_path = work_dir / f"{bvid}.asr.srt"
    blocks = []
    for i, seg in enumerate(result.get("segments", []), 1):
        start = _seconds_to_srt(seg["start"])
        end = _seconds_to_srt(seg["end"])
        text = seg["text"].strip()
        if text:
            blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    srt_path.write_text("\n".join(blocks), encoding="utf-8")
    return str(srt_path)


def fetch_subtitle_via_asr(
    video_info: VideoInfo,
    work_dir: str,
    cookies_path: str = "",
    model_name: str = "small",
) -> tuple[str, str]:
    """ASR 兜底：下载音频 + whisper 转录。

    Args:
        video_info: 视频元信息。
        work_dir: 工作目录（音频和字幕临时文件）。
        cookies_path: cookies 文件路径。
        model_name: whisper 模型名（tiny/base/small/medium/large）。

    Returns:
        (srt文件路径, "ASR转录")
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    audio_path = _download_audio(video_info, work, cookies_path)
    srt_path = _transcribe(audio_path, work, video_info.bvid, model_name)
    return srt_path, "ASR转录"
