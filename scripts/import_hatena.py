#!/usr/bin/env python3
"""Convert Hatena (MovableType export format) blogs into AstroPaper markdown posts.

Usage:
    python scripts/import_hatena.py <export.txt> <out_subdir> [--base-url URL]

Each MT entry becomes one markdown file under src/content/posts/<out_subdir>/.
"""
import sys
import os
import re
import html
import urllib.parse
import argparse
from datetime import datetime, timezone, timedelta

from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md

JST = timezone(timedelta(hours=9))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(REPO, "src", "content", "posts")

# MT multi-line section keys (value spans until the next "-----")
MULTILINE_KEYS = {"BODY", "EXTENDED BODY", "EXCERPT", "KEYWORDS", "COMMENT", "PING"}


def parse_entries(text):
    """Split an MT export file into a list of entry dicts."""
    # Entries are separated by a line of exactly 8 dashes.
    raw_entries = re.split(r"(?m)^--------\s*$", text)
    entries = []
    for raw in raw_entries:
        raw = raw.strip("\n")
        if not raw.strip():
            continue
        entries.append(parse_entry(raw))
    return entries


def parse_entry(raw):
    """Parse a single MT entry block into {meta, body, extended, comments}."""
    # Sections within an entry are separated by a line of exactly 5 dashes.
    sections = re.split(r"(?m)^-----\s*$", raw)
    entry = {
        "meta": {},
        "categories": [],
        "body": "",
        "extended": "",
        "comments": [],
    }
    # First section: header key/value lines (single-line metadata).
    header = sections[0]
    for line in header.splitlines():
        m = re.match(r"^([A-Z][A-Z ]*?):\s?(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if key == "CATEGORY":
            entry["categories"].append(val.strip())
        else:
            entry["meta"][key] = val.strip()

    # Remaining sections: each begins with "KEY:" then content.
    for sec in sections[1:]:
        sec = sec.strip("\n")
        if not sec.strip():
            continue
        m = re.match(r"^([A-Z][A-Z ]*?):\s*\n?(.*)$", sec, re.DOTALL)
        if not m:
            continue
        key = m.group(1)
        content = m.group(2)
        if key == "BODY":
            entry["body"] = content
        elif key == "EXTENDED BODY":
            entry["extended"] = content
        elif key == "COMMENT":
            entry["comments"].append(parse_comment(content))
    return entry


def parse_comment(content):
    """Parse a COMMENT section: leading key/value lines then free text."""
    meta = {}
    lines = content.splitlines()
    i = 0
    for i, line in enumerate(lines):
        m = re.match(r"^(AUTHOR|DATE|EMAIL|URL|IP):\s?(.*)$", line)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
        else:
            break
    text = "\n".join(lines[i:]).strip()
    return {"meta": meta, "text": text}


def parse_mt_date(s):
    """MT date format: MM/DD/YYYY HH:MM:SS (assumed JST)."""
    s = s.strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=JST)
        except ValueError:
            continue
    return None


def preprocess_html(raw_html):
    """Clean Hatena-specific markup before HTML->markdown conversion.

    - Strip hatena auto-keyword links (keep their text only).
    - Convert footnotes into Markdown footnote syntax.
    - Convert iframe embeds into plain links.
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. Hatena keyword auto-links -> plain text.
    for a in soup.find_all("a", class_="keyword"):
        a.replace_with(a.get_text())

    # 2. Footnotes. Inline markers look like:
    #    <a href="#f-XXX" name="fn-XXX" title="...">*N</a>
    # Definitions live in <div class="footnote"> at the end.
    footnote_div = soup.find("div", class_="footnote")
    footnote_defs = {}  # id -> text
    if footnote_div:
        for p in footnote_div.find_all("p", class_="footnote"):
            link = p.find("a", class_="footnote-number")
            if not link:
                continue
            fid = link.get("name", "").replace("f-", "")
            txt_span = p.find("span", class_="footnote-text")
            txt = txt_span.get_text() if txt_span else p.get_text()
            footnote_defs[fid] = txt.strip()
        footnote_div.decompose()

    # Replace inline footnote markers with [^fid].
    for a in soup.find_all("a"):
        name = a.get("name", "")
        href = a.get("href", "")
        if name.startswith("fn-") or href.startswith("#f-"):
            fid = name.replace("fn-", "") or href.replace("#f-", "")
            a.replace_with(f"[^{fid}]")

    # 3. iframe embeds.
    #    Hatena embed cards (hatenablog-parts.com/embed?url=...) carry the page
    #    title in the iframe's `title` attribute and are followed by a
    #    <cite class="hatena-citation"> with the canonical link. Turn them into a
    #    link card (title + domain) so the link overview survives. Other embeds
    #    (YouTube, SpeakerDeck, SoundCloud, ...) become plain links.
    cards = []  # collected link-card data; emitted as @@HATENACARD:n@@ placeholders
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "") or ""
        if "hatenablog-parts.com" in src:
            title = (iframe.get("title") or "").strip()
            url = domain = None
            # Prefer the adjacent <cite class="hatena-citation"> for the real URL.
            cite = _adjacent_citation(iframe)
            if cite and cite.find("a"):
                anchor = cite.find("a")
                url = anchor.get("href")
                domain = anchor.get_text(strip=True)
                cite.decompose()
            if not url:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(src).query)
                url = (params.get("url") or [""])[0]
            if url and not domain:
                domain = urllib.parse.urlparse(url).netloc
            if url:
                idx = len(cards)
                cards.append(
                    {"url": url, "title": title or domain or url, "domain": domain or ""}
                )
                iframe.replace_with(f"@@HATENACARD:{idx}@@")
            else:
                iframe.decompose()
            continue
        if src.startswith("//"):
            src = "https:" + src
        if src:
            new = soup.new_tag("a", href=src)
            new.string = src
            iframe.replace_with(new)
        else:
            iframe.decompose()

    return str(soup), footnote_defs, cards


def _adjacent_citation(iframe):
    """Find the hatena-citation <cite> that belongs to this embed iframe."""
    sib = iframe.next_sibling
    while sib is not None:
        name = getattr(sib, "name", None)
        if name == "cite" and "hatena-citation" in (sib.get("class") or []):
            return sib
        if name == "iframe":
            break
        sib = sib.next_sibling
    return None


def render_link_card(card):
    title = html.escape(card["title"])
    url = html.escape(card["url"], quote=True)
    domain = html.escape(card["domain"])
    return (
        f'<iframe src="https://hatenablog-parts.com/embed?url='
        f'{urllib.parse.quote(card["url"], safe="")}" title="{title}" '
        f'class="hatena-embed-frame" scrolling="no" frameborder="0" '
        f'loading="lazy"></iframe>'
        f'<cite class="hatena-citation"><a href="{url}" target="_blank" '
        f'rel="noopener noreferrer">{domain}</a></cite>'
    )


def html_to_markdown(raw_html):
    cleaned, footnote_defs, cards = preprocess_html(raw_html)
    text = md(
        cleaned,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )
    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Expand link-card placeholders into raw HTML (markdownify leaves them alone).
    if cards:
        text = re.sub(
            r"@@HATENACARD:(\d+)@@",
            lambda m: render_link_card(cards[int(m.group(1))]),
            text,
        )

    if footnote_defs:
        text += "\n\n"
        for fid, ftext in footnote_defs.items():
            ftext = ftext.replace("\n", " ").strip()
            text += f"[^{fid}]: {ftext}\n"
    return text


def make_description(markdown_text):
    """First paragraph-ish chunk of plain text, trimmed to ~160 chars."""
    # Drop raw HTML (e.g. link cards), footnote defs and markdown syntax noise.
    text = re.sub(r"<[^>]+>", "", markdown_text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#>*`_\-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:157].rstrip() + "..."
    return text


def yaml_quote(s):
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def slugify_basename(basename):
    """Hatena basenames like '20120502/p1' or '2026/05/31/185456'."""
    return basename.strip("/")


def build_markdown(entry, source_name, base_url):
    meta = entry["meta"]
    title = meta.get("TITLE", "").strip()
    dt = parse_mt_date(meta.get("DATE", ""))
    basename = meta.get("BASENAME", "")

    body_md = html_to_markdown(entry["body"])
    if entry["extended"].strip():
        body_md += "\n\n" + html_to_markdown(entry["extended"])

    description = make_description(body_md) or title

    tags = [c for c in entry["categories"] if c]

    fm = ["---"]
    fm.append(f"title: {yaml_quote(title)}")
    if dt:
        fm.append(f"pubDatetime: {dt.isoformat()}")
    fm.append("author: atsushieno")
    fm.append('timezone: "Asia/Tokyo"')
    if tags:
        fm.append("tags:")
        for t in tags:
            fm.append(f"  - {yaml_quote(t)}")
    fm.append(f"description: {yaml_quote(description)}")
    if base_url and basename:
        fm.append(f"canonicalURL: {yaml_quote(base_url.rstrip('/') + '/' + basename)}")
    fm.append("---")

    parts = ["\n".join(fm), "", body_md]

    # Append original reader comments for preservation.
    if entry["comments"]:
        parts.append("\n---\n\n## コメント")
        for c in entry["comments"]:
            cauthor = c["meta"].get("author", "anonymous")
            cdate = c["meta"].get("date", "")
            curl = c["meta"].get("url", "")
            who = f"[{cauthor}]({curl})" if curl else cauthor
            header = f"**{who}**" + (f" — {cdate}" if cdate else "")
            ctext = html_to_markdown(c["text"]) if c["text"].strip() else ""
            parts.append(f"\n{header}\n\n{ctext}")

    return "\n".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("subdir")
    ap.add_argument("--base-url", default="")
    args = ap.parse_args()

    with open(args.export, encoding="utf-8") as f:
        text = f.read()

    entries = parse_entries(text)
    out_root = os.path.join(POSTS_DIR, args.subdir)
    os.makedirs(out_root, exist_ok=True)

    written = 0
    skipped = 0
    seen = {}
    for entry in entries:
        basename = entry["meta"].get("BASENAME")
        # Skip malformed/truncated entries (must have basename and a valid date).
        if not basename or parse_mt_date(entry["meta"].get("DATE", "")) is None:
            skipped += 1
            continue
        slug = slugify_basename(basename)
        # Ensure unique filenames.
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}-{seen[slug]}"
        else:
            seen[slug] = 0
        out_path = os.path.join(out_root, slug + ".md")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        content = build_markdown(entry, args.subdir, args.base_url)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        written += 1

    print(f"{args.export}: wrote {written} posts, skipped {skipped} into {out_root}")


if __name__ == "__main__":
    main()
