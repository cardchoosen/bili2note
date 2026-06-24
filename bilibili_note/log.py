"""统一日志输出：stderr 带颜色标记。

用法:
    from .log import info, warn, error, progress, progress_done
    info("下载音频中...")
    warn("下载失败，2s 后重试")
    error("yt-dlp 错误：...")
    progress("下载音频  45%")        # \r 行内刷新
    progress_done("下载音频  100%")   # \r 刷新后换行
"""

from __future__ import annotations

import sys

_TAG = "bili2note"

# ANSI 颜色
_RESET = "\033[0m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"


def info(msg: str) -> None:
    """正常信息。"""
    print(f"{_CYAN}[{_TAG}]{_RESET} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """警告信息（黄色）。"""
    print(f"{_YELLOW}[{_TAG}]{_RESET} {msg}", file=sys.stderr)


def error(msg: str) -> None:
    """错误信息（红色）。"""
    print(f"{_RED}[{_TAG}]{_RESET} {msg}", file=sys.stderr)


def progress(msg: str) -> None:
    """行内刷新进度（\r 覆盖，不换行）。"""
    print(f"\r{_CYAN}[{_TAG}]{_RESET} {msg}", file=sys.stderr, end="", flush=True)


def progress_done(msg: str) -> None:
    """行内进度完成后换行。"""
    print(f"\r{_CYAN}[{_TAG}]{_RESET} {msg}", file=sys.stderr)
