#!/usr/bin/env python3
"""Build local metadata for imported Hatena link-card placeholders."""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser


ROOT = pathlib.Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "src" / "content" / "posts"
OUTPUT_PATH = ROOT / "public" / "hatena-embeds" / "manifest.json"
LINK_RE = re.compile(r"^\s*\[([^\]]+)\]\((https?://[^)\s]+)\)\s*$")
IMPORTED_EMBED_RE = re.compile(
    r"^\s*<https?://[^>]+>\[([^\]]+)\]\((https?://[^)\s]+)\)\s*$"
)


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
            return

        if tag.lower() != "meta":
            return

        key = attr.get("property") or attr.get("name")
        value = attr.get("content")
        if key and value:
            self.meta[key.lower()] = value.strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())


def normalize_host(hostname: str) -> str:
    return hostname.lower().removeprefix("www.")


def discover_urls() -> list[str]:
    urls: dict[str, None] = {}
    for path in POSTS_DIR.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line in text.splitlines():
            match = LINK_RE.match(line) or IMPORTED_EMBED_RE.match(line)
            if not match:
                continue

            label, url = match.groups()
            parsed = urllib.parse.urlparse(url)
            if normalize_host(label.strip()) == normalize_host(parsed.hostname or ""):
                urls[url] = None

    return sorted(urls)


def clean(value: str | None) -> str | None:
    if not value:
        return None
    value = html.unescape(value)
    value = " ".join(value.split())
    return value or None


def first_meta(parser: MetadataParser, *keys: str) -> str | None:
    for key in keys:
        value = clean(parser.meta.get(key))
        if value:
            return value
    return None


def fetch_metadata(url: str, timeout: float) -> tuple[str, dict[str, str] | None, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return url, None, f"skipped non-html content-type: {content_type}"

            raw = response.read(1_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
            document = raw.decode(charset, errors="replace")
            final_url = response.geturl()
    except (
        TimeoutError,
        socket.timeout,
        urllib.error.HTTPError,
        urllib.error.URLError,
        OSError,
    ) as exc:
        return url, None, str(exc)

    parser = MetadataParser()
    parser.feed(document)

    title = first_meta(parser, "og:title", "twitter:title") or clean(parser.title)
    image = first_meta(parser, "og:image", "twitter:image", "twitter:image:src")
    description = first_meta(parser, "og:description", "twitter:description", "description")
    site_name = first_meta(parser, "og:site_name", "application-name")

    if image:
        image = urllib.parse.urljoin(final_url, image)

    metadata = {
        key: value
        for key, value in {
            "title": title,
            "image": image,
            "description": description,
            "siteName": site_name,
            "finalUrl": final_url if final_url != url else None,
        }.items()
        if value
    }
    if not metadata:
        return url, None, "no metadata found"

    return url, metadata, None


def load_existing_manifest() -> dict[str, dict[str, str]]:
    if not OUTPUT_PATH.exists():
        return {}

    try:
        loaded = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(loaded, dict):
        return {}

    manifest: dict[str, dict[str, str]] = {}
    for url, metadata in loaded.items():
        if isinstance(url, str) and isinstance(metadata, dict):
            manifest[url] = {
                str(key): str(value)
                for key, value in metadata.items()
                if isinstance(key, str) and isinstance(value, str)
            }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch every discovered URL instead of only missing manifest entries.",
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry URLs whose previous manifest entry only recorded an error.",
    )
    args = parser.parse_args()

    urls = discover_urls()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = {} if args.refresh else load_existing_manifest()
    pending_urls = urls if args.refresh else [url for url in urls if url not in results]
    if args.retry_failures and not args.refresh:
        pending_urls.extend(
            url
            for url in urls
            if url in results and "error" in results[url] and url not in pending_urls
        )
    failures: list[tuple[str, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(fetch_metadata, url, args.timeout): url for url in pending_urls
        }
        for future in as_completed(futures):
            url, metadata, error = future.result()
            if metadata:
                results[url] = metadata
            elif error:
                results[url] = {"error": error}
                failures.append((url, error))

    OUTPUT_PATH.write_text(
        json.dumps(dict(sorted(results.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Discovered {len(urls)} Hatena embed placeholder URLs.")
    if args.refresh:
        print(f"Refreshed {len(pending_urls)} URLs.")
    elif args.retry_failures:
        print(f"Fetched {len(pending_urls)} missing or previously failed URLs.")
    else:
        print(f"Fetched {len(pending_urls)} missing URLs.")
    print(f"Wrote {len(results)} total metadata entries to {OUTPUT_PATH.relative_to(ROOT)}.")
    if failures:
        print(f"Skipped {len(failures)} URLs that could not be read:")
        for url, error in failures[:20]:
            print(f"  - {url}: {error}")
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
