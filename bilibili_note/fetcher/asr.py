"""字幕获取层：下载音频 + whisper 转录生成字幕。

音频下载优先通过 B站 playurl API 获取直链（稳定，不被 412 拦截），
不可用时降级 yt-dlp。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from ..log import info, warn, error, progress, progress_done
from .video_info import VideoInfo, HEADERS

PLAYURL_API = "https://api.bilibili.com/x/player/playurl"


# ---------------------------------------------------------------------------
# 音频下载
# ---------------------------------------------------------------------------

def _download_audio(video_info: VideoInfo, work_dir: Path) -> str:
    """下载 B站视频音频，返回文件路径。已有缓存则复用。

    优先走 playurl API 直链（httpx），不被 412 拦截；失败降级 yt-dlp。
    """
    page = getattr(video_info, "page", 1)
    audio_prefix = f"{video_info.bvid}.p{page}" if page > 1 else video_info.bvid

    # 检查是否已缓存
    for p in sorted(work_dir.glob(f"{audio_prefix}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)

    info("下载音频中，请耐心等待...")

    # 方案一：playurl API 直链下载
    audio_url = _get_audio_url(video_info)
    if audio_url:
        try:
            return _download_audio_direct(audio_url, work_dir, audio_prefix)
        except Exception as exc:
            warn(f"直链下载失败 ({exc})，降级 yt-dlp...")

    # 方案二：yt-dlp 降级
    warn("提示：如遇网络问题可尝试关闭代理后重试")
    return _download_via_ytdlp(video_info, work_dir, audio_prefix)


# -- playurl API 方案 ---------------------------------------------------------

def _get_audio_url(video_info: VideoInfo) -> str | None:
    """通过 B站 playurl API 获取音频流直链。"""
    try:
        resp = httpx.get(
            PLAYURL_API,
            params={
                "bvid": video_info.bvid,
                "cid": video_info.cid,
                "fnval": 16,
                "qn": 0,
                "fnver": 0,
                "fourk": 1,
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            return None
        dash = data.get("data", {}).get("dash", {})
        audios = dash.get("audio", [])
        if audios:
            return audios[0].get("baseUrl") or audios[0].get("base_url", "")
        return None
    except Exception:
        return None


def _download_audio_direct(
    audio_url: str, work_dir: Path, audio_prefix: str
) -> str:
    """从直链流式下载音频，显示百分比进度。"""
    ext = os.path.splitext(audio_url.split("?")[0])[1] or ".m4a"
    output_path = work_dir / f"{audio_prefix}{ext}"

    with httpx.stream(
        "GET", audio_url,
        headers={**HEADERS, "Referer": "https://www.bilibili.com"},
        timeout=300, follow_redirects=True,
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        with open(output_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded * 100 // total
                    progress(f"下载音频  {pct}%")
    progress_done(f"下载音频  100%")
    info("音频下载完成")
    return str(output_path)


# -- yt-dlp 降级方案 -----------------------------------------------------------

_YTDLP_RETRYABLE = (
    "SSL: UNEXPECTED_EOF_WHILE_READING",
    "EOF occurred in violation of protocol",
    "HTTP Error 5",
    "HTTP Error 412",
    "timed out",
    "Connection reset by peer",
    "No route to host",
)

_YTDLP_MAX_RETRIES = 3
_YTDLP_BACKOFF = 2.0


def _download_via_ytdlp(
    video_info: VideoInfo, work_dir: Path, audio_prefix: str
) -> str:
    """yt-dlp 降级下载，带重试。"""
    page = getattr(video_info, "page", 1)
    url = f"https://www.bilibili.com/video/{video_info.bvid}"
    if page > 1:
        url += f"?p={page}"
    output_template = str(work_dir / f"{audio_prefix}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]/bestaudio/best",
        "--no-progress",
        "--no-playlist",
        "--user-agent", HEADERS["User-Agent"],
        "--add-header", f"Referer:{HEADERS['Referer']}",
        "-o", output_template,
        url,
    ]

    for attempt in range(_YTDLP_MAX_RETRIES + 1):
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            break
        except KeyboardInterrupt:
            _cleanup_partial(work_dir, audio_prefix)
            raise
        except subprocess.CalledProcessError as exc:
            err_text = (exc.stderr or "") + (exc.stdout or "")
            retryable = any(
                keyword in err_text for keyword in _YTDLP_RETRYABLE
            )
            if retryable and attempt < _YTDLP_MAX_RETRIES:
                wait = _YTDLP_BACKOFF * (2 ** attempt)
                first_line = err_text.strip().split("\n")[0]
                warn(f"yt-dlp 失败，{wait:.0f}s 后重试 "
                      f"({attempt + 1}/{_YTDLP_MAX_RETRIES})")
                if first_line:
                    warn(f"错误原因：{first_line}")
                time.sleep(wait)
            else:
                if err_text:
                    error(f"yt-dlp 错误详情：\n{err_text.strip()}")
                _cleanup_partial(work_dir, audio_prefix)
                raise

    info("音频下载完成")
    for p in sorted(work_dir.glob(f"{audio_prefix}.*")):
        if p.suffix.lower() in (".m4a", ".webm", ".mp3", ".opus", ".aac"):
            return str(p)
    _cleanup_partial(work_dir, audio_prefix)
    raise RuntimeError("音频下载失败，文件未找到")


def _cleanup_partial(work_dir: Path, prefix: str) -> None:
    """清理下载中断的残留文件（.part、.ytdl 等）。"""
    for p in sorted(work_dir.glob(f"{prefix}*")):
        if p.is_file():
            p.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# whisper 转录
# ---------------------------------------------------------------------------

def _seconds_to_srt(sec: float) -> str:
    """秒数转 SRT 时间戳格式。"""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# whisper 模型下载 URL（来自 openai-whisper 源码）
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
    """确保 whisper 模型已缓存且 SHA256 正确，否则接管下载并显示进度。"""
    import hashlib
    import urllib.request

    url = _MODEL_URLS.get(model_name)
    if not url:
        return

    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
    os.makedirs(cache_dir, exist_ok=True)
    model_path = os.path.join(cache_dir, f"{model_name}.pt")
    expected_hash = url.split("/")[-2]

    # 校验已有缓存
    if os.path.exists(model_path) and os.path.getsize(model_path) > 0:
        sha = hashlib.sha256()
        with open(model_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                sha.update(chunk)
        if sha.hexdigest() == expected_hash:
            return
        os.unlink(model_path)

    progress(f"下载 whisper 模型 ({model_name}) ...")

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
                    progress(f"下载 whisper 模型 ({model_name})  {pct}%")
        with open(model_path, "wb") as f:
            f.write(data)
        print(file=sys.stderr)
    except Exception:
        print(file=sys.stderr)
        if os.path.exists(model_path):
            os.unlink(model_path)
        raise


def _transcribe(
    audio_path: str, work_dir: Path, bvid: str, model_name: str
) -> str:
    """用 whisper 转录音频为 SRT 字幕文件。"""
    import warnings

    import whisper

    _ensure_model(model_name)

    info("whisper 转录中，请耐心等待...")
    model = whisper.load_model(model_name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = model.transcribe(
            audio_path, language="zh", task="transcribe", verbose=False
        )
    info("whisper 转录完成")

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


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------

def fetch_subtitle(
    video_info: VideoInfo,
    work_dir: str = ".cache",
    model_name: str = "small",
) -> tuple[str, str]:
    """下载音频 + whisper 转录，返回 (SRT路径, 来源标记)。"""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    audio_path = _download_audio(video_info, work)
    srt_path = _transcribe(audio_path, work, video_info.bvid, model_name)
    return srt_path, "ASR转录"
