import os
from pathlib import Path


def get_instagram_cookie_file():
    cookie_file = os.getenv("YTDLP_COOKIES_FILE_INSTAGRAM", "").strip()

    if not cookie_file:
        return ""

    expanded = os.path.expandvars(cookie_file)
    expanded = os.path.expanduser(expanded)

    return expanded if Path(expanded).exists() else ""


def build_instagram_ydl_opts():
    opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "extractor_retries": 3,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        },
    }

    cookie_file = get_instagram_cookie_file()

    if cookie_file:
        opts["cookiefile"] = cookie_file

    return opts
