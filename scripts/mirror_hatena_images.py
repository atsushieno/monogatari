#!/usr/bin/env python3
"""Mirror Hatena Fotolife image URLs used by imported posts into public/.

The markdown content remains unchanged; runtime rendering rewrites matching
remote URLs to these local files.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[1]
CONTENT_DIR = REPO / "src" / "content" / "posts"
PUBLIC_DIR = REPO / "public" / "hatena-images"
MANIFEST_PATH = PUBLIC_DIR / "manifest.json"
URL_RE = re.compile(
    r"https://cdn-ak\.f\.st-hatena\.com/images/fotolife/[^\]\)\"'<\s]+"
)


def local_path_for_url(url: str) -> Path:
    parsed = urlparse(url)
    prefix = "/images/fotolife/"
    if not parsed.path.startswith(prefix):
        raise ValueError(f"Not a Hatena Fotolife image URL: {url}")
    return PUBLIC_DIR / parsed.path.removeprefix("/images/")


def public_path_for_url(url: str) -> str:
    return "/" + local_path_for_url(url).relative_to(REPO / "public").as_posix()


def iter_urls() -> list[str]:
    urls: set[str] = set()
    for path in CONTENT_DIR.rglob("*"):
        if path.suffix not in {".md", ".mdx"}:
            continue
        text = path.read_text(encoding="utf-8")
        urls.update(URL_RE.findall(text))
    return sorted(urls)


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "monogatari-mirror/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        dest.write_bytes(response.read())
    return True


def main() -> int:
    urls = iter_urls()
    downloaded = 0
    failed: list[tuple[str, str]] = []

    for url in urls:
        dest = local_path_for_url(url)
        try:
            if download(url, dest):
                downloaded += 1
                print(f"mirrored {url} -> {dest.relative_to(REPO)}")
        except (OSError, urllib.error.URLError, ValueError) as exc:
            failed.append((url, str(exc)))
            print(f"failed {url}: {exc}", file=sys.stderr)

    manifest = {
        url: public_path_for_url(url)
        for url in urls
        if local_path_for_url(url).exists() and local_path_for_url(url).stat().st_size > 0
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        "{\n"
        + ",\n".join(
            f'  "{url}": "{path}"' for url, path in sorted(manifest.items())
        )
        + "\n}\n",
        encoding="utf-8",
    )

    print(f"{len(urls)} URLs, {downloaded} downloaded, {len(failed)} failed")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO)} with {len(manifest)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
