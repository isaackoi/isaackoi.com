from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import textwrap
from copy import deepcopy
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}
SITE_TITLE = "Isaac Koi Archive"
SITE_SHORT_TITLE = "Isaac Koi"
SITE_BRAND_NAME = "Isaac Koi"
SITE_DOMAIN = "isaackoi.com"
SITE_URL = f"https://{SITE_DOMAIN}"
SITE_DESCRIPTION = "Articles and guides on Isaac Koi's UFO archive, organized as a navigable topic tree."
SITE_TAGLINE = "Structured notes, cases, timelines, books, personalities and source material from the Isaac Koi archive."
HOME_HERO_TITLE = "A navigable UFO research archive"
HOME_HERO_ROUTE_CHIPS = (
    "Cases",
    "Timelines",
    "Books",
    "Personalities",
    "Videos",
    "Source material",
)
HOME_HERO_TOPIC_LINKS = (
    ("Starter Pack", "/ufog/starter-pack"),
    ("Best UFO Cases", "/ufog/best-ufo-cases"),
    ("UFO Timeline", "/ufo-history/ufo"),
    ("UFO Books", "/ufo-history/ufo-books"),
    ("UFO Personalities", "/ufo-history/ufo-personalities"),
    ("UFO Videos", "/ufog/ufo-videos"),
)
SKIP_ROOT_CATEGORY_PATHS = {"tobedeleted", "uncategorised"}
MAX_SIBLING_LINKS = 14
MAX_CATEGORY_CHILD_LINKS = 60
MAX_RENDERED_CATEGORY_CARDS = 120
MAX_RENDERED_TAG_CARDS = 120
MAX_HOME_RECENT = 12
MAX_PLANNED_SECTIONS = 12
MAX_SEARCH_RESULTS_PER_QUERY = 48
BOOK_ROUTE_PREFIX = "/ufo-history/ufo-books/"
BOOK_COVER_CACHE_ROOT = Path("assets/source/book-covers")
BOOK_COVER_PLACEHOLDER_URL = "/assets/images/book-cover-placeholder.svg"
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€™", "â€œ", "â€\x9d", "â€“", "â€”", "â€¦")
PRESERVED_OUTPUT_NAMES = {".bundle", "vendor", "Gemfile.lock"}
RAW_HTML_BLOCK_TAGS = {"table", "iframe", "video", "audio", "embed", "object"}
SKIP_ITEM_ROUTE_PREFIXES = ("/other/admin",)
LOCAL_URL_PREFIXES = (
    "images/",
    "documents/",
    "media/",
    "book-covers/",
    "ufog/",
    "ufo-history/",
    "tags/",
)
LOCAL_SITE_PREFIXES = (
    "assets",
    "book-covers",
    "documents",
    "homepage",
    "images",
    "media",
    "search",
    "sitemap",
    "tags",
    "ufo-history",
    "ufog",
    "uncategorised",
    "www.cassiopaea.org",
)
SCHEMELESS_EXTERNAL_HOST_PATTERN = re.compile(
    r"^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?$",
    re.IGNORECASE,
)
NON_HOST_SUFFIXES = (
    ".7z",
    ".avi",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".htm",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".php",
    ".png",
    ".rar",
    ".svg",
    ".txt",
    ".webm",
    ".webp",
    ".wmv",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
)
LEGACY_SECTION_ROUTE_PREFIXES = {
    "alien-photos": "/ufog/alien-photos",
    "best-ufo-cases": "/ufog/best-ufo-cases",
    "starter-pack": "/ufog/starter-pack",
    "tags": "/tags",
    "ufo": "/ufo-history/ufo",
    "ufo-books": "/ufo-history/ufo-books",
    "ufo-personalities": "/ufo-history/ufo-personalities",
    "ufo-videos": "/ufog/ufo-videos",
    "ufog": "/ufog",
}
HOME_INTRO_COPY = (
    "A large public archive of UFO cases, books, personalities, timelines, videos, and reference material. "
    "Start with the Starter Pack if you want an orientation, Best UFO Cases if you want landmark incidents, "
    "or Search if you already know the case, person, book, or year you need."
)
SECTION_EDITORIAL = {
    "/ufog": {
        "lead": "The working branch of the archive: starter guides, curated cases, image-led pages, and video analyses.",
        "summary": "Start here for guided entry points, debunks, and image-heavy material.",
        "start_links": [
            ("Starter Pack", "/ufog/starter-pack"),
            ("Best UFO Cases", "/ufog/best-ufo-cases"),
            ("UFO Videos", "/ufog/ufo-videos"),
        ],
    },
    "/ufog/starter-pack": {
        "lead": "A guided introduction for readers who want the archive’s assumptions, methods, and recommended starting points before diving deeper.",
        "summary": "Orientation material for new readers and a sensible first stop before the larger archive.",
        "start_links": [
            ("Section 1", "/ufog/starter-pack/1-introduction"),
            ("Preliminary points", "/ufog/starter-pack/2-preliminary-points"),
        ],
    },
    "/ufog/best-ufo-cases": {
        "lead": "A selective branch focused on cases and frameworks that Isaac Koi treated as especially worth examining.",
        "summary": "A curated route into the strongest or most discussed UFO cases in the archive.",
        "start_links": [
            ("Introduction", "/ufog/best-ufo-cases/1-introduction"),
            ("Case criteria", "/ufog/best-ufo-cases/20-quantitative-criteria-hynek-strangeness-and-probability"),
        ],
    },
    "/ufog/ufo-videos": {
        "lead": "Video-focused pages, often built around specific clips, stills, and debunking notes.",
        "summary": "An image-led branch for clip-by-clip analysis and video case notes.",
        "start_links": [
            ("Video archive", "/ufog/ufo-videos"),
            ("Search videos", "/search/"),
        ],
    },
    "/ufog/alien-photos": {
        "lead": "Image-led pages built around claimed alien photographs and their source material.",
        "summary": "A gallery-heavy branch best approached by browsing or direct search.",
        "start_links": [
            ("Alien photo archive", "/ufog/alien-photos"),
            ("Search photos", "/search/"),
        ],
    },
    "/ufo-history": {
        "lead": "The long-form historical reference branch: timelines, personalities, books, and the development of UFO culture and research over time.",
        "summary": "The main reference branch for chronology, bibliography, and researcher context.",
        "start_links": [
            ("UFO Timeline", "/ufo-history/ufo"),
            ("UFO Books", "/ufo-history/ufo-books"),
            ("UFO Personalities", "/ufo-history/ufo-personalities"),
        ],
    },
    "/ufo-history/ufo": {
        "lead": "A chronological reference branch covering sightings, cases, claims, reports, and media across decades.",
        "summary": "The main timeline branch for case-by-case historical browsing.",
        "start_links": [
            ("Browse by year tags", "/tags/1952/"),
            ("Search the archive", "/search/"),
        ],
    },
    "/ufo-history/ufo-books": {
        "lead": "A large bibliography and notes branch covering books relevant to UFOs, SETI, skepticism, contact claims, and adjacent topics.",
        "summary": "A deep book-reference branch with sortable tables and linked author pages.",
        "start_links": [
            ("Search books", "/search/"),
            ("Browse personalities", "/ufo-history/ufo-personalities"),
        ],
    },
    "/ufo-history/ufo-personalities": {
        "lead": "Profile pages for researchers, writers, witnesses, skeptics, and other figures that recur across the archive.",
        "summary": "A people-focused branch for context on recurring names in the archive.",
        "start_links": [
            ("Search people", "/search/"),
            ("Browse books", "/ufo-history/ufo-books"),
        ],
    },
}
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "figcaption",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def reset_output_root(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for child in output_root.iterdir():
        if child.name in PRESERVED_OUTPUT_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def excerpt(value: str | None, limit: int = 220) -> str:
    text = clean_text(strip_html(value))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def repair_mojibake(value: str) -> str:
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value
    try:
        repaired = value.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    original_score = sum(value.count(marker) for marker in MOJIBAKE_MARKERS)
    repaired_score = sum(repaired.count(marker) for marker in MOJIBAKE_MARKERS)
    return repaired if repaired_score < original_score else value


def clean_text(value: str) -> str:
    repaired = repair_mojibake(value)
    return repaired.replace("\ufeff", "").replace("\u00a0", " ")


def deep_clean(value: Any) -> Any:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [deep_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: deep_clean(item) for key, item in value.items()}
    return value


def normalize_inline_spacing(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+\]", "]", text)
    text = re.sub(r"\[\s+", "[", text)
    return text.strip()


def cleanup_markdown(text: str) -> str:
    cleaned = text.replace("\r\n", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"^\s*---\s*\n+", "", cleaned)
    cleaned = re.sub(r"(?m)^###\s*(?:\{:[^}]+\})?\s*$\n?", "", cleaned)
    cleaned = re.sub(r"\*\*<a (?:name|id)=\"([^\"]+)\"></a>(.+?)\*\*", r'<a id="\1"></a>**\2**', cleaned)
    cleaned = re.sub(r"\*\*(.+?)<a (?:name|id)=\"([^\"]+)\"></a>(.+?)\*\*", r'<a id="\2"></a>**\1\3**', cleaned)
    cleaned = re.sub(r"\*\*(.+?)<a (?:name|id)=\"([^\"]+)\"></a>\*\*", r'<a id="\2"></a>**\1**', cleaned)
    cleaned = re.sub(r"\*\*(.+?)\*\*<a (?:name|id)=\"([^\"]+)\"></a>", r'<a id="\2"></a>**\1**', cleaned)
    cleaned = re.sub(r"^(#{1,6}\s+.+?)<a (?:name|id)=\"([^\"]+)\"></a>$", r'<a id="\2"></a>' + "\n" + r"\1", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^(.*\S)\s*<a (?:name|id)=\"([^\"]+)\"></a>$", r'<a id="\2"></a>\1', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^<a (?:name|id)=\"([^\"]+)\"></a>$", r'<a id="\1"></a>', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^(#{1,6}\s+.+?)\s*\{:\s*#([^ }\n]+)\s*\}$", r'<a id="\2"></a>' + "\n" + r"\1", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^(\*\*.+?\*\*)\s*\{:\s*#([^ }\n]+)\s*\}$", r'<a id="\2"></a>\1', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\{:\s*#([^ }\n]+)\s*\}$", r'<a id="\1"></a>', cleaned, flags=re.MULTILINE)
    return cleaned.strip() + "\n"


def absolutize_schemeless_external_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("#", "/", "//")):
        return raw
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return raw
    authority = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if not authority or "." not in authority or any(char.isspace() for char in authority):
        return raw
    authority_no_port = re.sub(r":\d+$", "", authority)
    if authority_no_port.lower().endswith(NON_HOST_SUFFIXES):
        return raw
    if SCHEMELESS_EXTERNAL_HOST_PATTERN.fullmatch(authority):
        return f"http://{raw}"
    return raw


def append_fragment(route: str, fragment: str | None) -> str:
    if not fragment:
        return route
    return f"{route}#{fragment}"


def normalize_legacy_content_link(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("#", "/", "//")):
        return None

    parsed = urlparse(raw)
    if parsed.path.lower() == "search.html":
        params = parse_qs(parsed.query)
        query = (params.get("searchword") or params.get("q") or [""])[0].strip()
        if not query:
            return "/search/"
        return "/search/?" + urlencode({"q": query})

    cleaned_path = unquote(parsed.path or "").strip().lstrip("/").rstrip(" '\"")
    if not cleaned_path:
        return None

    lowered = cleaned_path.lower()
    if lowered.endswith(".html"):
        stem = cleaned_path[:-5]
        first_segment = stem.split("/", 1)[0].lower()
        if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
            base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
            remainder = stem.split("/", 1)[1] if "/" in stem else ""
            route = base_route if not remainder else f"{base_route}/{remainder}"
            return append_fragment(route, parsed.fragment)
        return append_fragment("/" + stem, parsed.fragment)

    first_segment = cleaned_path.split("/", 1)[0].lower()
    if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
        base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
        remainder = cleaned_path.split("/", 1)[1] if "/" in cleaned_path else ""
        route = base_route if not remainder else f"{base_route}/{remainder}"
        return append_fragment(route, parsed.fragment)

    return None


def normalize_local_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith(("#", "/", "//")):
        return raw
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return raw
    absolutized = absolutize_schemeless_external_url(raw)
    if absolutized != raw:
        return absolutized
    legacy_link = normalize_legacy_content_link(raw)
    if legacy_link:
        return legacy_link
    cleaned = raw.lstrip("./")
    if cleaned.startswith(LOCAL_URL_PREFIXES):
        return "/" + cleaned
    return raw


def is_local_site_path(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("#", "//")):
        return False
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return False
    cleaned = raw.lstrip("/").lstrip("./")
    return any(cleaned == prefix or cleaned.startswith(prefix + "/") for prefix in LOCAL_SITE_PREFIXES)


def local_site_path(value: str | None) -> str:
    raw = normalize_local_url(value)
    if not is_local_site_path(raw):
        return raw
    cleaned = str(raw).strip().lstrip("/").lstrip("./")
    path, suffix = re.match(r"^([^?#]*)(.*)$", cleaned).groups()  # type: ignore[union-attr]
    return "/" + path + suffix


def relative_url_expression(value: str | None) -> str:
    raw = local_site_path(value)
    if not is_local_site_path(raw):
        return raw
    path, suffix = re.match(r"^([^?#]*)(.*)$", raw).groups()  # type: ignore[union-attr]
    escaped_path = path.replace("\\", "\\\\").replace("'", "\\'")
    return "{{ '" + escaped_path + "' | relative_url }}" + suffix


def html_attr_value(value: str | None) -> str:
    rendered = str(value or "")
    if "{{" in rendered and "}}" in rendered:
        return rendered
    return html.escape(rendered, quote=True)


def should_preserve_raw_block(tag: Tag) -> bool:
    if tag.name in RAW_HTML_BLOCK_TAGS:
        return True
    if tag.name == "div":
        significant_attrs = {key for key in tag.attrs if key not in {"style", "align", "sizcache", "sizset"}}
        return bool(significant_attrs)
    if tag.name == "figure":
        significant_attrs = {key for key in tag.attrs if key not in {"style", "align"}}
        return bool(significant_attrs)
    return False


def convert_jce_caption_blocks(root: Tag | BeautifulSoup) -> None:
    for wrapper in list(root.select("div.jce_caption")):
        figure_soup = BeautifulSoup("", "lxml")
        figure = figure_soup.new_tag("figure")
        first_image = wrapper.find("img")
        if first_image is not None:
            image_copy = BeautifulSoup(str(first_image), "lxml").find("img")
            if image_copy is not None:
                figure.append(image_copy)

        text_source = BeautifulSoup(str(wrapper), "lxml")
        for image in text_source.find_all("img"):
            image.decompose()
        caption_text = normalize_inline_spacing(" ".join(text_source.stripped_strings))
        if caption_text:
            figcaption = figure_soup.new_tag("figcaption")
            figcaption.string = caption_text
            figure.append(figcaption)

        wrapper.replace_with(figure)


def mark_sortable_tables(root: Tag | BeautifulSoup) -> None:
    for table in root.find_all("table"):
        row_count = len(table.find_all("tr"))
        first_row = table.find("tr")
        column_count = len(first_row.find_all(["td", "th"], recursive=False)) if first_row else 0
        if row_count < 2 or column_count < 2:
            continue
        classes = list(table.get("class", []))
        if "sortable" not in classes:
            classes.append("sortable")
        table["class"] = classes
        table["data-sortable"] = "true"


def normalize_soup(wrapper: Tag) -> None:
    for comment in wrapper.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    convert_jce_caption_blocks(wrapper)
    mark_sortable_tables(wrapper)

    for iframe in list(wrapper.find_all("iframe")):
        src = str(iframe.get("src") or "").lower()
        if "amazon-adsystem.com/widgets" in src:
            iframe.decompose()

    for tag in list(wrapper.find_all(["span", "font"])):
        if tag.get("id") or tag.get("class"):
            continue
        tag.unwrap()

    for node in wrapper.find_all(True):
        if node.has_attr("href"):
            node["href"] = relative_url_expression(node.get("href"))
        if node.has_attr("src"):
            node["src"] = relative_url_expression(node.get("src"))

    for anchor in list(wrapper.find_all("a")):
        href = str(anchor.get("href") or "").strip()
        has_named_anchor = bool(anchor.get("name"))
        has_visible_content = bool(normalize_inline_spacing(" ".join(anchor.stripped_strings))) or anchor.find("img") is not None
        if has_named_anchor and not href and not has_visible_content:
            continue
        if not href and not has_named_anchor and not has_visible_content:
            anchor.decompose()

    for tag in list(wrapper.find_all(["div", "section", "article", "aside"])):
        if tag.get("class") or tag.get("id"):
            continue
        significant_attrs = {key for key in tag.attrs if key not in {"style", "align", "sizcache", "sizset"}}
        if significant_attrs:
            continue
        tag.unwrap()


def render_inline_markdown(node: Any) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name == "br":
        return "  \n"
    if name == "a":
        if node.get("name") and not node.get("href"):
            return f'<a id="{html.escape(str(node["name"]), quote=True)}"></a>'
        href = str(node.get("href") or "").strip()
        label = normalize_inline_spacing("".join(render_inline_markdown(child) for child in node.children)) or href
        if not href:
            return label
        return f"[{label}]({href})"
    if name == "img":
        src = str(node.get("src") or "").strip()
        if not src:
            return ""
        alt = normalize_inline_spacing(str(node.get("alt") or ""))
        if alt.lower() in {"image_needed", "image needed"}:
            alt = ""
        return f"![{alt}]({src})"
    if name in {"strong", "b"}:
        inner = normalize_inline_spacing("".join(render_inline_markdown(child) for child in node.children))
        return f"**{inner}**" if inner else ""
    if name in {"em", "i"}:
        inner = normalize_inline_spacing("".join(render_inline_markdown(child) for child in node.children))
        return f"*{inner}*" if inner else ""
    if name == "code":
        inner = "".join(node.strings).strip()
        if not inner:
            return ""
        if "`" in inner or "\n" in inner:
            return str(node)
        return f"`{inner}`"
    if name in {"sup", "sub"}:
        return str(node)
    return "".join(render_inline_markdown(child) for child in node.children)


def render_list_markdown(tag: Tag, depth: int = 0) -> str:
    lines: list[str] = []
    ordered = tag.name.lower() == "ol"
    items = [child for child in tag.children if isinstance(child, Tag) and child.name.lower() == "li"]
    for index, item in enumerate(items, start=1):
        prefix = f"{index}. " if ordered else "- "
        inline_parts: list[Any] = []
        nested_blocks: list[str] = []
        for child in item.children:
            if isinstance(child, Tag) and child.name.lower() in {"ul", "ol"}:
                nested_blocks.append(render_list_markdown(child, depth + 1))
            elif isinstance(child, Tag) and (
                should_preserve_raw_block(child)
                or child.name.lower() in {"pre", "blockquote"}
            ):
                nested_blocks.append(render_block_markdown(child))
            else:
                inline_parts.append(child)
        line_text = normalize_inline_spacing("".join(render_inline_markdown(child) for child in inline_parts))
        lines.append(("  " * depth) + prefix + line_text)
        for nested in nested_blocks:
            lines.append(textwrap.indent(nested, "  " * (depth + 1)).rstrip())
    return "\n".join(line for line in lines if line.strip())


def render_heading_markdown(tag: Tag) -> str:
    level = int(tag.name[1])
    anchor_name = None
    inline_nodes: list[Any] = []
    for child in tag.children:
        if isinstance(child, Tag) and child.name.lower() == "a" and child.get("name") and not child.get("href"):
            anchor_name = str(child.get("name"))
            continue
        inline_nodes.append(child)
    text = normalize_inline_spacing("".join(render_inline_markdown(child) for child in inline_nodes))
    heading = f"{'#' * level} {text}".rstrip()
    if anchor_name:
        heading += f" {{: #{anchor_name} }}"
    return heading


def render_figure_markdown(tag: Tag) -> str:
    image = tag.find("img")
    figcaption = tag.find("figcaption")
    parts: list[str] = []
    if image is not None:
        image_markdown = render_inline_markdown(image)
        if image_markdown:
            parts.append(image_markdown)
    caption_text = normalize_inline_spacing(figcaption.get_text(" ", strip=True)) if figcaption else ""
    if caption_text:
        parts.append(f"*{caption_text}*")
    return "\n\n".join(parts)


def render_block_markdown(node: Any) -> str:
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        text = normalize_inline_spacing(str(node))
        return text if text else ""
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if should_preserve_raw_block(node):
        return str(node)
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return render_heading_markdown(node)
    if name == "figure":
        return render_figure_markdown(node)
    if name in {"ul", "ol"}:
        return render_list_markdown(node)
    if name == "blockquote":
        inner = "\n\n".join(
            block for child in node.children if (block := render_block_markdown(child))
        )
        return "\n".join(f"> {line}" if line else ">" for line in inner.splitlines())
    if name == "pre":
        code = "".join(node.strings).strip("\n")
        return f"```\n{code}\n```" if code else ""
    if name == "hr":
        return "---"
    if name == "img":
        return render_inline_markdown(node)
    if name in {"div", "section", "article", "main", "aside", "header", "footer", "nav", "figcaption"}:
        parts = [render_block_markdown(child) for child in node.children]
        return "\n\n".join(part for part in parts if part.strip())
    text = normalize_inline_spacing("".join(render_inline_markdown(child) for child in node.children))
    return text if text else ""


def html_to_markdown_fragment(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(f"<div>{value}</div>", "lxml")
    wrapper = soup.find("div")
    if wrapper is None:
        return ""
    normalize_soup(wrapper)
    blocks = [render_block_markdown(child) for child in wrapper.children]
    return cleanup_markdown("\n\n".join(block for block in blocks if block.strip()))


def article_source_path(output_root: Path, route: str) -> Path:
    cleaned = route.strip("/")
    if not cleaned:
        return output_root / "index.md"
    return output_root / "pages" / Path(*cleaned.split("/")).with_suffix(".md")


def slugify(value: str | None, fallback: str) -> str:
    text = strip_html(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback


def page_stub_from_route(route: str, fallback: str) -> str:
    cleaned = route.strip("/")
    if not cleaned:
        return fallback
    return cleaned.replace("/", "__")


def route_search_text(route: str) -> str:
    cleaned = route.strip("/")
    if not cleaned:
        return ""
    return cleaned.replace("/", " ").replace("-", " ").replace("_", " ")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def yaml_front_matter(values: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in values.items():
        if value is None:
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def render_yaml(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def relative_asset_url(asset_ref: str | None) -> str | None:
    if not asset_ref:
        return None
    return "/" + asset_ref.lstrip("/")


def ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def is_book_route(route: str | None) -> bool:
    return str(route or "").startswith(BOOK_ROUTE_PREFIX)


def looks_like_isbn(identifier: str) -> bool:
    normalized = identifier.strip().upper()
    if len(normalized) == 10:
        return bool(re.fullmatch(r"[0-9]{9}[0-9X]", normalized))
    if len(normalized) == 13:
        return normalized.isdigit()
    return False


def extract_book_identifiers(body: str | None) -> list[str]:
    if not body:
        return []
    found: list[str] = []
    for pattern in (
        r"/dp/([A-Z0-9]{10,13})",
        r"(?:placement|asins)=([A-Z0-9,]{10,})",
    ):
        for match in re.finditer(pattern, body, flags=re.IGNORECASE):
            raw = match.group(1).upper()
            if "," in raw:
                found.extend(part for part in raw.split(",") if part)
            else:
                found.append(raw)
    return ordered_unique(found)


def local_book_cover_url(content_root: Path | None, identifier: str | list[str] | tuple[str, ...] | None) -> str | None:
    if not content_root or not identifier:
        return None
    identifiers = [identifier] if isinstance(identifier, str) else list(identifier)
    cache_root = content_root / BOOK_COVER_CACHE_ROOT
    for raw_identifier in identifiers:
        normalized = str(raw_identifier or "").strip()
        if not normalized:
            continue
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = cache_root / f"{normalized}{suffix}"
            if candidate.exists():
                return f"/book-covers/{candidate.name}"
    return None


def build_book_metadata(item: dict[str, Any], *, content_root: Path | None = None) -> dict[str, Any] | None:
    if not is_book_route(str(item.get("original_url") or "")):
        return None
    identifiers = extract_book_identifiers(item.get("body"))
    book: dict[str, Any] = {"identifiers": identifiers}
    cached_cover = local_book_cover_url(content_root, identifiers)
    if cached_cover:
        book["cover_image"] = cached_cover
        book["cover_source"] = "local-cache"
    primary_isbn = next((identifier for identifier in identifiers if looks_like_isbn(identifier)), None)
    if primary_isbn:
        book["primary_isbn"] = primary_isbn
        if not book.get("cover_image"):
            book["cover_image"] = f"https://covers.openlibrary.org/b/isbn/{primary_isbn}-L.jpg?default=false"
            book["cover_source"] = "openlibrary"
    if not book.get("cover_image"):
        book["cover_image"] = BOOK_COVER_PLACEHOLDER_URL
        book["cover_source"] = "placeholder"
    return book


def first_preview_image(item: dict[str, Any], *, content_root: Path | None = None) -> str | None:
    refs = item.get("asset_resolution", {}).get("resolved", [])
    for ref in refs:
        suffix = Path(ref).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return relative_asset_url(ref)
    book = build_book_metadata(item, content_root=content_root)
    if book and book.get("cover_image"):
        return str(book["cover_image"])
    return None


def extract_headings(body: str, limit: int = 6) -> list[str]:
    headings = re.findall(r"<h[23]\b[^>]*>(.*?)</h[23]>", body, flags=re.IGNORECASE | re.DOTALL)
    cleaned: list[str] = []
    for heading in headings:
        text = strip_html(heading)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def compact_title(title: str, limit: int = 44) -> str:
    text = strip_html(title)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def make_link_entry(title: str, url: str, short_title: str | None = None) -> dict[str, str]:
    entry = {"title": title, "permalink": url}
    if short_title:
        entry["short_title"] = short_title
    return entry


def section_editorial(route: str) -> dict[str, Any]:
    return dict(SECTION_EDITORIAL.get(route, {}))


def render_action_links(links: list[tuple[str, str]] | list[dict[str, str]] | None) -> str:
    if not links:
        return ""
    rendered: list[str] = []
    for entry in links:
        if isinstance(entry, dict):
            label = str(entry.get("label") or "").strip()
            url = str(entry.get("url") or "").strip()
        else:
            label = str(entry[0]).strip()
            url = str(entry[1]).strip()
        if not label or not url:
            continue
        rendered.append(
            f'<a class="nav-pill nav-pill-primary" href="{html_attr_value(relative_url_expression(url))}">{html.escape(label)}</a>'
        )
    if not rendered:
        return ""
    return '<div class="home-hero-actions">' + "".join(rendered) + "</div>"


def format_home_recent_date(item: dict[str, Any]) -> str | None:
    raw = clean_text(str(item.get("updated_at") or item.get("created_at") or "").strip())
    if not raw:
        return None
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
    if not match:
        return None
    try:
        parsed = datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError:
        return None
    return f"{parsed.day} {parsed.strftime('%b %Y')}"


def home_recent_bucket(route: str) -> str:
    parts = [part for part in str(route or "").split("/") if part]
    if not parts:
        return ""
    if len(parts) >= 2:
        return "/" + "/".join(parts[:2])
    return "/" + parts[0]


def select_home_recent_items(recent_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    visible = [item for item in recent_items if recent_item_is_public(item)]
    selected: list[dict[str, Any]] = []
    selected_routes: set[str] = set()
    seen_buckets: set[str] = set()

    for item in visible:
        route = str(item.get("original_url") or "").strip()
        bucket = home_recent_bucket(route) or route
        if not route or bucket in seen_buckets:
            continue
        selected.append(item)
        selected_routes.add(route)
        seen_buckets.add(bucket)
        if len(selected) >= MAX_HOME_RECENT:
            return selected

    for item in visible:
        route = str(item.get("original_url") or "").strip()
        if not route or route in selected_routes:
            continue
        selected.append(item)
        selected_routes.add(route)
        if len(selected) >= MAX_HOME_RECENT:
            break

    return selected


def recent_item_is_public(item: dict[str, Any]) -> bool:
    route = str(item.get("original_url") or "").strip().lower()
    title = str(item.get("title") or "").strip().lower()
    if not route:
        return False
    if route.startswith("/other/"):
        return False
    if route == "/uncategorised/404" or route.endswith("/404"):
        return False
    if "coming soon" in title:
        return False
    if title == "404":
        return False
    return True


def render_card(
    *,
    title: str,
    url: str,
    summary: str,
    kicker: str,
    level: int,
    preview_image: str | None = None,
    card_class: str = "",
    meta: list[str] | None = None,
) -> str:
    clean_title = clean_text(title)
    safe_title = html.escape(clean_title)
    safe_url = html_attr_value(relative_url_expression(url))
    safe_summary = html.escape(clean_text(summary))
    safe_preview_image = html_attr_value(relative_url_expression(preview_image))
    class_names = f"topic-card level-{level}"
    if card_class.strip():
        class_names += " " + card_class.strip()
    media = (
        f'<a class="topic-card-media" href="{safe_url}" title="{safe_title}">'
        f'<img src="{safe_preview_image}" alt="Preview for {safe_title}" loading="lazy" decoding="async"></a>'
        if preview_image
        else (
            f'<a class="topic-card-media topic-card-placeholder" href="{safe_url}" title="{safe_title}">'
            f'<span class="topic-card-initial">{html.escape(clean_title[:1].upper())}</span></a>'
        )
    )
    meta_html = ""
    meta_values = [clean_text(str(entry)) for entry in (meta or []) if str(entry).strip()]
    if meta_values:
        meta_html = '<p class="topic-card-meta">' + "".join(
            f"<span>{html.escape(entry)}</span>" for entry in meta_values
        ) + "</p>"
    return f"""
      <article class="{class_names}" data-level="{level}">
        <p class="topic-card-kicker">{html.escape(kicker)}</p>
        {media}
        <h3><a href="{safe_url}" title="{safe_title}">{safe_title}</a></h3>
        {meta_html}
        <p class="topic-card-summary">{safe_summary}</p>
        <a class="topic-card-link" href="{safe_url}" title="{safe_title}">Read more</a>
      </article>""".strip()


def build_tree(
    categories: list[dict[str, Any]],
    items: list[dict[str, Any]],
    *,
    allowed_top_routes: list[str] | None = None,
    allowed_section_routes: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    published_categories = [
        row
        for row in categories
        if row.get("extension") == "com_content"
        and row.get("published") in (1, "1", True)
        and str(row.get("path") or "").strip("/")
        and str(row.get("path") or "").strip("/") not in SKIP_ROOT_CATEGORY_PATHS
    ]
    category_by_path = {
        "/" + str(row["path"]).strip("/"): row
        for row in published_categories
    }
    child_categories: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for category in published_categories:
        child_categories[int(category["parent_id"])].append(category)

    for rows in child_categories.values():
        rows.sort(key=lambda row: str(row.get("title") or "").lower())

    items_by_category_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_routes = sorted(category_by_path.keys(), key=len, reverse=True)
    for item in items:
        route = str(item.get("original_url") or "")
        for category_route in category_routes:
            if route.startswith(category_route + "/"):
                items_by_category_route[category_route].append(item)
                break

    for rows in items_by_category_route.values():
        rows.sort(key=lambda row: (str(row.get("title") or "").lower(), str(row.get("original_url") or "")))

    def category_node(category: dict[str, Any]) -> dict[str, Any]:
        route = "/" + str(category["path"]).strip("/")
        node = {
            "title": str(category["title"]),
            "title_full": str(category["title"]),
            "url": route,
            "children": [],
        }
        subcategories = child_categories.get(int(category["id"]), [])
        if allowed_section_routes is not None:
            subcategories = [
                child
                for child in subcategories
                if "/" + str(child["path"]).strip("/") in allowed_section_routes
            ]
        if subcategories:
            node["children"] = [category_node(child) for child in subcategories]
        else:
            node["children"] = [
                {
                    "title": item["title"],
                    "title_full": item["title"],
                    "title_short": compact_title(item["title"], 34),
                    "url": item["original_url"],
                }
                for item in items_by_category_route.get(route, [])
            ]
        return node

    top_level_categories = child_categories.get(1, [])
    if allowed_top_routes is not None:
        route_order = {route: index for index, route in enumerate(allowed_top_routes)}
        top_level_categories = [
            category
            for category in top_level_categories
            if "/" + str(category["path"]).strip("/") in route_order
        ]
        top_level_categories.sort(
            key=lambda row: route_order["/" + str(row["path"]).strip("/")]
        )
    nav_tree = [category_node(category) for category in top_level_categories]
    return nav_tree, items_by_category_route, category_by_path


def build_category_descendant_counts(nav_tree: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    def walk(node: dict[str, Any]) -> int:
        total = 1
        for child in node.get("children", []):
            if child.get("children"):
                total += walk(child)
            else:
                total += 1
        counts[node["url"]] = total
        return total

    for node in nav_tree:
        walk(node)
    return counts


def build_footer_navigation(nav_tree: list[dict[str, Any]]) -> dict[str, Any]:
    footer_primary = [
        {"title": "Overview", "url": "/"},
        {"title": "Search", "url": "/search"},
        {"title": "Archive intro", "url": "/homepage"},
        {"title": "Tags", "url": "/tags"},
        {"title": "Sitemap", "url": "/sitemap"},
    ]
    top_sections = [
        {"title": node["title"], "url": node["url"]}
        for node in nav_tree[:8]
    ]
    return {
        "sidebar_generated": nav_tree,
        "footer_primary": footer_primary,
        "top_sections": top_sections,
    }


def find_category_for_route(
    route: str,
    category_by_route: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        category
        for category_route, category in category_by_route.items()
        if route == category_route or route.startswith(category_route + "/")
    ]
    if not matches:
        return None
    matches.sort(key=lambda row: len(str(row.get("path") or "")), reverse=True)
    return matches[0]


def iter_section_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("children"):
            collected.append(node)
            branch_children = [child for child in node.get("children", []) if child.get("children")]
            if branch_children:
                collected.extend(iter_section_nodes(branch_children))
    return collected


def build_search_index(
    *,
    items: list[dict[str, Any]],
    tags: list[dict[str, Any]],
    nav_tree: list[dict[str, Any]],
    category_by_route: dict[str, dict[str, Any]],
    descendant_counts: dict[str, int],
    content_root: Path,
) -> list[dict[str, Any]]:
    search_index: list[dict[str, Any]] = [
        {
            "kind": "overview",
            "kicker": "Overview",
            "title": SITE_TITLE,
            "title_text": SITE_TITLE,
            "url": "/",
            "url_text": "home archive overview",
            "summary": SITE_DESCRIPTION,
            "summary_text": SITE_DESCRIPTION,
            "section": "Overview",
            "section_text": "Overview",
            "tags": [],
            "tags_text": "",
            "headings_text": "",
            "body_text": "",
            "preview_image": None,
            "search_text": " ".join(
                [SITE_TITLE, SITE_SHORT_TITLE, SITE_DESCRIPTION, SITE_TAGLINE, "overview", "archive", "search"]
            ),
        }
    ]

    tag_labels_by_source: dict[str, list[str]] = defaultdict(list)
    for tag in tags:
        label = str(tag.get("label") or "").strip()
        for item in tag.get("items", []):
            source_id = str(item.get("source_id") or "").strip()
            if source_id and label and label not in tag_labels_by_source[source_id]:
                tag_labels_by_source[source_id].append(label)

    for item in items:
        route = str(item.get("original_url") or "").strip()
        if not route:
            continue
        category = find_category_for_route(route, category_by_route)
        section_title = str(category.get("title") or "Page") if category else "Page"
        explicit_tags = [
            str(label).strip()
            for label in item.get("tags", [])
            if str(label).strip()
        ]
        derived_tags = tag_labels_by_source.get(str(item.get("source_id") or ""), [])
        tag_labels = list(dict.fromkeys(explicit_tags + derived_tags))
        title = str(item.get("title") or route)
        summary = excerpt(str(item.get("summary") or item.get("body") or ""), 220)
        body_excerpt = excerpt(str(item.get("body") or ""), 420)
        headings = extract_headings(str(item.get("body") or ""), limit=6)
        route_text = route_search_text(route)
        tags_text = " ".join(tag_labels)
        headings_text = " ".join(headings)
        search_index.append(
            {
                "kind": "page",
                "kicker": "Page",
                "title": title,
                "title_text": title,
                "url": route,
                "url_text": route_text,
                "summary": summary,
                "summary_text": summary,
                "section": section_title,
                "section_text": section_title,
                "tags": tag_labels[:6],
                "tags_text": tags_text,
                "headings_text": headings_text,
                "body_text": body_excerpt,
                "preview_image": first_preview_image(item, content_root=content_root),
                "search_text": " ".join(
                    [
                        title,
                        route_text,
                        summary,
                        body_excerpt,
                        section_title,
                        tags_text,
                        headings_text,
                    ]
                ),
            }
        )

    for node in iter_section_nodes(nav_tree):
        route = str(node.get("url") or "").strip()
        if not route:
            continue
        descendant_total = max(descendant_counts.get(route, 1) - 1, 0)
        child_titles = [
            str(child.get("title_full") or child.get("title") or "").strip()
            for child in node.get("children", [])[:10]
            if str(child.get("title_full") or child.get("title") or "").strip()
        ]
        search_index.append(
            {
                "kind": "section",
                "kicker": "Section",
                "title": str(node.get("title") or route),
                "title_text": str(node.get("title") or route),
                "url": route,
                "url_text": route_search_text(route),
                "summary": f"{descendant_total} pages in this section.",
                "summary_text": f"{descendant_total} pages in this section.",
                "section": "Section",
                "section_text": "Section",
                "tags": [],
                "tags_text": "",
                "headings_text": " ".join(child_titles),
                "body_text": "",
                "preview_image": None,
                "search_text": " ".join(
                    [
                        str(node.get("title") or ""),
                        str(node.get("title_full") or ""),
                        f"{descendant_total} pages in this section",
                        " ".join(child_titles),
                    ]
                ),
            }
        )

    for tag in tags:
        label = str(tag.get("label") or "").strip()
        slug = str(tag.get("slug") or "").strip()
        if not label or not slug:
            continue
        sample_titles = [
            str(item.get("title") or "").strip()
            for item in tag.get("items", [])[:10]
            if str(item.get("title") or "").strip()
        ]
        search_index.append(
            {
                "kind": "tag",
                "kicker": "Tag",
                "title": label,
                "title_text": label,
                "url": f"/tags/{slug}/",
                "url_text": route_search_text(f"/tags/{slug}/"),
                "summary": f"{int(tag.get('count') or len(tag.get('items', [])))} tagged pages.",
                "summary_text": f"{int(tag.get('count') or len(tag.get('items', [])))} tagged pages.",
                "section": "Tags",
                "section_text": "Tags",
                "tags": [label],
                "tags_text": label,
                "headings_text": "",
                "body_text": " ".join(sample_titles),
                "preview_image": None,
                "search_text": " ".join(
                    [
                        label,
                        "tag archive",
                        " ".join(sample_titles),
                    ]
                ),
            }
        )

    return search_index


def derive_public_category_routes(public_nav: list[dict[str, Any]]) -> tuple[list[str], set[str]]:
    top_routes: list[str] = []
    section_routes: set[str] = set()
    for entry in public_nav:
        route = str(entry.get("route") or "")
        if not route or route in {"/homepage", "/tags"}:
            continue
        if route.count("/") == 1:
            if route not in top_routes:
                top_routes.append(route)
            section_routes.add(route)
            continue
        root_route = "/" + route.strip("/").split("/")[0]
        if root_route not in top_routes:
            top_routes.append(root_route)
        section_routes.add(route)
    return top_routes, section_routes


def write_config(output_root: Path, nav_tree: list[dict[str, Any]], *, site_url: str, site_baseurl: str) -> None:
    config = {
        "title": SITE_TITLE,
        "short_title": SITE_SHORT_TITLE,
        "brand_name": SITE_BRAND_NAME,
        "brand_domain": SITE_DOMAIN,
        "description": SITE_DESCRIPTION,
        "tagline": SITE_TAGLINE,
        "lang": "en",
        "locale": "en",
        "direction": "ltr",
        "visual_profile": "atlas",
        "layout_archetype": "atlas",
        "visual_palette": "signal-cobalt",
        "visual_motif": "orbital",
        "font_heading": "Manrope",
        "font_body": "Merriweather",
        "appearance_menu_enabled": True,
        "appearance_menu_default_open": False,
        "appearance_toast_ms": 5000,
        "appearance_text_default": "standard",
        "appearance_width_default": "standard",
        "appearance_color_default": "dark",
        "mobile_layout_mode": "article-first",
        "mobile_sidebar_mode": "collapsible",
        "mobile_sidebar_default": "closed",
        "endnotes_mode": "auto",
        "endnotes_collapse_threshold": 10,
        "endnotes_initial_visible": 10,
        "endnotes_show_accessed": False,
        "baseurl": site_baseurl,
        "url": site_url,
        "ui_priority": "home-first",
        "home_layout_mode": "catalog",
        "auto_home_layout_mode": "catalog",
        "hierarchy_viz_mode": "off",
        "ui_bundle_version": "isaackoi-jekyll-1",
        "theme": "minima",
        "plugins": ["jekyll-feed", "jekyll-seo-tag", "jekyll-sitemap"],
        "include": ["pages"],
        "exclude": [
            ".bundle",
            "vendor",
            "Gemfile",
            "Gemfile.lock",
            "README.md",
            "tmp",
            "node_modules",
        ],
        "defaults": [{"scope": {"path": ""}, "values": {"layout": "default"}}],
        "ui_strings": {
            "home": "Home",
            "overview": "Overview",
            "overview_prefix": "Overview:",
            "contents": "Contents",
            "close": "Close",
            "open_contents": "Open contents",
            "close_contents": "Close contents",
            "show_appearance_settings": "Show appearance settings",
            "appearance_menu_moved_here": "The appearance menu has moved here.",
            "appearance": "Appearance",
            "text": "Text",
            "small": "Small",
            "standard": "Standard",
            "large": "Large",
            "width": "Width",
            "wide": "Wide",
            "theme": "Theme",
            "automatic": "Automatic",
            "light": "Light",
            "dark": "Dark",
            "quick_navigation": "Quick navigation",
            "parent": "Parent",
            "search": "Search",
            "outline": "Outline",
            "breadcrumb": "Breadcrumb",
            "within": "Within",
            "key_sections": "Key sections",
            "inside_this_report": "On this page",
            "open_report_preview_image": "Open preview image",
            "page_outline": "Page outline",
            "jump_by_section": "Jump by section",
            "on_this_page": "On this page",
            "expand_all": "Expand all",
            "collapse_all": "Collapse all",
            "jump_to_endnotes": "Jump to endnotes",
            "back_to_top": "Back to top",
            "topic_tree": "Topic Tree",
            "follow_this_branch": "Follow this branch",
            "parent_topic": "Parent topic",
            "peer_reports": "Related pages",
            "child_reports": "More on this topic",
            "more_in_sidebar": "more in sidebar",
            "close_page_outline_panel": "Close page outline panel",
            "topic_tree_navigation": "Topic tree navigation",
            "search_this_branch": "Search this branch",
            "search_reports_in_this_branch": "Search pages in this branch...",
            "clear": "Clear",
            "expand_section": "Expand section",
            "collapse_section": "Collapse section",
            "open_report": "Read more",
            "open_topic": "Open topic",
            "open_subtopic": "Open section",
            "open_child_report": "Open page",
            "children_label": "pages",
            "branches_label": "branches",
            "primary_navigation": "Primary",
            "footer_navigation": "Footer navigation",
            "site_summary": "Site summary",
            "topic_guide": "Archive guide",
            "navigate": "Navigate",
            "browse_reports": "Browse pages",
            "main_topic": "Main section",
            "how_to_use_this_site": "How to use this site",
            "use_this_site": "Use this site",
            "footer_use_this_site_copy": "Start on the homepage, then move into sections and article pages. Use Contents and Outline when you want tighter navigation.",
            "built_for_long_form_topic_maps_and_report_collections": "Built for long-form topic maps and article collections.",
            "restore_page_outline": "Restore page outline",
            "restore_contents": "Restore contents",
            "page_outline_moved_here": "The page outline has moved here.",
            "contents_panel_moved_here": "The contents panel has moved here.",
            "switch_theme": "Switch theme",
            "follow_the_branches_from_overview_topics_to_focused_reports": "Start with the archive overview, then move into sections and individual pages.",
            "website_contents": "Site contents",
            "topics": "Sections",
            "search_panel_title": "Search",
            "open_search": "Open search",
            "close_search": "Close search",
        },
    }
    write_text(output_root / "_config.yml", "\n".join(render_yaml(config)) + "\n")


def write_public_repo_files(
    output_root: Path,
    *,
    site_url: str,
    site_baseurl: str,
    site_domain: str,
) -> None:
    sitemap_root = f"{site_url.rstrip('/')}{site_baseurl.rstrip('/')}"
    write_text(
        output_root / ".gitignore",
        "\n".join(
            [
                "_site/",
                ".jekyll-cache/",
                ".jekyll-metadata",
                ".sass-cache/",
                ".bundle/",
                "vendor/bundle/",
                "tmp/",
                "",
            ]
        ),
    )
    write_text(
        output_root / "README.md",
        textwrap.dedent(
            """\
            # Isaac Koi Archive

            This Jekyll site is the generated public-repo source for the Isaac Koi archive.

            Key paths:

            - `pages/` holds the route-based Markdown source pages
            - `images/`, `documents/`, `book-covers/`, and `assets/` hold site assets
            - `_layouts/`, `_includes/`, and `assets/` hold the Phoenix-derived theme
            - `navigation-tree.json` holds the client-side sidebar navigation tree

            Local development:

            ```powershell
            bundle install
            bundle exec jekyll serve
            ```

            Production deploys should use the GitHub Actions workflow in `.github/workflows/pages.yml`.
            """
        ),
    )
    write_text(output_root / "CNAME", f"{site_domain}\n")
    write_text(
        output_root / "robots.txt",
        "\n".join(
            [
                "User-agent: *",
                "Allow: /",
                "",
                f"Sitemap: {sitemap_root}/sitemap.xml",
                f"Host: {site_domain}",
                "",
            ]
        ),
    )
    write_text(
        output_root / "404.html",
        yaml_front_matter(
            {
                "layout": "default",
                "title": "Page Not Found",
                "permalink": "/404.html",
                "suppress_page_tools": True,
                "description": "This page could not be found in the Isaac Koi archive.",
            }
        )
        + "\n\n"
        + textwrap.dedent(
            """\
            <section class="home-hero">
              <p class="home-kicker">Archive navigation</p>
              <h1>Page not found</h1>
              <p>The requested page is not available at this address. Use the homepage, site contents, or section pages to find the archived material.</p>
              <div class="home-actions">
                <a class="button button-primary" href="{{ '/' | relative_url }}">Go to homepage</a>
                <a class="button button-secondary" href="{{ '/tags/' | relative_url }}">Browse tags</a>
              </div>
            </section>
            """
        )
        + "\n",
    )
    write_text(
        output_root / ".github" / "workflows" / "pages.yml",
        textwrap.dedent(
            """\
            name: Build And Deploy Jekyll Site

            on:
              push:
                branches: ["main"]
              workflow_dispatch:

            permissions:
              contents: read
              pages: write
              id-token: write

            concurrency:
              group: pages
              cancel-in-progress: true

            jobs:
              build:
                runs-on: ubuntu-latest
                steps:
                  - name: Checkout
                    uses: actions/checkout@v4

                  - name: Configure GitHub Pages
                    uses: actions/configure-pages@v5

                  - name: Set up Ruby
                    uses: ruby/setup-ruby@v1
                    with:
                      ruby-version: "3.2"
                      bundler-cache: true

                  - name: Build site
                    run: bundle exec jekyll build --trace

                  - name: Upload Pages artifact
                    uses: actions/upload-pages-artifact@v4
                    with:
                      path: ./_site

              deploy:
                environment:
                  name: github-pages
                  url: ${{ steps.deployment.outputs.page_url }}
                needs: build
                runs-on: ubuntu-latest
                steps:
                  - name: Deploy to GitHub Pages
                    id: deployment
                    uses: actions/deploy-pages@v4
            """
        ),
    )


def render_category_page(
    *,
    route: str,
    title: str,
    description: str,
    children: list[dict[str, Any]],
    level_kicker: str,
) -> str:
    editorial = section_editorial(route)
    total_children = len(children)
    visible_children = children[:MAX_RENDERED_CATEGORY_CARDS]
    cards = "\n".join(
        render_card(
            title=child["title"],
            url=child["url"],
            summary=child["summary"],
            kicker=child["kicker"],
            level=child["level"],
            preview_image=child.get("preview_image"),
        )
        for child in visible_children
    )
    overflow_note = ""
    if total_children > len(visible_children):
        overflow_note = (
            f'<p class="home-hierarchy-note">Showing the first {len(visible_children)} '
            f'of {total_children} pages in this section.</p>'
        )
    lead = html.escape(str(editorial.get("lead") or description))
    action_links = render_action_links(editorial.get("start_links"))
    return f"""
<section class="home-level-group">
  <div class="home-hierarchy-band-head">
    <p class="home-hierarchy-kicker">{html.escape(level_kicker)}</p>
    <h2>{html.escape(title)}</h2>
    <p>{lead}</p>
    <p>{html.escape(description)}</p>
    {action_links}
    {overflow_note}
  </div>
  <div class="topic-card-grid">
    {cards}
  </div>
</section>
""".strip()


def render_tag_page(tag: dict[str, Any]) -> str:
    total_items = len(tag["items"])
    visible_items = tag["items"][:MAX_RENDERED_TAG_CARDS]
    cards = "\n".join(
        render_card(
            title=item["title"],
            url=item["url"],
            summary=f"{item['category']} page",
            kicker="Tagged page",
            level=3,
        )
        for item in visible_items
    )
    overflow_note = ""
    if total_items > len(visible_items):
        overflow_note = (
            f'<p class="home-hierarchy-note">Showing the first {len(visible_items)} '
            f'of {total_items} tagged pages.</p>'
        )
    return f"""
<section class="home-level-group">
  <div class="home-hierarchy-band-head">
    <p class="home-hierarchy-kicker">Tag archive</p>
    <h2>{html.escape(tag['label'])}</h2>
    <p>{tag['count']} tagged pages.</p>
    {overflow_note}
  </div>
  <div class="topic-card-grid">
    {cards}
  </div>
</section>
""".strip()


def render_tag_index(tags: list[dict[str, Any]]) -> str:
    cards = "\n".join(
        render_card(
            title=tag["label"],
            url=f"/tags/{tag['slug']}/",
            summary=f"{tag['count']} related pages",
            kicker="Tag",
            level=2,
        )
        for tag in tags
    )
    return f"""
<section class="home-level-group">
  <div class="home-hierarchy-band-head">
    <p class="home-hierarchy-kicker">Tag index</p>
    <h2>Tags</h2>
    <p>Browse the recurring themes and labels derived from the archive itself.</p>
  </div>
  <div class="topic-card-grid">
    {cards}
  </div>
</section>
""".strip()


def render_search_page(total_entries: int) -> str:
    return f"""
<section class="fr-section-shell archive-search-shell" data-archive-search data-search-source="{{{{ '/search-index.json' | relative_url }}}}" data-search-page-size="{MAX_SEARCH_RESULTS_PER_QUERY}">
  <header class="fr-section-header">
    <div class="fr-section-heading">
      <p class="fr-search-kicker">Archive search</p>
      <h1 class="fr-heading">Search the archive</h1>
      <p class="fr-search-desc">Search titles, summaries, headings, tags, and section labels across {total_entries} archived entries.</p>
    </div>
    <form class="archive-search-form" role="search" data-archive-search-form>
      <label class="archive-search-label" for="archive-search-input">Keywords</label>
      <div class="archive-search-row">
        <input id="archive-search-input" class="archive-search-input" type="search" name="q" placeholder="Try 1952, Hynek, Pascagoula, or SETI" autocomplete="off" data-archive-search-input>
        <button class="nav-pill nav-pill-primary" type="submit">Search</button>
        <button class="nav-pill" type="button" data-archive-search-clear hidden>Clear</button>
      </div>
      <p class="archive-search-help">Try years, case names, authors, books, personalities, places, or recurring tags.</p>
      <p class="archive-search-status" data-archive-search-status aria-live="polite">Loading search index...</p>
    </form>
  </header>
  <div class="fr-search-grid archive-search-results" data-archive-search-results></div>
</section>
""".strip()


def render_sitemap(nav_tree: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for node in nav_tree:
        child_cards = []
        for child in node.get("children", []):
            child_cards.append(
                render_card(
                    title=child["title"],
                    url=child["url"],
                    summary=child.get("title_full", child["title"]),
                    kicker="Section" if child.get("children") else "Page",
                    level=2 if child.get("children") else 3,
                )
            )
        blocks.append(
            f"""
<section class="home-level-group">
  <div class="home-hierarchy-band-head">
    <p class="home-hierarchy-kicker">Sitemap section</p>
    <h2>{html.escape(node['title'])}</h2>
  </div>
  <div class="topic-card-grid">
    {''.join(child_cards)}
  </div>
</section>
""".strip()
        )
    return "\n\n".join(blocks)


def render_home_page(
    *,
    nav_tree: list[dict[str, Any]],
    recent_items: list[dict[str, Any]],
    intro_item: dict[str, Any] | None,
    descendant_counts: dict[str, int],
    category_by_route: dict[str, dict[str, Any]],
    content_root: Path,
) -> str:
    intro_text = HOME_INTRO_COPY
    top_sections_html: list[str] = []
    for node in nav_tree:
        editorial = section_editorial(str(node["url"]))
        root_summary = f"{descendant_counts.get(node['url'], 1) - 1} pages across this section."
        root_card = render_card(
            title=node["title"],
            url=node["url"],
            summary=str(editorial.get("summary") or root_summary),
            kicker="Section",
            level=1,
        )
        child_cards = []
        for child in node.get("children", []):
            child_editorial = section_editorial(str(child["url"]))
            child_cards.append(
                render_card(
                    title=child["title"],
                    url=child["url"],
                    summary=str(child_editorial.get("summary") or child.get("title_full", child["title"])),
                    kicker="Subsection" if child.get("children") else "Page",
                    level=2 if child.get("children") else 3,
                )
            )
        group_lead = html.escape(
            str(editorial.get("lead") or root_summary)
        )
        group_actions = render_action_links(editorial.get("start_links"))
        section_cards = "".join(child_cards) if child_cards else root_card
        section_cards_class = "topic-card-grid topic-card-grid-subtopic home-topic-section-grid"
        if not child_cards:
            section_cards_class = "topic-card-grid home-topic-root-grid"
        top_sections_html.append(
            f"""
<section class="home-level-group home-topic-group">
  <details class="home-level-disclosure home-topic-disclosure" open>
    <summary class="home-level-summary">
      <span class="home-level-summary-title">{html.escape(node['title'])}</span>
      <span class="home-level-summary-count">{max(descendant_counts.get(node['url'], 1) - 1, 0)} pages</span>
    </summary>
    <div class="home-hierarchy-band-head">
      <p>{group_lead}</p>
      {group_actions}
    </div>
    <div class="{section_cards_class}">{section_cards}</div>
  </details>
</section>
""".strip()
        )
    recent_visible = select_home_recent_items(recent_items)
    featured_recent = recent_visible[0] if recent_visible else None
    remaining_recent = recent_visible[1:]

    def render_recent_card(item: dict[str, Any], *, featured: bool = False) -> str:
        route = str(item.get("original_url") or "").strip()
        category = find_category_for_route(route, category_by_route)
        meta: list[str] = []
        if category:
            meta.append(str(category.get("title") or "").strip())
        elif route == "/homepage":
            meta.append("Archive introduction")
        date_label = format_home_recent_date(item)
        if date_label:
            meta.append(date_label)
        return render_card(
            title=str(item.get("title") or "Untitled page"),
            url=route,
            summary=excerpt(item.get("summary"), 220 if featured else 140),
            kicker="Recent highlight" if featured else "Recently updated",
            level=3,
            preview_image=first_preview_image(item, content_root=content_root),
            card_class="topic-card-featured home-recent-featured-card" if featured else "home-recent-card",
            meta=meta,
        )

    recent_feature_html = render_recent_card(featured_recent, featured=True) if featured_recent else ""
    recent_stack_html = "\n".join(render_recent_card(item) for item in remaining_recent)
    intro_link = (
        f'<a class="topic-card-link home-hero-intro-link" href="{html_attr_value(relative_url_expression(intro_item["original_url"]))}">Read the archive introduction</a>'
        if intro_item
        else ""
    )
    search_link = f'<a class="nav-pill nav-pill-primary" href="{html_attr_value(relative_url_expression("/search"))}">Search the archive</a>'
    starter_link = f'<a class="nav-pill" href="{html_attr_value(relative_url_expression("/ufog/starter-pack"))}">Start with the Starter Pack</a>'
    cases_link = f'<a class="nav-pill" href="{html_attr_value(relative_url_expression("/ufog/best-ufo-cases"))}">Browse best UFO cases</a>'
    archive_page_total = sum(max(descendant_counts.get(node["url"], 1) - 1, 0) for node in nav_tree)
    hero_route_chips = "".join(f"<span>{html.escape(label)}</span>" for label in HOME_HERO_ROUTE_CHIPS)
    hero_topic_links = "".join(
        f'<a class="home-hero-topic" href="{html_attr_value(relative_url_expression(url))}">{html.escape(label)}</a>'
        for label, url in HOME_HERO_TOPIC_LINKS
    )
    return f"""
<section class="home-hero">
  <div class="home-hero-copy">
    <p class="home-eyebrow">Isaac Koi Archive</p>
    <div class="home-platform-badge">
      <span class="home-platform-mark" aria-hidden="true">
        <svg viewBox="0 0 64 64" role="img" focusable="false">
          <circle cx="32" cy="32" r="11" fill="currentColor" opacity="0.18"></circle>
          <circle cx="32" cy="32" r="6" fill="currentColor"></circle>
          <ellipse cx="32" cy="32" rx="22" ry="10.5" fill="none" stroke="currentColor" stroke-width="3.2"></ellipse>
          <path d="M15 21c7.2 4.2 26.8 4.2 34 0" fill="none" stroke="currentColor" stroke-width="2.6" opacity="0.42"></path>
        </svg>
      </span>
      <div class="home-platform-copy">
        <p class="home-platform-label">Public research archive</p>
        <p class="home-platform-domain"><span class="home-platform-name">{html.escape(SITE_DOMAIN)}</span></p>
      </div>
    </div>
    <p class="home-platform-note">Structured routes into cases, books, timelines, personalities, and reference material collected from the Isaac Koi archive.</p>
    <h1>{html.escape(HOME_HERO_TITLE)}</h1>
    <p class="home-hero-lead">{html.escape(intro_text)}</p>
    <div class="home-hero-route">
      {hero_route_chips}
    </div>
    <div class="home-hero-actions">
      {search_link}
      {starter_link}
      {cases_link}
      {intro_link}
    </div>
  </div>
  <aside class="home-hero-stage" aria-label="Archive overview">
    <p class="home-hero-stage-kicker">Start with</p>
    <div class="home-hero-topics">
      <p class="home-hero-topics-label">Popular routes</p>
      <div class="home-hero-topic-list">
        {hero_topic_links}
      </div>
    </div>
    <div class="home-stats">
      <div class="home-stat"><strong>{archive_page_total}</strong><span class="home-stat-label">Public pages</span></div>
      <div class="home-stat"><strong>{len(nav_tree)}</strong><span class="home-stat-label">Main branches</span></div>
      <div class="home-stat"><strong>{len(HOME_HERO_TOPIC_LINKS)}</strong><span class="home-stat-label">Quick routes</span></div>
      <div class="home-stat"><strong>{len(recent_visible)}</strong><span class="home-stat-label">Fresh picks</span></div>
    </div>
    <p class="home-hero-stage-note">Search is the fastest route if you already know a surname, year, case label, or book title. The branch cards below are better when you want to browse deliberately.</p>
  </aside>
</section>

<section class="home-level-group home-browse-lead">
  <div class="home-hierarchy-band-head">
    <div>
      <p class="home-hierarchy-kicker">Browse by branch</p>
      <h2>Choose a route through the archive</h2>
    </div>
    <p class="home-browse-lead-copy">The archive is split into a practical UFO branch and a larger historical reference branch. Each one exposes its best entry points directly.</p>
  </div>
</section>

<section id="browse-reports" class="home-mode-panel is-active" data-home-mode-panel="catalog" data-home-mode-label="Catalog">
  {''.join(top_sections_html)}
</section>

<section class="home-level-group home-recent-section">
  <div class="home-hierarchy-band-head">
    <p class="home-hierarchy-kicker">Recently updated</p>
    <h2>Recent highlights</h2>
    <p>A smaller, more varied sample of visible additions and updates across the archive.</p>
  </div>
  <div class="home-recent-grid">
    <div class="home-recent-feature">
      {recent_feature_html}
    </div>
    <div class="home-recent-stack">
      {recent_stack_html}
    </div>
  </div>
</section>
""".strip()


def build_breadcrumbs(
    route: str,
    category_by_route: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, str]], str | None, str | None]:
    breadcrumb_links: list[dict[str, str]] = []
    parent_permalink = None
    parent_title = None
    segments = route.strip("/").split("/")
    if len(segments) <= 1:
        return breadcrumb_links, parent_permalink, parent_title
    current_parts: list[str] = []
    for segment in segments[:-1]:
        current_parts.append(segment)
        candidate = "/" + "/".join(current_parts)
        category = category_by_route.get(candidate)
        if not category:
            continue
        breadcrumb_links.append(make_link_entry(str(category["title"]), candidate, compact_title(str(category["title"]))))
    if breadcrumb_links:
        parent_permalink = breadcrumb_links[-1]["permalink"]
        parent_title = breadcrumb_links[-1]["title"]
    return breadcrumb_links, parent_permalink, parent_title


def article_sibling_links(
    item: dict[str, Any],
    items_in_category: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if len(items_in_category) <= 1:
        return []
    index = next((i for i, row in enumerate(items_in_category) if row["source_id"] == item["source_id"]), 0)
    start = max(0, index - MAX_SIBLING_LINKS // 2)
    end = min(len(items_in_category), start + MAX_SIBLING_LINKS)
    start = max(0, end - MAX_SIBLING_LINKS)
    subset = [row for row in items_in_category[start:end] if row["source_id"] != item["source_id"]]
    return [make_link_entry(row["title"], row["original_url"], compact_title(row["title"])) for row in subset]


def category_child_links(
    children: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> list[dict[str, str]]:
    visible_children = children if limit is None else children[:limit]
    return [
        make_link_entry(child["title"], child["url"], compact_title(child["title"]))
        for child in visible_children
    ]


def copy_theme_source(template_root: Path, output_root: Path) -> None:
    for relative in ("_includes", "_layouts", "assets", "favicon.svg", "Gemfile"):
        source = template_root / relative
        destination = output_root / relative
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def copy_content_assets(content_root: Path, output_root: Path) -> int:
    assets_root = content_root / "assets" / "source"
    copied = 0
    if not assets_root.exists():
        return copied
    for child in assets_root.iterdir():
        destination = output_root / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, destination)
        copied += 1
    return copied


def normalize_route_prefixes(route_prefixes: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not route_prefixes:
        return ()
    normalized: list[str] = []
    for prefix in route_prefixes:
        cleaned = "/" + str(prefix).strip().strip("/")
        if cleaned == "/":
            return ()
        normalized.append(cleaned)
    return tuple(dict.fromkeys(normalized))


def route_matches_prefixes(route: str, route_prefixes: tuple[str, ...]) -> bool:
    if not route_prefixes:
        return True
    return any(route == prefix or route.startswith(prefix + "/") for prefix in route_prefixes)


def build_site(
    *,
    content_root: Path,
    output_root: Path,
    template_root: Path,
    route_prefixes: list[str] | tuple[str, ...] | None = None,
    limit_items: int | None = None,
    site_url: str = SITE_URL,
    site_baseurl: str = "",
) -> dict[str, int]:
    meta_root = content_root / "_meta"
    normalized_route_prefixes = normalize_route_prefixes(route_prefixes)
    items = [
        item
        for item in deep_clean(load_json(meta_root / "content-manifest.json"))
        if item.get("status") == "published" and item.get("original_url")
        and not any(str(item.get("original_url")).startswith(prefix) for prefix in SKIP_ITEM_ROUTE_PREFIXES)
    ]
    if normalized_route_prefixes:
        items = [
            item
            for item in items
            if route_matches_prefixes(str(item["original_url"]), normalized_route_prefixes)
        ]
    if limit_items is not None:
        items = items[: max(limit_items, 0)]
    categories = deep_clean(load_json(meta_root / "category-index.json"))
    raw_tags = deep_clean(load_json(meta_root / "tags-index.json"))
    homepage_intent = deep_clean(load_json(meta_root / "homepage-intent.json"))
    public_nav = deep_clean(load_json(meta_root / "public-nav.json"))
    included_source_ids = {item["source_id"] for item in items}
    tags: list[dict[str, Any]] = []
    for tag in raw_tags:
        filtered_items = [item for item in tag.get("items", []) if item.get("source_id") in included_source_ids]
        if not filtered_items:
            continue
        tag_copy = dict(tag)
        tag_copy["items"] = filtered_items
        tag_copy["count"] = len(filtered_items)
        tags.append(tag_copy)

    top_routes, section_routes = derive_public_category_routes(public_nav)
    nav_tree, items_by_category_route, category_by_route = build_tree(
        categories,
        items,
        allowed_top_routes=top_routes,
        allowed_section_routes=section_routes,
    )
    descendant_counts = build_category_descendant_counts(nav_tree)

    reset_output_root(output_root)
    copy_theme_source(template_root, output_root)
    copied_asset_roots = copy_content_assets(content_root, output_root)
    write_config(output_root, nav_tree, site_url=site_url, site_baseurl=site_baseurl)
    write_public_repo_files(
        output_root,
        site_url=site_url,
        site_baseurl=site_baseurl,
        site_domain=SITE_DOMAIN,
    )
    write_text(output_root / "_data" / "navigation.json", json.dumps(build_footer_navigation(nav_tree), indent=2))
    write_text(output_root / "navigation-tree.json", json.dumps(nav_tree, indent=2))
    search_index = build_search_index(
        items=items,
        tags=tags,
        nav_tree=nav_tree,
        category_by_route=category_by_route,
        descendant_counts=descendant_counts,
        content_root=content_root,
    )
    write_text(
        output_root / "search-index.json",
        json.dumps(search_index, indent=2, ensure_ascii=False),
    )

    items_by_route = {item["original_url"]: item for item in items}
    intro_item = items_by_route.get("/homepage")
    recent_items = sorted(
        items,
        key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )[: MAX_HOME_RECENT * 10]

    write_text(
        output_root / "index.html",
        yaml_front_matter(
            {
                "layout": "default",
                "title": SITE_TITLE,
                "permalink": "/",
                "home": True,
                "suppress_page_tools": True,
                "description": SITE_DESCRIPTION,
            }
        )
        + "\n\n"
        + render_home_page(
            nav_tree=nav_tree,
            recent_items=recent_items,
            intro_item=intro_item,
            descendant_counts=descendant_counts,
            category_by_route=category_by_route,
            content_root=content_root,
        )
        + "\n",
    )
    write_text(
        output_root / "pages" / "search.html",
        yaml_front_matter(
            {
                "layout": "default",
                "title": "Search",
                "permalink": "/search/",
                "suppress_page_tools": True,
                "description": "Search titles, sections, tags, and page summaries across the Isaac Koi archive.",
            }
        )
        + "\n\n"
        + render_search_page(len(search_index))
        + "\n",
    )

    category_pages = 0
    for node in nav_tree:
        top_category = category_by_route[node["url"]]
        child_entries = []
        for child in node.get("children", []):
            child_item = items_by_route.get(child["url"])
            child_editorial = section_editorial(str(child["url"]))
            child_entries.append(
                {
                    "title": child["title"],
                    "url": child["url"],
                    "summary": excerpt(
                        str(
                            child_editorial.get("summary")
                            or (child_item.get("summary") if child_item else child.get("title_full", child["title"]))
                        ),
                        180,
                    ),
                    "kicker": "Subsection" if child.get("children") else "Page",
                    "level": 2 if child.get("children") else 3,
                        "preview_image": first_preview_image(child_item, content_root=content_root) if child_item else None,
                }
            )
        route = node["url"]
        write_text(
            output_root / "pages" / f"category-{page_stub_from_route(route, 'root')}.html",
            yaml_front_matter(
                {
                    "layout": "default",
                    "title": top_category["title"],
                    "description": f"{max(descendant_counts.get(route, 1) - 1, 0)} pages in this section.",
                    "permalink": route + "/",
                    "suppress_page_tools": True,
                    "display_title_short": compact_title(str(top_category["title"])),
                    "child_links": category_child_links(child_entries, limit=MAX_CATEGORY_CHILD_LINKS),
                    "child_links_total": len(child_entries),
                }
            )
            + "\n\n"
            + render_category_page(
                route=route,
                title=str(top_category["title"]),
                description=f"{max(descendant_counts.get(route, 1) - 1, 0)} pages in this section.",
                children=child_entries,
                level_kicker="Section",
            )
            + "\n",
        )
        category_pages += 1

        for child in node.get("children", []):
            if not child.get("children"):
                continue
            sub_route = child["url"]
            sub_category = category_by_route[sub_route]
            article_entries = []
            for article in items_by_category_route.get(sub_route, []):
                article_entries.append(
                    {
                        "title": article["title"],
                        "url": article["original_url"],
                        "summary": excerpt(article.get("summary"), 180),
                        "kicker": "Page",
                        "level": 3,
                        "preview_image": first_preview_image(article, content_root=content_root),
                    }
                )
            write_text(
                output_root / "pages" / f"category-{page_stub_from_route(sub_route, 'section')}.html",
                yaml_front_matter(
                    {
                        "layout": "default",
                        "title": sub_category["title"],
                        "description": f"{len(article_entries)} pages in this subsection.",
                        "permalink": sub_route + "/",
                        "suppress_page_tools": True,
                        "display_title_short": compact_title(str(sub_category["title"])),
                        "parent_permalink": route,
                        "parent_title": top_category["title"],
                        "breadcrumb_links": [make_link_entry(str(top_category["title"]), route, compact_title(str(top_category["title"])))],
                        "child_links": category_child_links(article_entries, limit=MAX_CATEGORY_CHILD_LINKS),
                        "child_links_total": len(article_entries),
                    }
                )
                + "\n\n"
                + render_category_page(
                    route=sub_route,
                    title=str(sub_category["title"]),
                    description=f"{len(article_entries)} pages in this subsection.",
                    children=article_entries,
                    level_kicker="Subsection",
                )
                + "\n",
            )
            category_pages += 1

    article_pages = 0
    for item in items:
        route = item["original_url"]
        book_metadata = build_book_metadata(item, content_root=content_root)
        category_route = None
        for candidate, rows in items_by_category_route.items():
            if any(row["source_id"] == item["source_id"] for row in rows):
                category_route = candidate
                break
        breadcrumb_links, parent_permalink, parent_title = build_breadcrumbs(route, category_by_route)
        sibling_links = article_sibling_links(item, items_by_category_route.get(category_route, [])) if category_route else []
        front_matter = {
            "layout": "default",
            "title": item["title"],
            "description": excerpt(item.get("summary"), 240),
            "permalink": route + "/",
            "display_title_short": compact_title(item["title"]),
            "nav_short_title": compact_title(item["title"]),
            "breadcrumb_links": breadcrumb_links,
            "parent_permalink": parent_permalink,
            "parent_title": parent_title,
            "sibling_links": sibling_links,
            "planned_sections": extract_headings(item.get("body", ""))[:MAX_PLANNED_SECTIONS],
            "header": {"preview_image": first_preview_image(item, content_root=content_root)},
        }
        if book_metadata:
            front_matter["book"] = book_metadata
        body_markdown = html_to_markdown_fragment(item.get("body", ""))
        write_text(
            article_source_path(output_root, route),
            yaml_front_matter(front_matter) + "\n\n" + body_markdown,
        )
        article_pages += 1

    tag_pages = 0
    write_text(
        output_root / "pages" / "tags-index.html",
        yaml_front_matter(
            {
                "layout": "default",
                "title": "Tags",
                "description": "Browse the derived tag index across the Isaac Koi archive.",
                "permalink": "/tags/",
                "suppress_page_tools": True,
            }
        )
        + "\n\n"
        + render_tag_index(tags)
        + "\n",
    )
    tag_pages += 1
    for tag in tags:
        write_text(
            output_root / "pages" / "tags" / f"{tag['slug']}.html",
            yaml_front_matter(
                {
                    "layout": "default",
                    "title": f"Tag: {tag['label']}",
                    "description": f"{tag['count']} pages tagged {tag['label']}.",
                    "permalink": f"/tags/{tag['slug']}/",
                    "suppress_page_tools": True,
                    "parent_permalink": "/tags",
                    "parent_title": "Tags",
                }
            )
            + "\n\n"
            + render_tag_page(tag)
            + "\n",
        )
        tag_pages += 1

    write_text(
        output_root / "pages" / "sitemap.html",
        yaml_front_matter(
            {
                "layout": "default",
                "title": "Sitemap",
                "description": "Structured navigation across the Isaac Koi archive.",
                "permalink": "/sitemap/",
                "suppress_page_tools": True,
            }
        )
        + "\n\n"
        + render_sitemap(nav_tree)
        + "\n",
    )

    return {
        "article_pages": article_pages,
        "category_pages": category_pages,
        "tag_pages": tag_pages,
        "copied_asset_roots": copied_asset_roots,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Jekyll source tree from extracted Joomla content.")
    parser.add_argument("--content-root", type=Path, default=Path("content"))
    parser.add_argument("--output-root", type=Path, default=Path("jekyll-site"))
    parser.add_argument("--template-root", type=Path, default=Path("templates/jekyll-phoenix-theme"))
    parser.add_argument("--site-url", default=SITE_URL, help="Canonical site URL for Jekyll absolute URLs.")
    parser.add_argument("--baseurl", default="", help="Jekyll baseurl, e.g. /isaackoi.com for repo-scoped GitHub Pages.")
    parser.add_argument("--route-prefix", action="append", default=[], help="Only include pages under this route prefix, e.g. /ufog or /ufo-history/ufo-books")
    parser.add_argument("--limit-items", type=int, default=None, help="Limit the number of exported article pages after filtering.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_site(
        content_root=args.content_root.resolve(),
        output_root=args.output_root.resolve(),
        template_root=args.template_root.resolve(),
        route_prefixes=args.route_prefix,
        limit_items=args.limit_items,
        site_url=args.site_url,
        site_baseurl=args.baseurl,
    )
    print(
        f"Built Jekyll source with {result['article_pages']} article pages, "
        f"{result['category_pages']} category pages, {result['tag_pages']} tag pages, and "
        f"{result['copied_asset_roots']} copied asset roots into {args.output_root.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
