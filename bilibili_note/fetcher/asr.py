"""ASR 字幕兜底层。

当 B站字幕不可用时，用 yt-dlp 下载音频 + openai-whisper 转录生成字幕。
whisper 在函数内延迟 import，未安装时不影响其他功能。
"""

from __future__ import annotations

import os
import subprocess
import sys
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
    page = getattr(video_info, "page", 1)
    audio_prefix = f"{video_info.bvid}.p{page}" if page > 1 else video_info.bvid
    for p in sorted(work_dir.glob(f"{audio_prefix}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)
    print("[bilibili-note] 下载音频中，请耐心等待...", file=sys.stderr)
    url = f"https://www.bilibili.com/video/{video_info.bvid}"
    if page > 1:
        url += f"?p={page}"
    output_template = str(work_dir / f"{audio_prefix}.%(ext)s")
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
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (KeyboardInterrupt, subprocess.CalledProcessError):
        _cleanup_partial(work_dir, audio_prefix)
        raise
    print("[bilibili-note] 音频下载完成", file=sys.stderr)
    for p in sorted(work_dir.glob(f"{audio_prefix}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)
    _cleanup_partial(work_dir, audio_prefix)
    raise RuntimeError("音频下载失败，文件未找到")


def _cleanup_partial(work_dir: Path, bvid: str) -> None:
    """清理下载中断的残留文件（.part、.ytdl 等）。"""
    for p in sorted(work_dir.glob(f"{bvid}*")):
        if p.is_file():
            p.unlink(missing_ok=True)


def _seconds_to_srt(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# whisper 模型下载 URL
_MODEL_URLS = {
    "tiny.en": "https://openaipublic.azureedge.net/main/whisper/models/d3dd57d32accea0b295c96e26691aa14d8822fac7d9d27d5dc00b4ca2826dd03/tiny.en.pt",
    "tiny": "https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt",
    "base.en": "https://openaipublic.azureedge.net/main/whisper/models/25a8566e1d0c1e2231d1c762132cd20e0f96a85d16145c3a00adf5d1ac670ead/base.en.pt",
    "base": "https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt",
    "small.en": "https://openaipublic.azureedge.net/main/whisper/models/f953ad0fd29cacd07d5a9eda5624af0f6bcf2258be67c92b79389873d91e0872/small.en.pt",
    "small": "https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt",
    "medium.en": "https://openaipublic.azureedge.net/main/whisper/models/d7440d1dc186f76616474e0ff0b3b6b879abc9d1a4926b7adfa41db2d497ab4f/medium.en.pt",
    "medium": "https://openaipublic.azureedge.net/main/whisper/models/345ae4da62f9b3d59415adc60127b97c714f32e89e936602e85993674d08dcb1/medium.pt",
    "large": "https://openaipublic.azureedge.net/main/whisper/models/e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb/large-v3.pt",
    "large-v1": "https://openaipublic.azureedge.net/main/whisper/models/e4b87e7e0bf463eb8e6956e646f1e277e901512310def2c24bf0e11bd3c28e9a/large-v1.pt",
    "large-v2": "https://openaipublic.azureedge.net/main/whisper/models/81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a73e524/large-v2.pt",
    "large-v3": "https://openaipublic.azureedge.net/main/whisper/models/e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb/large-v3.pt",
    "turbo": "https://openaipublic.azureedge.net/main/whisper/models/aff26ae408abcba5fbf8813c21e62b0941638c5f6eebfb145be0c9839262a19a/large-v3-turbo.pt",
    "large-v3-turbo": "https://openaipublic.azureedge.net/main/whisper/models/aff26ae408abcba5fbf8813c21e62b0941638c5f6eebfb145be0c9839262a19a/large-v3-turbo.pt",
}


def _ensure_model(model_name: str) -> None:
    """确保 whisper 模型已缓存且 SHA256 正确，否则下载并显示干净进度。"""
    import hashlib
    import urllib.request

    url = _MODEL_URLS.get(model_name)
    if not url:
        return  # 未知模型，交给 whisper 自己处理

    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
    os.makedirs(cache_dir, exist_ok=True)
    model_path = os.path.join(cache_dir, f"{model_name}.pt")
    expected_hash = url.split("/")[-2]

    if os.path.exists(model_path) and os.path.getsize(model_path) > 0:
        sha = hashlib.sha256()
        with open(model_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
        if sha.hexdigest() == expected_hash:
            return  # 缓存有效，whisper 不会重复下载
        # 损坏文件，删掉重下
        os.unlink(model_path)

    print(f"[bilibili-note] 下载 whisper 模型 ({model_name}) ...",
          file=sys.stderr, end="", flush=True)

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            data = bytearray()
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                data.extend(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    print(f"\r[bilibili-note] 下载 whisper 模型 ({model_name}) "
                          f"{pct}%", file=sys.stderr, end="", flush=True)
        with open(model_path, "wb") as f:
            f.write(data)
        print(file=sys.stderr)  # 换行
    except Exception:
        print(file=sys.stderr)
        if os.path.exists(model_path):
            os.unlink(model_path)
        raise


def _transcribe(
    audio_path: str, work_dir: Path, bvid: str, model_name: str
) -> str:
    """用 whisper 转录音频，输出 SRT 文件。"""
    import warnings

    import whisper

    # 确保模型已下载（接管进度输出，避免 tqdm 刷屏）
    _ensure_model(model_name)

    print("[bilibili-note] whisper 转录中，请耐心等待...", file=sys.stderr)
    model = whisper.load_model(model_name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.transcribe(
            audio_path, language="zh", task="transcribe", verbose=False
        )
    print("[bilibili-note] whisper 转录完成", file=sys.stderr)

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
