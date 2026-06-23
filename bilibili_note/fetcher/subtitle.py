"""字幕获取层。

以 B站 player/v2 API 为主获取字幕（CC 优先、AI 兜底），yt-dlp 作为备选。
API 方案直接调用 B站接口，不受 yt-dlp 网页抓取被 412 拦截的影响。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx

from .video_info import VideoInfo, HEADERS, load_cookies

PLAYER_API = "https://api.bilibili.com/x/player/v2"


def _seconds_to_srt_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _json_to_srt(sub_data: dict, work_dir: Path, name: str, lang: str) -> str:
    """B站字幕 JSON 转 SRT 文件。"""
    body = sub_data.get("body", [])
    blocks = []
    for i, item in enumerate(body, 1):
        start = _seconds_to_srt_time(item.get("from", 0))
        end = _seconds_to_srt_time(item.get("to", 0))
        content = item.get("content", "").strip()
        if content:
            blocks.append(f"{i}\n{start} --> {end}\n{content}\n")
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / f"{name}.{lang}.srt"
    path.write_text("\n".join(blocks), encoding="utf-8")
    return str(path)


def _match_subtitle(
    subs: list[dict], preferred_langs: list[str], prefer_ai: bool = False
) -> dict | None:
    """从字幕列表中按优先级选择。用 lan 字段区分：ai- 开头为 AI 字幕，其余为 CC。"""
    cc = [s for s in subs if not s.get("lan", "").startswith("ai-")]
    ai = [s for s in subs if s.get("lan", "").startswith("ai-")]
    pool = ai if prefer_ai else cc
    if not pool:
        pool = cc if prefer_ai else ai
    for lang in preferred_langs:
        for s in pool:
            if lang.lower() in s.get("lan", "").lower():
                return s
    return pool[0] if pool else None


def _fetch_via_api(
    video_info: VideoInfo,
    preferred_langs: list[str],
    work_dir: Path,
    cookies_path: str,
) -> tuple[str, str] | None:
    """通过 B站 player/v2 API 获取字幕。带重试，应对 auth_key 偶发失效。"""
    cookies = load_cookies(cookies_path)
    for _ in range(3):
        resp = httpx.get(
            PLAYER_API,
            params={"aid": video_info.aid, "cid": video_info.cid},
            cookies=cookies,
            headers=HEADERS,
            timeout=30,
        )
        data = resp.json()
        if data.get("code") != 0:
            return None
        subs = data.get("data", {}).get("subtitle", {}).get("subtitles", [])
        if not subs:
            return None

        chosen = _match_subtitle(subs, preferred_langs, prefer_ai=False)
        if not chosen:
            chosen = _match_subtitle(subs, preferred_langs, prefer_ai=True)
        if not chosen:
            return None
        source = "AI字幕" if chosen.get("lan", "").startswith("ai-") else "CC字幕"

        sub_url = chosen.get("subtitle_url", "")
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        elif sub_url and not sub_url.startswith("http"):
            sub_url = "https://" + sub_url
        if not sub_url:
            continue

        try:
            sub_resp = httpx.get(sub_url, headers=HEADERS, timeout=30)
            sub_resp.raise_for_status()
            sub_data = sub_resp.json()
            if not sub_data.get("body"):
                continue
            lang = chosen.get("lan", "zh")
            srt_path = _json_to_srt(sub_data, work_dir, video_info.bvid, lang)
            return srt_path, source
        except Exception:
            continue
    return None


def _fetch_via_ytdlp(
    video_info: VideoInfo,
    preferred_langs: list[str],
    work_dir: Path,
    cookies_path: str,
) -> tuple[str, str] | None:
    """yt-dlp 备选方案。"""
    if shutil.which("yt-dlp") is None:
        return None
    url = f"https://www.bilibili.com/video/{video_info.bvid}"
    before = set(work_dir.glob("*"))
    for auto, source in [(False, "CC字幕"), (True, "AI字幕")]:
        cmd = [
            "yt-dlp", "--skip-download",
            "--write-auto-subs" if auto else "--write-subs",
            "--sub-langs", ",".join(preferred_langs),
            "--sub-format", "srt/vtt/best",
            "--no-progress",
        ]
        if cookies_path:
            cmd += ["--cookies", cookies_path]
        cmd += ["-o", str(work_dir / "%(id)s.%(ext)s"), url]
        subprocess.run(cmd, capture_output=True, text=True)
        after = set(work_dir.glob("*"))
        for f in sorted(after - before):
            if f.suffix.lower() in (".srt", ".vtt"):
                return str(f), source
        before = set(work_dir.glob("*"))
    return None


def fetch_subtitle(
    video_info: VideoInfo,
    preferred_langs: list[str],
    work_dir: str,
    cookies_path: str = "",
) -> tuple[str, str]:
    """获取字幕。

    以 B站 player/v2 API 为主，yt-dlp 为备选。CC 字幕优先，AI 字幕兜底。

    Args:
        video_info: 视频元信息（含 aid, cid, bvid）。
        preferred_langs: 字幕语言优先级列表。
        work_dir: 字幕临时下载目录。
        cookies_path: Netscape 格式 cookies 文件路径。

    Returns:
        (字幕文件路径, 来源标记) 来源标记为 "CC字幕" 或 "AI字幕"。

    Raises:
        RuntimeError: 所有方案均未获取到字幕。
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    result = _fetch_via_api(video_info, preferred_langs, work, cookies_path)
    if result:
        return result

    result = _fetch_via_ytdlp(video_info, preferred_langs, work, cookies_path)
    if result:
        return result

    raise RuntimeError(
        "未找到可用字幕（CC 和 AI 均无）。"
        "可能原因：视频无字幕、需要登录态（配置 bilibili.cookies_path）、或需要 ASR（见 docs/Plans.md）"
    )
