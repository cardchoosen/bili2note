"""B站视频元信息抓取：通过 view API 获取标题、UP主、时长、cid 等。"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict

import httpx

VIEW_API = "https://api.bilibili.com/x/web-interface/view"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

_BV_PATTERN = re.compile(r"(BV[0-9A-Za-z]{8,12})")
_PAGE_PATTERN = re.compile(r"[?&]p=(\d+)")


@dataclass
class VideoInfo:
    bvid: str
    aid: int
    cid: int
    title: str
    up: str
    duration: int  # 秒
    desc: str
    pic: str
    pubdate: int
    page: int = 1  # 分P序号

    def to_dict(self) -> dict:
        return asdict(self)


def extract_bvid(url: str) -> str:
    """从 URL 或纯 BV 号中提取 BV 号。"""
    m = _BV_PATTERN.search(url)
    if not m:
        raise ValueError(f"无法从输入中提取 BV 号: {url}")
    return m.group(1)


def extract_page(url: str) -> int:
    """从 URL 中提取分P序号，默认 1。"""
    m = _PAGE_PATTERN.search(url)
    return int(m.group(1)) if m else 1


def fetch_video_info(url: str) -> VideoInfo:
    """抓取视频元信息，支持 ?p=N 指定分P。"""
    bvid = extract_bvid(url)
    page = extract_page(url)

    resp = httpx.get(
        VIEW_API,
        params={"bvid": bvid},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(
            f"B站 API 错误: code={data.get('code')} message={data.get('message')}"
        )

    d = data["data"]
    cid = d["cid"]
    title = d["title"]
    duration = d["duration"]

    # 分P 视频：从 pages 数组取对应页的 cid、标题、时长
    pages = d.get("pages", [])
    if page > 1 and len(pages) >= page:
        page_info = pages[page - 1]
        cid = page_info["cid"]
        part = page_info.get("part", "")
        if part:
            title = f"{title} - {part}"
        duration = page_info.get("duration", duration)

    return VideoInfo(
        bvid=bvid,
        aid=d["aid"],
        cid=cid,
        title=title,
        up=d["owner"]["name"],
        duration=duration,
        desc=d.get("desc", "") or "",
        pic=d.get("pic", "") or "",
        pubdate=d.get("pubdate", 0),
        page=page,
    )


def format_duration(seconds: int) -> str:
    """秒数格式化为 mm:ss 或 h:mm:ss。"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
