#!/usr/bin/env python3
"""Mirror Hatena Fotolife image URLs used by imported posts into public/.

The markdown content remains unchanged; runtime rendering rewrites matching
remote URLs to these local files.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parents[1]
CONTENT_DIR = REPO / "src" / "content" / "posts"
PUBLIC_DIR = REPO / "public" / "hatena-images"
MANIFEST_PATH = PUBLIC_DIR / "manifest.json"
TABLE_REPAIRS_PATH = PUBLIC_DIR / "table-repairs.json"
EXPORT_PATH = REPO / "atsushieno.hatenablog.com.export.txt"
HATENA_IMAGE_URL_RE = re.compile(
    r"https://cdn-ak\.f\.st-hatena\.com/images/fotolife/[^\]\)\"'<\s]+"
)
IMGUR_IMAGE_URL_RE = re.compile(
    r"https?://(?:i\.)?imgur\.com/[^\]\)\"'<\s]+\.(?:apng|avif|gif|jpe?g|png|webp)",
    re.IGNORECASE,
)


def is_hatena_fotolife_url(url: str) -> bool:
    return url.startswith("https://cdn-ak.f.st-hatena.com/images/fotolife/")


def is_imgur_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc not in {"i.imgur.com", "imgur.com"}:
        return False
    return bool(re.search(r"\.(?:apng|avif|gif|jpe?g|png|webp)$", parsed.path, re.I))


def local_path_for_url(url: str) -> Path:
    if is_imgur_image_url(url):
        return local_path_for_external_url(url)

    parsed = urlparse(url)
    prefix = "/images/fotolife/"
    if not parsed.path.startswith(prefix):
        raise ValueError(f"Not a Hatena Fotolife image URL: {url}")
    return PUBLIC_DIR / parsed.path.removeprefix("/images/")


def local_path_for_external_url(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Not a downloadable image URL: {url}")

    path = parsed.path.strip("/")
    if not path:
        raise ValueError(f"Image URL has no path: {url}")
    return PUBLIC_DIR / "external" / parsed.netloc / path


def public_path_for_url(url: str) -> str:
    return "/" + local_path_for_url(url).relative_to(REPO / "public").as_posix()


def public_path_for_external_url(url: str) -> str:
    return "/" + local_path_for_external_url(url).relative_to(REPO / "public").as_posix()


def iter_urls() -> list[str]:
    urls: set[str] = set()
    for path in CONTENT_DIR.rglob("*"):
        if path.suffix not in {".md", ".mdx"}:
            continue
        text = path.read_text(encoding="utf-8")
        urls.update(HATENA_IMAGE_URL_RE.findall(text))
        urls.update(IMGUR_IMAGE_URL_RE.findall(text))
    return sorted(urls)


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "monogatari-mirror/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        dest.write_bytes(response.read())
    return True


class TableImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.row = -1
        self.cell = -1
        self.images: list[dict[str, str | int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value or "" for name, value in attrs}
        if tag == "table":
            self.in_table = True
            self.row = -1
            return
        if self.in_table and tag == "tr":
            self.in_row = True
            self.row += 1
            self.cell = -1
            return
        if self.in_row and tag in {"td", "th"}:
            self.in_cell = True
            self.cell += 1
            return
        if self.in_cell and tag == "img" and attr.get("src"):
            self.images.append(
                {
                    "row": self.row,
                    "cell": self.cell,
                    "alt": attr.get("alt", ""),
                    "src": attr["src"],
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self.in_cell = False
        elif tag == "tr":
            self.in_row = False
        elif tag == "table":
            self.in_table = False


def iter_export_entries() -> list[tuple[dict[str, str], str]]:
    if not EXPORT_PATH.exists():
        return []

    entries: list[tuple[dict[str, str], str]] = []
    metadata: dict[str, str] = {}
    body: list[str] = []
    in_body = False

    for line in EXPORT_PATH.read_text(encoding="utf-8").splitlines():
        if line == "--------":
            if metadata:
                entries.append((metadata, "\n".join(body)))
            metadata = {}
            body = []
            in_body = False
            continue

        if in_body:
            body.append(line)
        elif line == "BODY:":
            in_body = True
        elif ": " in line:
            key, value = line.split(": ", 1)
            metadata[key] = value

    if metadata:
        entries.append((metadata, "\n".join(body)))
    return entries


def mirror_table_repairs() -> tuple[int, int, list[tuple[str, str]]]:
    repairs: dict[str, list[dict[str, str | int]]] = {}
    downloaded = 0
    failed: list[tuple[str, str]] = []

    for metadata, body in iter_export_entries():
        basename = metadata.get("BASENAME")
        if not basename:
            continue

        parser = TableImageParser()
        parser.feed(body)
        if not parser.images:
            continue

        post_repairs = []
        for image in parser.images:
            src = str(image["src"])
            try:
                local_src = public_path_for_external_url(src)
                downloaded_now = download(src, local_path_for_external_url(src))
            except (OSError, urllib.error.URLError, ValueError) as exc:
                failed.append((src, str(exc)))
                print(f"failed {src}: {exc}", file=sys.stderr)
                continue

            if downloaded_now:
                downloaded += 1
            post_repairs.append({**image, "localSrc": local_src})

        if post_repairs:
            repairs[basename] = post_repairs

    TABLE_REPAIRS_PATH.write_text(
        json.dumps(repairs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(repairs), downloaded, failed


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
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    repair_count, repair_downloaded, repair_failed = mirror_table_repairs()

    print(f"{len(urls)} URLs, {downloaded} downloaded, {len(failed)} failed")
    print(f"wrote {MANIFEST_PATH.relative_to(REPO)} with {len(manifest)} entries")
    print(
        f"wrote {TABLE_REPAIRS_PATH.relative_to(REPO)} with "
        f"{repair_count} posts, {repair_downloaded} downloaded, "
        f"{len(repair_failed)} failed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
