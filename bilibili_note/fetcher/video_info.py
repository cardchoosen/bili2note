"""B站视频元信息抓取。

通过 B 站 view API 获取视频标题、UP 主、时长、简介、cid 等元信息。
支持合集分 P：从 URL 的 ?p= 参数取对应分 P 的 cid。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

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
    page: int = 1  # 分 P 序号

    def to_dict(self) -> dict:
        return asdict(self)


def extract_bvid(url: str) -> str:
    """从 B 站 URL 或纯 BV 号中提取 BV 号。"""
    m = _BV_PATTERN.search(url)
    if not m:
        raise ValueError(f"无法从输入中提取 BV 号: {url}")
    return m.group(1)


def extract_page(url: str) -> int:
    """从 B 站 URL 中提取分 P 序号，默认 1。"""
    m = _PAGE_PATTERN.search(url)
    return int(m.group(1)) if m else 1


def load_cookies(cookies_path: str) -> dict:
    """从 cookies 文件加载为 dict。支持 JSON 数组格式和 Netscape 格式。"""
    if not cookies_path:
        return {}
    p = Path(cookies_path)
    if not p.exists():
        return {}
    if p.suffix == ".json":
        arr = json.loads(p.read_text(encoding="utf-8"))
        return {item["name"]: item["value"] for item in arr}
    cookies: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies[parts[5]] = parts[6]
    return cookies


def fetch_video_info(url: str, cookies_path: str = "") -> VideoInfo:
    """抓取视频元信息。

    Args:
        url: B 站视频 URL 或 BV 号，支持 ?p=N 指定分 P。
        cookies_path: cookies 文件路径（JSON 或 Netscape 格式），部分视频需要登录态。

    Returns:
        VideoInfo 数据对象。
    """
    bvid = extract_bvid(url)
    page = extract_page(url)
    cookies = load_cookies(cookies_path)
    resp = httpx.get(
        VIEW_API,
        params={"bvid": bvid},
        cookies=cookies,
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
