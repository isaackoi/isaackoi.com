from __future__ import annotations

import argparse
import bz2
import shutil
import gzip
import json
import os
import re
import struct
import sys
import zlib
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import unescape
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse


ASSET_PATTERN = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"'#?]+(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)
RELATIVE_LINK_HREF_PATTERN = re.compile(
    r'href=(["\'])(?!https?://|mailto:|/|#)(.*?)\1',
    re.IGNORECASE,
)
ABSOLUTE_INTERNAL_HTML_LINK_PATTERN = re.compile(
    r'href=(["\'])(https?://(?:www\.)?isaackoi\.com/[^"\']+\.html)(#[^"\']*)?\1',
    re.IGNORECASE,
)
LOCAL_FILE_LINK_PATTERN = re.compile(
    r"<a\b(?P<before>[^>]*?)href=(?P<quote>[\"'])(?P<href>file:(?:/{2,3})?[^\"']+)"
    r"(?P=quote)(?P<after>[^>]*)>(?P<label>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
LOCAL_FILE_IMAGE_PATTERN = re.compile(
    r"<img\b[^>]*src=(?:[\"'])file:(?:/{2,3})?[^\"']+(?:[\"'])[^>]*>",
    re.IGNORECASE,
)
CONTEXT_LINK_HREF_PATTERN = re.compile(
    r'href=(["\'])([^"\']+)\1',
    re.IGNORECASE,
)
ARTICLE_INCLUDE_PATTERN = re.compile(
    r"\{article\s+(\d+)\}\{text\}\{/article\}",
    re.IGNORECASE,
)
SCRIPT_TAG_PATTERN = re.compile(
    r"<script\b[^>]*>.*?</script>",
    re.IGNORECASE | re.DOTALL,
)
NAMESPACED_TAG_PATTERN = re.compile(
    r"</?[a-zA-Z0-9_]+:[^>]+>",
    re.IGNORECASE,
)
GOOGLE_HIGHLIGHT_SPAN_PATTERN = re.compile(
    r'<span\b[^>]*id="google-navclient-highlight"[^>]*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
TAG_LINK_PATTERN = re.compile(r'href="/tags/([^"#?]+)"', re.IGNORECASE)
STRIP_TAGS_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
MOJIBAKE_MARKERS = ("â", "Ã", "Â", "�")
ASSET_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
    ".7z",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".css",
    ".js",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}
ASSET_PATH_HINTS = ("images/", "media/", "documents/", "docs/", "files/", "images\\")
BARE_EXTERNAL_LINK_PATTERN = re.compile(
    r"^[a-z0-9-]+(?:\.[a-z0-9-]+){2,}(?:/.*)?$",
    re.IGNORECASE,
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
TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")
LOCAL_FILE_LINK_TEXT_LOOKUP = {
    "out of the shadows": "/ufo-history/ufo-books/clarke-david-and-roberts-andy-out-of-the-shadows",
    "schmitt, donald": "/ufo-history/ufo-personalities/schmitt-donald-r",
    "donald schmitt": "/ufo-history/ufo-personalities/schmitt-donald-r",
    "john g fuller": "/ufo-history/ufo-personalities/fuller-john-g",
}
LOCAL_FILE_LINK_PATH_LOOKUP = {
    "schmitt, donald r": "/ufo-history/ufo-personalities/schmitt-donald-r",
}
LOCAL_FILE_LINK_AUTHOR_TITLE_LOOKUP = {
    ("stranges-frank", "the ufo conspiracy"): "/ufo-history/ufo-books/stranges-frank-the-ufo-conspiracy",
    ("randles-jenny", "the ufo conspiracy"): "/ufo-history/ufo-books/randles-jenny-the-ufo-conspiracy",
}
LEGACY_LINK_ALIAS_LOOKUP = {
    "best-ufo-cases/27-quantitative-criteria-kois-card-ratings.html":
        "best-ufo-cases/27-quantitative-criteria-kois-ices-ratings.html",
    "ufo-books/bergier-jaques-extraterrestrial-visitations-from-prehistoric-times-to-the-present.html":
        "ufo-books/bergier-jacques-extraterrestrial-visitations-from-prehistoric-times-to-the-present.html",
    "ufo-history-guides/polls.html": "ufo/19910000-roper-abduction-polls.html",
    "ufo-personalities/friend-robert-f.html": "ufo-personalities/friend-robert-j.html",
    "ufo-personalities/wilkins-harold-t.html": "ufo-personalities/wilkins-harold.html",
    "ufo-personalities/wilson-katharina.html": "ufo-personalities/wilson-k.html",
    "sitemap.html": "/sitemap",
}
INTENTIONALLY_OMITTED_ASSET_REFS = {
    "images/stories/alien_photos/koi_ap_17_d.jpg",
    "images/stories/alien_photos/koi_ap_66_bREMOVEDASTHISSHOWSADEADBODY.jpg",
}


@dataclass
class ExtractionResult:
    items: list[dict[str, Any]]
    redirects: list[dict[str, Any]]
    report: dict[str, Any]
    meta: dict[str, Any]


@dataclass
class LoadResult:
    tables: dict[str, list[dict[str, Any]]]
    parse_errors: dict[str, int]


@dataclass
class JPAEntry:
    path: str
    entity_type: int
    compression_type: int
    compressed_size: int
    uncompressed_size: int
    permissions: int
    data_offset: int


@dataclass
class JPAArchiveIndex:
    archives: list[Path]
    entries: dict[str, JPAEntry]

    @property
    def file_count(self) -> int:
        return len(self.entries)


def sql_backslash_escaped(text: str, index: int) -> bool:
    backslash_count = 0
    lookbehind = index - 1
    while lookbehind >= 0 and text[lookbehind] == "\\":
        backslash_count += 1
        lookbehind -= 1
    return backslash_count % 2 == 1


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    index = 0

    while index < len(sql_text):
        char = sql_text[index]
        current.append(char)
        if char == "'":
            if in_string:
                if index + 1 < len(sql_text) and sql_text[index + 1] == "'":
                    current.append(sql_text[index + 1])
                    index += 2
                    continue
                if not sql_backslash_escaped(sql_text, index):
                    in_string = False
            else:
                in_string = True
        if char == ";" and not in_string:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        index += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def iter_sql_insert_statements(path: Path) -> Any:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        collecting = False
        current: list[str] = []
        for line in handle:
            stripped = line.lstrip()
            if not collecting:
                if not stripped.upper().startswith("INSERT INTO"):
                    continue
                collecting = True
                current = [line]
            else:
                current.append(line)

            if line.rstrip().endswith(";"):
                yield "".join(current).strip()
                collecting = False
                current = []

        if collecting and current:
            yield "".join(current).strip()


def split_sql_rows(values_block: str) -> list[str]:
    rows: list[str] = []
    current: list[str] = []
    in_string = False
    depth = 0
    index = 0

    while index < len(values_block):
        char = values_block[index]
        if depth == 0 and char in ", \n\r\t":
            index += 1
            continue
        current.append(char)
        if char == "'":
            if in_string:
                if index + 1 < len(values_block) and values_block[index + 1] == "'":
                    current.append(values_block[index + 1])
                    index += 2
                    continue
                if not sql_backslash_escaped(values_block, index):
                    in_string = False
            else:
                in_string = True
        if in_string:
            index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                row = "".join(current).strip()
                if row.startswith("(") and row.endswith(")"):
                    rows.append(row[1:-1])
                current = []
        index += 1
    return rows


def split_row_values(row_text: str) -> list[str]:
    values: list[str] = []
    current: list[str] = []
    in_string = False
    index = 0

    while index < len(row_text):
        char = row_text[index]
        if char == "," and not in_string:
            values.append("".join(current).strip())
            current = []
            index += 1
            continue
        if char == "'":
            current.append(char)
            if in_string:
                if index + 1 < len(row_text) and row_text[index + 1] == "'":
                    current.append(row_text[index + 1])
                    index += 2
                    continue
                if not sql_backslash_escaped(row_text, index):
                    in_string = False
            else:
                in_string = True
            index += 1
            continue
        current.append(char)
        index += 1

    values.append("".join(current).strip())
    return values


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


def decode_sql_string(inner: str) -> str:
    pieces: list[str] = []
    index = 0
    while index < len(inner):
        char = inner[index]
        if char == "\\" and index + 1 < len(inner):
            next_char = inner[index + 1]
            pieces.append(
                {
                    "r": "\r",
                    "n": "\n",
                    "t": "\t",
                    "'": "'",
                    '"': '"',
                    "\\": "\\",
                    "0": "\0",
                }.get(next_char, next_char)
            )
            index += 2
            continue
        if char == "'" and index + 1 < len(inner) and inner[index + 1] == "'":
            pieces.append(char)
            index += 2
            continue
        pieces.append(char)
        index += 1
    return repair_mojibake("".join(pieces))


def decode_sql_value(value: str) -> Any:
    if value.upper() == "NULL":
        return None
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return decode_sql_string(value[1:-1])
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_insert_statement(statement: str) -> tuple[str, list[dict[str, Any]]] | None:
    normalized = statement.strip()
    if not normalized.upper().startswith("INSERT INTO"):
        return None

    match = re.match(
        r"INSERT INTO\s+[`\"]?([^`\"\s]+)[`\"]?\s*\((.*?)\)\s*VALUES\s*(.*)",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    table_name, column_block, values_block = match.groups()
    columns = [column.strip().strip("`\"") for column in column_block.split(",")]
    rows = split_sql_rows(values_block)
    records: list[dict[str, Any]] = []
    for row in rows:
        raw_values = split_row_values(row)
        if len(raw_values) != len(columns):
            raise ValueError(
                f"Column count mismatch for {table_name}: {len(columns)} columns, "
                f"{len(raw_values)} values"
            )
        record = {
            column: decode_sql_value(raw_value)
            for column, raw_value in zip(columns, raw_values, strict=True)
        }
        records.append(record)
    return table_name, records


def read_sql_text(path: Path) -> str:
    if path.suffix.lower() == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="replace")


def identify_insert_table(statement: str) -> str:
    match = re.match(r"INSERT INTO\s+[`\"]?([^`\"\s]+)", statement.strip(), flags=re.IGNORECASE)
    return match.group(1).lower() if match else "unknown"


def load_sql_records(db_root: Path) -> LoadResult:
    tables: dict[str, list[dict[str, Any]]] = defaultdict(list)
    parse_errors: dict[str, int] = defaultdict(int)
    sql_files = sorted(
        path for path in db_root.rglob("*") if path.suffix.lower() in {".sql", ".gz"}
    )
    for sql_file in sql_files:
        for statement in iter_sql_insert_statements(sql_file):
            try:
                parsed = parse_insert_statement(statement)
            except ValueError:
                parse_errors[identify_insert_table(statement)] += 1
                continue
            if not parsed:
                continue
            table_name, records = parsed
            tables[table_name.lower()].extend(records)
    return LoadResult(tables=dict(tables), parse_errors=dict(parse_errors))


def detect_joomla_prefix(table_names: list[str]) -> str | None:
    candidates = [name[: -len("_content")] for name in table_names if name.endswith("_content")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda value: (len(value), value))[0]


def select_core_tables(raw_tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    prefix = detect_joomla_prefix(list(raw_tables.keys()))
    if not prefix:
        return {}

    mapping = {
        "content": f"{prefix}_content",
        "categories": f"{prefix}_categories",
        "users": f"{prefix}_users",
        "menu": f"{prefix}_menu",
        "content_frontpage": f"{prefix}_content_frontpage",
        "redirect_links": f"{prefix}_redirect_links",
        "sefurls_bak": f"{prefix}_sefurls_bak",
        "tags": f"{prefix}_tags",
        "contentitem_tag_map": f"{prefix}_contentitem_tag_map",
        "itpm_tags": f"{prefix}_itpm_tags",
        "itpm_urls": f"{prefix}_itpm_urls",
        "modules": f"{prefix}_modules",
        "modules_menu": f"{prefix}_modules_menu",
        "route66_metadata": f"{prefix}_route66_metadata",
        "route66_sitemaps": f"{prefix}_route66_sitemaps",
        "osmap_sitemaps": f"{prefix}_osmap_sitemaps",
        "osmap_sitemap_menus": f"{prefix}_osmap_sitemap_menus",
        "kunena_categories": f"{prefix}_kunena_categories",
        "kunena_topics": f"{prefix}_kunena_topics",
        "kunena_messages": f"{prefix}_kunena_messages",
        "kunena_messages_text": f"{prefix}_kunena_messages_text",
    }
    selected = {alias: raw_tables.get(raw_name, []) for alias, raw_name in mapping.items()}
    selected["_prefix"] = [{"value": prefix}]
    return selected


@dataclass
class AssetLookup:
    filesystem_root: Path
    archive_index: JPAArchiveIndex | None
    asset_source: dict[str, Any]
    canonical_assets: dict[str, str]


class MultiPartBinaryReader:
    def __init__(self, parts: list[Path]) -> None:
        if not parts:
            raise ValueError("At least one archive part is required")
        self.parts = parts
        self.part_sizes = [part.stat().st_size for part in parts]
        self.part_offsets: list[int] = []
        offset = 0
        for size in self.part_sizes:
            self.part_offsets.append(offset)
            offset += size
        self.total_size = offset

    def read_range(self, offset: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must be non-negative")
        if offset < 0 or offset + size > self.total_size:
            raise ValueError("Requested range is outside the archive bounds")
        if size == 0:
            return b""

        remaining = size
        current_offset = offset
        chunks: list[bytes] = []
        while remaining:
            part_index = bisect_right(self.part_offsets, current_offset) - 1
            part_start = self.part_offsets[part_index]
            local_offset = current_offset - part_start
            available = self.part_sizes[part_index] - local_offset
            take = min(remaining, available)
            with self.parts[part_index].open("rb") as handle:
                handle.seek(local_offset)
                chunks.append(handle.read(take))
            current_offset += take
            remaining -= take
        return b"".join(chunks)


def detect_jpa_parts(joomla_root: Path) -> list[Path]:
    archive_parts = sorted(joomla_root.glob("*.j??"))
    jpa_parts = sorted(joomla_root.glob("*.jpa"))
    if not jpa_parts:
        return []
    return archive_parts + [part for part in jpa_parts if part not in archive_parts]


def read_uint16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_uint32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def normalize_archive_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")


def build_jpa_index(archive_parts: list[Path]) -> JPAArchiveIndex:
    reader = MultiPartBinaryReader(archive_parts)
    header = reader.read_range(0, 19)
    if header[:3] != b"JPA":
        raise ValueError(f"Unsupported archive signature in {archive_parts[-1].name}")

    header_length = read_uint16(header, 3)
    if header_length < 19:
        raise ValueError("Invalid JPA header length")
    cursor = header_length
    entries: dict[str, JPAEntry] = {}

    while cursor < reader.total_size:
        signature = reader.read_range(cursor, 3)
        if not signature:
            break
        if signature != b"JPF":
            raise ValueError(f"Unexpected JPA entity signature at offset {cursor}: {signature!r}")

        block_header = reader.read_range(cursor, 21)
        block_length = read_uint16(block_header, 3)
        path_length = read_uint16(block_header, 5)
        full_block = reader.read_range(cursor, block_length)
        path_start = 7
        path_end = path_start + path_length
        raw_path = full_block[path_start:path_end]
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            path = raw_path.decode("latin-1")
        normalized_path = normalize_archive_path(path)
        entity_type = full_block[path_end]
        compression_type = full_block[path_end + 1]
        compressed_size = read_uint32(full_block, path_end + 2)
        uncompressed_size = read_uint32(full_block, path_end + 6)
        permissions = read_uint32(full_block, path_end + 10)
        data_offset = cursor + block_length

        entries[normalized_path] = JPAEntry(
            path=normalized_path,
            entity_type=entity_type,
            compression_type=compression_type,
            compressed_size=compressed_size,
            uncompressed_size=uncompressed_size,
            permissions=permissions,
            data_offset=data_offset,
        )
        cursor = data_offset + compressed_size

    return JPAArchiveIndex(archives=archive_parts, entries=entries)


def read_jpa_member(archive_index: JPAArchiveIndex, member_path: str) -> bytes:
    return read_jpa_member_with_reader(
        archive_index,
        member_path,
        MultiPartBinaryReader(archive_index.archives),
    )


def read_jpa_member_with_reader(
    archive_index: JPAArchiveIndex,
    member_path: str,
    reader: MultiPartBinaryReader,
) -> bytes:
    normalized = normalize_archive_path(member_path)
    entry = archive_index.entries.get(normalized)
    if not entry:
        raise FileNotFoundError(f"Archive member not found: {member_path}")
    if entry.entity_type == 0:
        return b""

    payload = reader.read_range(entry.data_offset, entry.compressed_size)
    if entry.compression_type == 0:
        return payload
    if entry.compression_type == 1:
        return zlib.decompress(payload, -zlib.MAX_WBITS)
    if entry.compression_type == 2:
        return bz2.decompress(payload)
    raise ValueError(f"Unsupported JPA compression type: {entry.compression_type}")


def asset_alias_keys(path: str) -> set[str]:
    normalized = normalize_archive_path(path)
    path_obj = PurePosixPath(normalized)
    keys = {normalized.lower()}
    stem = path_obj.stem
    suffix = path_obj.suffix
    if stem.lower().startswith("koi_"):
        keys.add(str(path_obj.with_name(stem[4:] + suffix)).lower())
    else:
        keys.add(str(path_obj.with_name(f"koi_{stem}{suffix}")).lower())
    return keys


def collect_available_assets(joomla_root: Path, archive_index: JPAArchiveIndex | None) -> set[str]:
    available_assets: set[str] = set()
    if archive_index:
        available_assets.update(path for path in archive_index.entries.keys() if is_asset_ref(path))
    if joomla_root.exists():
        for path in joomla_root.rglob("*"):
            if not path.is_file():
                continue
            relative = normalize_archive_path(path.relative_to(joomla_root).as_posix())
            if is_asset_ref(relative):
                available_assets.add(relative)
    return available_assets


def build_canonical_asset_lookup(available_assets: set[str]) -> dict[str, str]:
    canonical_assets: dict[str, str] = {}
    for asset in sorted(available_assets):
        for alias_key in asset_alias_keys(asset):
            canonical_assets.setdefault(alias_key, asset)
    return canonical_assets


def build_asset_lookup(joomla_root: Path) -> AssetLookup:
    archive_parts = detect_jpa_parts(joomla_root)
    archive_index = build_jpa_index(archive_parts) if archive_parts else None
    filesystem_entries = (
        [
            path for path in joomla_root.iterdir()
            if path.name != ".gitkeep" and path not in archive_parts
        ]
        if joomla_root.exists()
        else []
    )
    if filesystem_entries:
        mode = "filesystem"
    elif archive_index:
        mode = "jpa-archive"
    else:
        mode = "empty"

    asset_source = {
        "mode": mode,
        "archives": [path.name for path in archive_parts],
        "archive_indexed_entries": archive_index.file_count if archive_index else 0,
    }
    available_assets = collect_available_assets(joomla_root, archive_index)
    canonical_assets = build_canonical_asset_lookup(available_assets)
    return AssetLookup(
        filesystem_root=joomla_root,
        archive_index=archive_index,
        asset_source=asset_source,
        canonical_assets=canonical_assets,
    )


def materialize_asset(asset_ref: str, asset_lookup: AssetLookup, output_root: Path) -> str | None:
    normalized = normalize_archive_path(asset_ref)
    canonical = asset_lookup.canonical_assets.get(normalized.lower(), normalized)
    output_path = output_root.joinpath(*PurePosixPath(normalized).parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filesystem_source = asset_lookup.filesystem_root.joinpath(*PurePosixPath(canonical).parts)
    if filesystem_source.exists():
        shutil.copyfile(filesystem_source, output_path)
        return "filesystem"

    if asset_lookup.archive_index and canonical in asset_lookup.archive_index.entries:
        reader = MultiPartBinaryReader(asset_lookup.archive_index.archives)
        payload = read_jpa_member_with_reader(asset_lookup.archive_index, canonical, reader)
        output_path.write_bytes(payload)
        return "jpa-archive"

    return None


def export_resolved_assets(
    items: list[dict[str, Any]],
    asset_lookup: AssetLookup,
    output_root: Path,
) -> dict[str, Any]:
    unique_refs: list[str] = []
    seen: set[str] = set()
    for item in items:
        for ref in item["asset_resolution"]["resolved"]:
            normalized = normalize_archive_path(ref)
            if normalized not in seen:
                seen.add(normalized)
                unique_refs.append(normalized)

    exported = 0
    by_source = Counter()
    missing: list[str] = []
    archive_reader = (
        MultiPartBinaryReader(asset_lookup.archive_index.archives)
        if asset_lookup.archive_index
        else None
    )

    for ref in unique_refs:
        output_path = output_root.joinpath(*PurePosixPath(ref).parts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        filesystem_source = asset_lookup.filesystem_root.joinpath(*PurePosixPath(ref).parts)
        if filesystem_source.exists():
            shutil.copyfile(filesystem_source, output_path)
            exported += 1
            by_source["filesystem"] += 1
            continue
        if asset_lookup.archive_index and ref in asset_lookup.archive_index.entries and archive_reader:
            payload = read_jpa_member_with_reader(asset_lookup.archive_index, ref, archive_reader)
            output_path.write_bytes(payload)
            exported += 1
            by_source["jpa-archive"] += 1
            continue
        missing.append(ref)

    return {
        "exported": exported,
        "missing": len(missing),
        "output_root": str(output_root),
        "by_source": dict(sorted(by_source.items())),
    }


def extract_archive_tree(
    asset_lookup: AssetLookup,
    output_root: Path,
) -> dict[str, Any]:
    if asset_lookup.archive_index is None:
        return {
            "output_root": str(output_root),
            "directories": 0,
            "files": 0,
            "skipped_existing": 0,
            "source": asset_lookup.asset_source.get("mode"),
        }

    reader = MultiPartBinaryReader(asset_lookup.archive_index.archives)
    directories = 0
    files = 0
    skipped_existing = 0

    for archive_path, entry in sorted(asset_lookup.archive_index.entries.items()):
        destination = output_root.joinpath(*PurePosixPath(archive_path).parts)
        if entry.entity_type == 0:
            destination.mkdir(parents=True, exist_ok=True)
            directories += 1
            continue
        if destination.exists():
            skipped_existing += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = read_jpa_member_with_reader(asset_lookup.archive_index, archive_path, reader)
        destination.write_bytes(payload)
        files += 1

    return {
        "output_root": str(output_root),
        "directories": directories,
        "files": files,
        "skipped_existing": skipped_existing,
        "source": "jpa-archive",
    }


def slugify(value: str | None, fallback: str) -> str:
    candidate = (value or "").strip().lower()
    candidate = re.sub(r"[^a-z0-9]+", "-", candidate)
    candidate = candidate.strip("-")
    return candidate or fallback


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    text = STRIP_TAGS_PATTERN.sub(" ", value)
    text = unescape(text)
    return WHITESPACE_PATTERN.sub(" ", text).strip()


def join_html_segments(introtext: str | None, fulltext: str | None) -> str:
    parts = [segment.strip() for segment in (introtext, fulltext) if segment and segment.strip()]
    return "\n\n".join(parts)


def parse_images_field(images_value: Any) -> list[str]:
    if not images_value or not isinstance(images_value, str):
        return []
    try:
        payload = json.loads(images_value)
    except json.JSONDecodeError:
        return []
    refs: list[str] = []
    for key in ("image_intro", "image_fulltext"):
        candidate = payload.get(key)
        if candidate:
            refs.append(str(candidate))
    return refs


def extract_asset_refs(body: str, image_refs: list[str]) -> list[str]:
    refs = list(image_refs)
    for match in ASSET_PATTERN.findall(body):
        cleaned = match.strip()
        parsed = urlparse(cleaned)
        if parsed.scheme or parsed.netloc:
            continue
        path = parsed.path.strip()
        if not path or path.startswith("mailto:"):
            continue
        normalized_path = path.lstrip("/")
        if not is_asset_ref(normalized_path):
            continue
        refs.append(normalized_path)
    unique: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        normalized = ref.replace("\\", "/")
        if normalized in INTENTIONALLY_OMITTED_ASSET_REFS:
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def strip_intentionally_omitted_assets(body: str) -> str:
    normalized = body
    for asset_ref in INTENTIONALLY_OMITTED_ASSET_REFS:
        escaped = re.escape(asset_ref)
        paragraph_pattern = re.compile(
            rf'<p\b[^>]*>\s*<img\b[^>]*src=["\']{escaped}["\'][^>]*>\s*</p>',
            re.IGNORECASE,
        )
        image_pattern = re.compile(
            rf'<img\b[^>]*src=["\']{escaped}["\'][^>]*>',
            re.IGNORECASE,
        )
        normalized = paragraph_pattern.sub("", normalized)
        normalized = image_pattern.sub("", normalized)
    return normalized


def build_link_lookup(
    articles: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    category_paths: dict[int, str],
    menu_routes: dict[int, str],
    legacy_route_lookup: dict[str, str] | None = None,
) -> dict[str, str]:
    candidate_targets: dict[str, set[str]] = defaultdict(set)
    category_by_id = {
        row["id"]: row
        for row in categories
        if isinstance(row.get("id"), int)
    }

    for category in categories:
        category_id = category.get("id")
        if not isinstance(category_id, int):
            continue
        category_path = category_paths.get(category_id)
        if not category_path:
            continue
        route = "/" + category_path
        candidates = {
            f"{category_path}.html",
            f"{category_path.split('/')[-1]}.html",
        }
        for candidate in candidates:
            candidate_targets[candidate.lower()].add(route)

    for article in articles:
        article_id = article.get("id")
        if not isinstance(article_id, int):
            continue
        route, _ = best_original_url(article, category_paths, menu_routes)
        slug = slugify(article.get("alias"), fallback=f"article-{article_id}")
        candidates = {f"{route.lstrip('/')}.html", f"{slug}.html"}
        legacy_prefixed_slug = None
        if re.match(r"^\d+-", slug):
            legacy_prefixed_slug = f"part-{slug}"
            candidates.add(f"{legacy_prefixed_slug}.html")

        catid = article.get("catid")
        if isinstance(catid, int):
            category_path = category_paths.get(catid)
            if category_path:
                category_tail = category_path.split("/")[-1]
                category = category_by_id.get(catid)
                category_title_slug = slugify(category.get("title") if category else None, fallback=category_tail)
                candidates.add(f"{category_path}/{slug}.html")
                candidates.add(f"{category_tail}/{slug}.html")
                candidates.add(f"{category_title_slug}/{slug}.html")
                if legacy_prefixed_slug:
                    candidates.add(f"{category_path}/{legacy_prefixed_slug}.html")
                    candidates.add(f"{category_tail}/{legacy_prefixed_slug}.html")
                    candidates.add(f"{category_title_slug}/{legacy_prefixed_slug}.html")
                if slug.endswith("q"):
                    candidates.add(f"{category_path}/{slug[:-1]}.html")
                    candidates.add(f"{category_tail}/{slug[:-1]}.html")
                    candidates.add(f"{category_title_slug}/{slug[:-1]}.html")

        for candidate in candidates:
            candidate_targets[candidate.lower()].add(route)

    link_lookup = {
        candidate: next(iter(targets))
        for candidate, targets in candidate_targets.items()
        if len(targets) == 1
    }
    if legacy_route_lookup:
        for source, target in legacy_route_lookup.items():
            link_lookup.setdefault(source, target)
    return link_lookup


def normalize_sef_target(sefurl: str) -> str:
    cleaned = sefurl.strip().lstrip("/")
    if cleaned.lower().endswith(".html"):
        cleaned = cleaned[:-5]
    return "/" + cleaned if cleaned else "/"


def append_fragment(route: str, fragment: str | None) -> str:
    if not fragment:
        return route
    return f"{route}#{fragment}"


def classify_origurl(origurl: str) -> str:
    if "option=com_tags" in origurl:
        return "com_tags"
    if "option=com_content" in origurl and "view=article" in origurl:
        return "com_content_article"
    if "option=com_content" in origurl and "view=category" in origurl:
        return "com_content_category"
    return "other"


def build_legacy_route_catalog(sef_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for row in sef_rows:
        sefurl = str(row.get("sefurl") or "").strip()
        if not sefurl:
            continue
        lower_key = sefurl.lower()
        record = catalog.get(lower_key)
        candidate = {
            "sefurl": sefurl,
            "target_path": normalize_sef_target(sefurl),
            "origurl": row.get("origurl"),
            "route_type": classify_origurl(str(row.get("origurl") or "")),
            "enabled": row.get("enabled"),
            "priority": row.get("priority"),
            "itemid": row.get("Itemid"),
            "id": row.get("id"),
        }
        if record is None:
            catalog[lower_key] = candidate
            continue
        current_enabled = 1 if record.get("enabled") else 0
        candidate_enabled = 1 if candidate.get("enabled") else 0
        if candidate_enabled > current_enabled:
            catalog[lower_key] = candidate
        elif candidate_enabled == current_enabled and (candidate.get("id") or 0) < (record.get("id") or 0):
            catalog[lower_key] = candidate
    return sorted(catalog.values(), key=lambda row: row["sefurl"])


def build_legacy_route_lookup(legacy_route_catalog: list[dict[str, Any]]) -> dict[str, str]:
    return {
        row["sefurl"].lower(): row["target_path"]
        for row in legacy_route_catalog
        if row.get("enabled") in (1, "1", True)
    }


def normalize_summary_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = SCRIPT_TAG_PATTERN.sub("", value)
    cleaned = NAMESPACED_TAG_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("\xa0", " ")
    text = html_to_text(cleaned)
    return text or None


def tag_slug_to_label(slug: str) -> str:
    if slug.isdigit():
        return slug
    words = slug.replace("-", " ").replace("_", " ").split()
    if not words:
        return slug
    return " ".join(word.capitalize() for word in words)


def extract_body_tags(body: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in TAG_LINK_PATTERN.findall(body):
        decoded = unquote(raw_tag).strip().strip("/")
        tag = slugify(decoded, fallback="")
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
    return sorted(tags)


def merge_item_tags(items: list[dict[str, Any]]) -> None:
    for item in items:
        merged = sorted(set(item.get("tags", [])) | set(extract_body_tags(item.get("body", ""))))
        item["tags"] = merged


def build_tags_index(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tag_map: dict[str, dict[str, Any]] = {}
    for item in items:
        if item.get("status") != "published":
            continue
        for tag in item.get("tags", []):
            record = tag_map.setdefault(
                tag,
                {
                    "slug": tag,
                    "label": tag_slug_to_label(tag),
                    "count": 0,
                    "items": [],
                },
            )
            record["count"] += 1
            record["items"].append(
                {
                    "source_id": item["source_id"],
                    "title": item["title"],
                    "url": item["original_url"],
                    "category": item.get("category"),
                }
            )
    for record in tag_map.values():
        record["items"].sort(key=lambda row: (row["title"].lower(), row["url"]))
    return sorted(tag_map.values(), key=lambda row: (-row["count"], row["slug"]))


def build_homepage_intent(
    frontpage_rows: list[dict[str, Any]],
    menu_index: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    item_by_id = {
        item["source_id"]: item
        for item in items
        if isinstance(item.get("source_id"), int)
    }
    featured_items: list[dict[str, Any]] = []
    for row in sorted(frontpage_rows, key=lambda entry: (entry.get("ordering") or 0, entry.get("content_id") or 0)):
        content_id = row.get("content_id")
        item = item_by_id.get(content_id)
        featured_items.append(
            {
                "content_id": content_id,
                "ordering": row.get("ordering"),
                "featured_up": normalize_timestamp(row.get("featured_up")),
                "featured_down": normalize_timestamp(row.get("featured_down")),
                "matched_item": (
                    {
                        "source_id": item["source_id"],
                        "title": item["title"],
                        "url": item["original_url"],
                        "status": item["status"],
                    }
                    if item
                    else None
                ),
            }
        )

    home_menu = next(
        (
            row for row in menu_index
            if row.get("published") in (1, "1", True)
            and row.get("home") in (1, "1", True)
        ),
        None,
    )
    if home_menu is None:
        home_menu = next(
            (
                row for row in menu_index
                if row.get("published") in (1, "1", True)
                and str(row.get("title") or "").strip().lower() == "home"
            ),
            None,
        )

    return {
        "featured_count": len(featured_items),
        "featured_items": featured_items,
        "home_menu": (
            {
                "id": home_menu.get("id"),
                "title": home_menu.get("title"),
                "path": home_menu.get("path"),
                "link": home_menu.get("link"),
                "menutype": home_menu.get("menutype"),
            }
            if home_menu
            else None
        ),
    }


def build_social_metadata(
    legacy_route_catalog: list[dict[str, Any]],
    url_rows: list[dict[str, Any]],
    tag_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    legacy_lookup = {
        "/" + str(row["sefurl"]).strip().lstrip("/"): row["target_path"]
        for row in legacy_route_catalog
    }
    tags_by_url_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in tag_rows:
        url_id = row.get("url_id")
        if isinstance(url_id, int):
            tags_by_url_id[url_id].append(row)

    records: list[dict[str, Any]] = []
    for row in sorted(url_rows, key=lambda entry: entry.get("id") or 0):
        url_id = row.get("id")
        if not isinstance(url_id, int):
            continue
        uri = str(row.get("uri") or "").strip()
        if not uri:
            continue
        metadata: dict[str, list[str]] = defaultdict(list)
        for tag in sorted(tags_by_url_id.get(url_id, []), key=lambda entry: (entry.get("ordering") or 0, entry.get("id") or 0)):
            tag_type = str(tag.get("type") or tag.get("name") or "").strip()
            content = str(tag.get("content") or "").strip()
            if tag_type and content:
                metadata[tag_type].append(content)
        records.append(
            {
                "url_id": url_id,
                "uri": uri,
                "target_path": legacy_lookup.get(uri, normalize_sef_target(uri)),
                "published": row.get("published"),
                "primary_url": row.get("primary_url"),
                "metadata": dict(sorted(metadata.items())),
            }
        )
    return records


def build_secondary_content_inventory(tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    published_frontend_modules = [
        row
        for row in tables.get("modules", [])
        if row.get("published") in (1, "1", True) and row.get("client_id") in (0, "0", None)
    ]
    kunena_topics = tables.get("kunena_topics", [])
    kunena_messages = tables.get("kunena_messages", [])

    return {
        "homepage_feature_rows": len(tables.get("content_frontpage", [])),
        "social_metadata_urls": len(tables.get("itpm_urls", [])),
        "social_metadata_tags": len(tables.get("itpm_tags", [])),
        "published_frontend_modules": len(published_frontend_modules),
        "published_frontend_module_titles": [
            str(row.get("title") or "")
            for row in published_frontend_modules[:12]
        ],
        "kunena": {
            "categories": len(tables.get("kunena_categories", [])),
            "topics": len(kunena_topics),
            "messages": len(kunena_messages),
            "sample_subjects": [
                str(row.get("subject") or "")
                for row in kunena_topics[:5]
            ],
        },
        "route66": {
            "metadata_rows": len(tables.get("route66_metadata", [])),
            "sitemaps": len(tables.get("route66_sitemaps", [])),
        },
        "osmap": {
            "sitemaps": len(tables.get("osmap_sitemaps", [])),
            "sitemap_menu_links": len(tables.get("osmap_sitemap_menus", [])),
        },
    }


def parse_content_identifier(value: str | None) -> int | None:
    if not value:
        return None
    raw = value.split(":")[0]
    if raw.isdigit():
        return int(raw)
    return None


def build_public_nav(
    menus: list[dict[str, Any]],
    items: list[dict[str, Any]],
    categories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_content_views = {"article", "category", "categories"}
    article_routes = {
        item["source_id"]: item["original_url"]
        for item in items
        if isinstance(item.get("source_id"), int)
    }
    category_routes = {
        row["id"]: "/" + str(row.get("path") or "").strip("/")
        for row in categories
        if isinstance(row.get("id"), int)
        and row.get("extension") in (None, "com_content")
        and str(row.get("path") or "").strip("/")
    }

    included_rows: list[dict[str, Any]] = []
    included_ids: set[int] = set()
    for menu in menus:
        identifier = menu.get("id")
        if not isinstance(identifier, int):
            continue
        if menu.get("published") not in (1, "1", True):
            continue
        link = menu.get("link")
        if not isinstance(link, str) or not link.strip():
            continue

        route = None
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        option = (query.get("option") or [None])[0]
        view = (query.get("view") or [None])[0]

        if option == "com_content" and view == "article":
            article_id = parse_content_identifier((query.get("id") or query.get("a_id") or [None])[0])
            if article_id is not None:
                route = article_routes.get(article_id)
        elif option == "com_content" and view in {"category", "categories"}:
            category_id = parse_content_identifier((query.get("id") or [None])[0])
            if category_id is not None:
                route = category_routes.get(category_id)
        elif option == "com_tags" and view == "tags":
            route = "/tags"

        if not route:
            continue

        if option == "com_content" and view not in allowed_content_views:
            continue
        if option not in {"com_content", "com_tags"}:
            continue

        included_rows.append(
            {
                "id": identifier,
                "title": menu.get("title"),
                "path": menu.get("path"),
                "route": route,
                "type": menu.get("type"),
                "menutype": menu.get("menutype"),
                "level": menu.get("level"),
                "parent_id": menu.get("parent_id"),
                "home": menu.get("home"),
                "link": link,
            }
        )
        included_ids.add(identifier)

    for row in included_rows:
        if row["parent_id"] not in included_ids:
            row["parent_id"] = None

    return sorted(included_rows, key=lambda row: ((row["path"] or ""), row["id"]))


def build_missing_assets_audit(items: list[dict[str, Any]], asset_lookup: AssetLookup) -> list[dict[str, Any]]:
    available_assets = collect_available_assets(asset_lookup.filesystem_root, asset_lookup.archive_index)

    directory_index: dict[str, list[str]] = defaultdict(list)
    for asset in available_assets:
        directory_index[str(PurePosixPath(asset).parent)].append(asset)
    for siblings in directory_index.values():
        siblings.sort()

    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        for asset in item["asset_resolution"]["missing"]:
            normalized = normalize_archive_path(asset)
            record = grouped.setdefault(
                normalized,
                {
                    "asset_ref": normalized,
                    "count": 0,
                    "affected_items": [],
                },
            )
            record["count"] += 1
            if len(record["affected_items"]) < 10:
                record["affected_items"].append(
                    {
                        "source_id": item["source_id"],
                        "title": item["title"],
                        "url": item["original_url"],
                    }
                )

    audit: list[dict[str, Any]] = []
    for asset_ref, record in grouped.items():
        asset_path = PurePosixPath(asset_ref)
        directory = str(asset_path.parent)
        siblings = directory_index.get(directory, [])
        stem = asset_path.stem.lower()
        suffix = asset_path.suffix.lower()

        def split_sequence_marker(value: str) -> tuple[str, str] | None:
            match = re.match(r"^(.*?)(?:[_-]?)([a-z]|\d+)$", value, re.IGNORECASE)
            if not match:
                return None
            base = match.group(1)
            marker = match.group(2)
            if not base:
                return None
            return base.lower(), marker.lower()

        same_stem = [
            candidate
            for candidate in siblings
            if PurePosixPath(candidate).stem.lower() == stem and PurePosixPath(candidate).suffix.lower() != suffix
        ]
        renamed_prefix = stem.removeprefix("koi_")
        rename_candidates = [
            candidate
            for candidate in siblings
            if PurePosixPath(candidate).stem.lower() in {stem, renamed_prefix}
            or PurePosixPath(candidate).stem.lower().removeprefix("koi_") == renamed_prefix
        ]
        desired_sequence = split_sequence_marker(stem)
        sequence_candidates = [
            candidate
            for candidate in siblings
            if desired_sequence
            and split_sequence_marker(PurePosixPath(candidate).stem.lower())
            and split_sequence_marker(PurePosixPath(candidate).stem.lower())[0] == desired_sequence[0]
        ]

        nearby_candidates = same_stem or rename_candidates or sequence_candidates
        classification = "missing-in-backup"
        suggested_action = "verify-source-or-remove-reference"
        suggested_target = None
        if same_stem:
            classification = "extension-variant-candidate"
            suggested_action = "review-extension-variant"
        elif rename_candidates and any(PurePosixPath(candidate).stem.lower() != stem for candidate in rename_candidates):
            classification = "possible-rename"
            suggested_action = "alias-to-existing-asset"
            if len(rename_candidates) == 1:
                suggested_target = rename_candidates[0]
        elif sequence_candidates:
            classification = "sequence-gap"
            suggested_action = "source-missing-sequence-member"

        audit.append(
            {
                "asset_ref": asset_ref,
                "count": record["count"],
                "classification": classification,
                "suggested_action": suggested_action,
                "suggested_target": suggested_target,
                "nearby_candidates": nearby_candidates[:12],
                "affected_items": record["affected_items"],
            }
        )

    return sorted(audit, key=lambda row: (-row["count"], row["asset_ref"]))


def resolve_relative_link_target(href: str, link_lookup: dict[str, str]) -> str | None:
    raw = href.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return None
    if parsed.path.lower() == "search.html":
        params = parse_qs(parsed.query)
        query = (params.get("searchword") or params.get("q") or [""])[0].strip()
        if not query:
            return "/search/"
        return "/search/?" + urlencode({"q": query})

    cleaned_path = unquote(parsed.path or "").strip().lstrip("/").rstrip(" '\"")
    if not cleaned_path:
        return None

    href_lower = cleaned_path.lower()
    target = link_lookup.get(href_lower)
    if target:
        return append_fragment(target, parsed.fragment)

    if href_lower.startswith("tags/"):
        return append_fragment(normalize_sef_target(cleaned_path), parsed.fragment)

    alias_target = LEGACY_LINK_ALIAS_LOOKUP.get(href_lower)
    if alias_target:
        resolved_alias_target = link_lookup.get(alias_target.lower())
        if resolved_alias_target:
            return append_fragment(resolved_alias_target, parsed.fragment)
        return append_fragment(normalize_sef_target(alias_target), parsed.fragment)

    if href_lower.endswith("q.html"):
        without_q = f"{href_lower[:-6]}.html"
        target = link_lookup.get(without_q)
        if target:
            return append_fragment(target, parsed.fragment)

    if BARE_EXTERNAL_LINK_PATTERN.match(raw):
        return f"http://{raw}"

    if href_lower.endswith(".html"):
        stem = cleaned_path[:-5]
        first_segment = stem.split("/", 1)[0].lower()
        if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
            base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
            remainder = stem.split("/", 1)[1] if "/" in stem else ""
            route = base_route if not remainder else f"{base_route}/{remainder}"
            return append_fragment(route, parsed.fragment)
        return append_fragment(normalize_sef_target(cleaned_path), parsed.fragment)

    first_segment = cleaned_path.split("/", 1)[0].lower()
    if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
        base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
        remainder = cleaned_path.split("/", 1)[1] if "/" in cleaned_path else ""
        route = base_route if not remainder else f"{base_route}/{remainder}"
        return append_fragment(route, parsed.fragment)

    return None


def resolve_absolute_internal_link_target(href: str, link_lookup: dict[str, str]) -> str | None:
    parsed = urlparse(href)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if parsed.netloc.lower() not in {"isaackoi.com", "www.isaackoi.com"}:
        return None
    candidate = parsed.path.lstrip("/")
    if not candidate:
        return "/"
    candidate_with_suffix = candidate
    if parsed.query:
        candidate_with_suffix += f"?{parsed.query}"
    if parsed.fragment:
        candidate_with_suffix += f"#{parsed.fragment}"
    target = resolve_relative_link_target(candidate_with_suffix, link_lookup)
    if target:
        return target
    if candidate.lower().endswith(".html"):
        return append_fragment(normalize_sef_target(candidate), parsed.fragment)
    return None


def normalize_link_label(label_html: str) -> str:
    stripped = TAG_STRIP_PATTERN.sub("", label_html)
    return " ".join(unescape(stripped).replace("\xa0", " ").split()).lower()


def resolve_contextual_personality_slug(context_html: str, link_lookup: dict[str, str]) -> str | None:
    for _, href in reversed(CONTEXT_LINK_HREF_PATTERN.findall(context_html)):
        candidate = href.strip()
        if not candidate or candidate.lower().startswith("file:"):
            continue
        if candidate.startswith("/ufo-history/ufo-personalities/"):
            return candidate.rstrip("/").split("/")[-1].lower()
        resolved = resolve_relative_link_target(candidate, link_lookup)
        if resolved and resolved.startswith("/ufo-history/ufo-personalities/"):
            return resolved.rstrip("/").split("/")[-1].lower()
    return None


def resolve_local_file_link_target(
    href: str,
    label_html: str,
    link_lookup: dict[str, str],
    context_html: str = "",
) -> str | None:
    label_key = normalize_link_label(label_html)
    target = LOCAL_FILE_LINK_TEXT_LOOKUP.get(label_key)
    if target:
        return target

    author_slug = resolve_contextual_personality_slug(context_html, link_lookup)
    if author_slug:
        contextual_target = LOCAL_FILE_LINK_AUTHOR_TITLE_LOOKUP.get((author_slug, label_key))
        if contextual_target:
            return contextual_target

    parsed = urlparse(href)
    normalized_path = unquote(parsed.path or "").replace("\\", "/").rstrip("/")
    if not normalized_path:
        return None
    path_key = normalized_path.split("/")[-1].strip().lower()
    return LOCAL_FILE_LINK_PATH_LOOKUP.get(path_key)


def normalize_body_html(
    body: str,
    article_by_id: dict[int, dict[str, Any]],
    link_lookup: dict[str, str],
    depth: int = 0,
) -> str:
    if not body:
        return ""

    normalized = body.replace("\xa0", " ")
    normalized = SCRIPT_TAG_PATTERN.sub("", normalized)
    normalized = NAMESPACED_TAG_PATTERN.sub("", normalized)
    normalized = GOOGLE_HIGHLIGHT_SPAN_PATTERN.sub(r"\1", normalized)
    normalized = LOCAL_FILE_IMAGE_PATTERN.sub("", normalized)
    normalized = strip_intentionally_omitted_assets(normalized)

    if depth < 2:
        def replace_article(match: re.Match[str]) -> str:
            article_id = int(match.group(1))
            article = article_by_id.get(article_id)
            if not article:
                return ""
            embedded_body = join_html_segments(article.get("introtext"), article.get("fulltext"))
            return normalize_body_html(embedded_body, article_by_id, link_lookup, depth + 1)

        normalized = ARTICLE_INCLUDE_PATTERN.sub(replace_article, normalized)
    else:
        normalized = ARTICLE_INCLUDE_PATTERN.sub("", normalized)

    def replace_local_file_link(match: re.Match[str]) -> str:
        context_html = normalized[max(0, match.start() - 500):match.start()]
        target = resolve_local_file_link_target(
            match.group("href"),
            match.group("label"),
            link_lookup,
            context_html,
        )
        if not target:
            return match.group("label")
        before = match.group("before")
        after = match.group("after")
        return f'<a{before}href="{target}"{after}>{match.group("label")}</a>'

    normalized = LOCAL_FILE_LINK_PATTERN.sub(replace_local_file_link, normalized)

    def replace_href(match: re.Match[str]) -> str:
        quote = match.group(1)
        href = match.group(2)
        target = resolve_relative_link_target(href, link_lookup)
        if not target:
            return match.group(0)
        return f'href={quote}{target}{quote}'

    normalized = RELATIVE_LINK_HREF_PATTERN.sub(replace_href, normalized)

    def replace_absolute_internal_href(match: re.Match[str]) -> str:
        quote = match.group(1)
        href = match.group(2)
        fragment = match.group(3) or ""
        target = resolve_absolute_internal_link_target(href, link_lookup)
        if not target:
            return match.group(0)
        return f'href={quote}{target}{fragment}{quote}'

    normalized = ABSOLUTE_INTERNAL_HTML_LINK_PATTERN.sub(replace_absolute_internal_href, normalized)
    return normalized


def is_asset_ref(path: str) -> bool:
    lowered = path.lower()
    _, extension = os.path.splitext(lowered)
    if extension in ASSET_EXTENSIONS:
        return True
    return any(lowered.startswith(prefix) for prefix in ASSET_PATH_HINTS)


def build_category_maps(categories: list[dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    category_by_id: dict[int, dict[str, Any]] = {}
    for category in categories:
        identifier = category.get("id")
        if isinstance(identifier, int):
            category_by_id[identifier] = category

    path_cache: dict[int, str] = {}

    def category_path(category_id: int) -> str:
        if category_id in path_cache:
            return path_cache[category_id]
        category = category_by_id.get(category_id)
        if not category:
            return ""
        alias = slugify(category.get("alias"), fallback=f"category-{category_id}")
        explicit_path = category.get("path")
        if isinstance(explicit_path, str) and explicit_path.strip() and explicit_path != "root":
            path_cache[category_id] = explicit_path.strip().strip("/")
            return path_cache[category_id]
        parent_id = category.get("parent_id")
        if parent_id in (None, 0, 1):
            path = alias
        else:
            parent_path = category_path(int(parent_id))
            path = f"{parent_path}/{alias}" if parent_path else alias
        path_cache[category_id] = path
        return path

    for category_id in category_by_id:
        category_path(category_id)

    return category_by_id, path_cache


def build_menu_route_map(menus: list[dict[str, Any]]) -> dict[int, str]:
    menu_by_id: dict[int, dict[str, Any]] = {}
    for menu in menus:
        identifier = menu.get("id")
        if isinstance(identifier, int):
            menu_by_id[identifier] = menu

    path_cache: dict[int, str] = {}

    def menu_path(menu_id: int) -> str:
        if menu_id in path_cache:
            return path_cache[menu_id]
        menu = menu_by_id.get(menu_id)
        if not menu:
            return ""
        alias = slugify(menu.get("alias"), fallback=f"menu-{menu_id}")
        parent_id = menu.get("parent_id")
        if parent_id in (None, 0, 1):
            path = alias
        else:
            parent_path = menu_path(int(parent_id))
            path = f"{parent_path}/{alias}" if parent_path else alias
        path_cache[menu_id] = path
        return path

    article_routes: dict[int, str] = {}
    for menu in menus:
        if menu.get("published") not in (1, "1"):
            continue
        link = menu.get("link")
        if not isinstance(link, str) or "view=article" not in link:
            continue
        parsed_query = parse_qs(urlparse(link).query)
        item_ids = parsed_query.get("id")
        if not item_ids:
            continue
        raw_id = item_ids[0].split(":")[0]
        if not raw_id.isdigit():
            continue
        article_id = int(raw_id)
        route = "/" + menu_path(int(menu["id"]))
        article_routes.setdefault(article_id, route)
    return article_routes


def build_tag_map(
    tag_rows: list[dict[str, Any]],
    content_tag_rows: list[dict[str, Any]],
) -> dict[int, list[str]]:
    tags_by_id = {
        row["id"]: row
        for row in tag_rows
        if isinstance(row.get("id"), int)
    }
    tag_map: dict[int, list[str]] = defaultdict(list)
    for mapping in content_tag_rows:
        content_item_id = mapping.get("content_item_id")
        tag_id = mapping.get("tag_id")
        if not isinstance(content_item_id, int) or not isinstance(tag_id, int):
            continue
        tag_row = tags_by_id.get(tag_id)
        if not tag_row:
            continue
        tag_alias = slugify(tag_row.get("alias") or tag_row.get("title"), fallback=f"tag-{tag_id}")
        tag_map[content_item_id].append(tag_alias)
    return {key: sorted(set(values)) for key, values in tag_map.items()}


def status_name(state: Any) -> str:
    mapping = {
        1: "published",
        0: "unpublished",
        2: "archived",
        -2: "trashed",
    }
    if isinstance(state, str) and state.lstrip("-").isdigit():
        state = int(state)
    return mapping.get(state, "unknown")


def normalize_timestamp(value: Any) -> Any:
    if value in (None, "", "0000-00-00 00:00:00", "0000-00-00"):
        return None
    return value


def resolve_assets(asset_refs: list[str], asset_lookup: AssetLookup) -> dict[str, list[str]]:
    resolved: list[str] = []
    missing: list[str] = []
    for asset_ref in asset_refs:
        normalized = normalize_archive_path(asset_ref)
        canonical = asset_lookup.canonical_assets.get(normalized.lower(), normalized)
        candidate = asset_lookup.filesystem_root.joinpath(*PurePosixPath(canonical).parts)
        exists_in_fs = candidate.exists()
        exists_in_archive = (
            asset_lookup.archive_index is not None
            and canonical in asset_lookup.archive_index.entries
        )
        if exists_in_fs or exists_in_archive:
            resolved.append(asset_ref)
        else:
            missing.append(asset_ref)
    return {"resolved": resolved, "missing": missing}


def best_original_url(
    article: dict[str, Any],
    category_paths: dict[int, str],
    menu_routes: dict[int, str],
) -> tuple[str, str]:
    article_id = article.get("id")
    if isinstance(article_id, int) and article_id in menu_routes:
        return menu_routes[article_id], "menu"

    alias = slugify(article.get("alias"), fallback=f"article-{article_id or 'unknown'}")
    cat_id = article.get("catid")
    if isinstance(cat_id, int):
        category_path = category_paths.get(cat_id, "")
        if category_path:
            return f"/{category_path}/{alias}", "category"
    return f"/{alias}", "alias"


def build_items(tables: dict[str, list[dict[str, Any]]], asset_lookup: AssetLookup) -> list[dict[str, Any]]:
    article_by_id = {
        row["id"]: row
        for row in tables.get("content", [])
        if isinstance(row.get("id"), int)
    }
    users = {
        row["id"]: row
        for row in tables.get("users", [])
        if isinstance(row.get("id"), int)
    }
    categories, category_paths = build_category_maps(
        [
            row
            for row in tables.get("categories", [])
            if row.get("extension") in (None, "com_content")
        ]
    )
    menu_routes = build_menu_route_map(tables.get("menu", []))
    tag_map = build_tag_map(
        tables.get("tags", []),
        tables.get("contentitem_tag_map", []),
    )
    legacy_route_catalog = build_legacy_route_catalog(tables.get("sefurls_bak", []))
    legacy_route_lookup = build_legacy_route_lookup(legacy_route_catalog)
    link_lookup = build_link_lookup(
        tables.get("content", []),
        tables.get("categories", []),
        category_paths,
        menu_routes,
        legacy_route_lookup,
    )

    items: list[dict[str, Any]] = []
    for article in tables.get("content", []):
        article_id = article.get("id")
        if not isinstance(article_id, int):
            continue

        raw_body = join_html_segments(article.get("introtext"), article.get("fulltext"))
        body = normalize_body_html(raw_body, article_by_id, link_lookup)
        image_refs = parse_images_field(article.get("images"))
        asset_refs = extract_asset_refs(body, image_refs)
        asset_resolution = resolve_assets(asset_refs, asset_lookup)
        original_url, route_source = best_original_url(article, category_paths, menu_routes)

        catid = article.get("catid")
        category_title = None
        if isinstance(catid, int):
            category = categories.get(catid)
            if category:
                category_title = category.get("title")

        author = None
        created_by = article.get("created_by")
        if isinstance(created_by, int) and created_by in users:
            author = users[created_by].get("name") or users[created_by].get("username")

        item = {
            "source_id": article_id,
            "source_type": "joomla_article",
            "source_table": "content",
            "slug": slugify(article.get("alias"), fallback=f"article-{article_id}"),
            "title": article.get("title") or f"Article {article_id}",
            "summary": normalize_summary_text(article.get("introtext")),
            "body": body,
            "body_format": "html",
            "created_at": normalize_timestamp(article.get("created")),
            "updated_at": normalize_timestamp(article.get("modified"))
            or normalize_timestamp(article.get("created")),
            "status": status_name(article.get("state")),
            "category": category_title,
            "tags": tag_map.get(article_id, []),
            "asset_refs": asset_refs,
            "asset_resolution": asset_resolution,
            "original_url": original_url,
            "legacy_route_guess": route_source,
            "author": author,
        }
        items.append(item)

    merge_item_tags(items)
    items.sort(key=lambda item: (item["slug"], item["source_id"]))
    return items


def build_menu_index(menus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    menu_by_id = {
        row["id"]: row
        for row in menus
        if isinstance(row.get("id"), int)
    }
    path_cache: dict[int, str] = {}

    def menu_path(menu_id: int) -> str:
        if menu_id in path_cache:
            return path_cache[menu_id]
        row = menu_by_id.get(menu_id)
        if not row:
            return ""
        explicit_path = row.get("path")
        if isinstance(explicit_path, str) and explicit_path.strip() and explicit_path != "root":
            path_cache[menu_id] = explicit_path.strip().strip("/")
            return path_cache[menu_id]
        alias = slugify(row.get("alias"), fallback=f"menu-{menu_id}")
        parent_id = row.get("parent_id")
        if parent_id in (None, 0, 1):
            resolved = alias
        else:
            parent_path = menu_path(int(parent_id))
            resolved = f"{parent_path}/{alias}" if parent_path else alias
        path_cache[menu_id] = resolved
        return resolved

    result: list[dict[str, Any]] = []
    for row in menus:
        identifier = row.get("id")
        if not isinstance(identifier, int):
            continue
        result.append(
            {
                "id": identifier,
                "title": row.get("title"),
                "alias": row.get("alias"),
                "path": menu_path(identifier),
                "link": row.get("link"),
                "type": row.get("type"),
                "menutype": row.get("menutype"),
                "published": row.get("published"),
                "home": row.get("home"),
                "parent_id": row.get("parent_id"),
                "level": row.get("level"),
            }
        )
    return sorted(result, key=lambda row: (row["path"] or "", row["id"]))


def build_category_index(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in categories:
        identifier = row.get("id")
        if not isinstance(identifier, int):
            continue
        result.append(
            {
                "id": identifier,
                "title": row.get("title"),
                "alias": row.get("alias"),
                "path": row.get("path"),
                "extension": row.get("extension"),
                "published": row.get("published"),
                "parent_id": row.get("parent_id"),
            }
        )
    return sorted(result, key=lambda row: ((row["path"] or ""), row["id"]))


def build_unresolved_relative_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for item in items:
        for match in RELATIVE_LINK_HREF_PATTERN.finditer(item["body"]):
            href = match.group(2)
            if is_asset_ref(href):
                continue
            entry = refs.setdefault(href, {"href": href, "count": 0, "source_ids": []})
            entry["count"] += 1
            if len(entry["source_ids"]) < 10 and item["source_id"] not in entry["source_ids"]:
                entry["source_ids"].append(item["source_id"])
    return sorted(refs.values(), key=lambda row: (-row["count"], row["href"]))


def build_template_inventory(asset_lookup: AssetLookup) -> list[dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    entry_paths: list[str] = []
    if asset_lookup.archive_index:
        entry_paths.extend(asset_lookup.archive_index.entries.keys())
    if asset_lookup.filesystem_root.exists():
        for path in asset_lookup.filesystem_root.joinpath("templates").rglob("*"):
            if path.is_file():
                relative = path.relative_to(asset_lookup.filesystem_root).as_posix()
                entry_paths.append(relative)

    for path in entry_paths:
        parts = PurePosixPath(path).parts
        if len(parts) < 2 or parts[0] != "templates":
            continue
        template_name = parts[1]
        if template_name == "index.html":
            continue
        record = templates.setdefault(
            template_name,
            {
                "name": template_name,
                "file_count": 0,
                "has_index_php": False,
                "has_template_details": False,
                "sample_files": [],
            },
        )
        record["file_count"] += 1
        relative_inside_template = "/".join(parts[2:]) if len(parts) > 2 else ""
        if relative_inside_template == "index.php":
            record["has_index_php"] = True
        if relative_inside_template == "templateDetails.xml":
            record["has_template_details"] = True
        if relative_inside_template and len(record["sample_files"]) < 10:
            record["sample_files"].append(relative_inside_template)

    return sorted(templates.values(), key=lambda row: row["name"])


def build_content_audit(items: list[dict[str, Any]], unresolved_relative_links: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items_with_tables": sum(1 for item in items if "<table" in item["body"].lower()),
        "items_with_images": sum(1 for item in items if "images/" in item["body"].lower()),
        "items_with_documents": sum(
            1
            for item in items
            if "documents/" in item["body"].lower() or "docs/" in item["body"].lower()
        ),
        "items_with_missing_assets": sum(1 for item in items if item["asset_resolution"]["missing"]),
        "unresolved_relative_link_targets": len(unresolved_relative_links),
        "unresolved_relative_link_occurrences": sum(row["count"] for row in unresolved_relative_links),
        "items_with_tags": sum(1 for item in items if item.get("tags")),
        "distinct_tags": len({tag for item in items for tag in item.get("tags", [])}),
    }


def build_redirects(redirect_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    redirects: list[dict[str, Any]] = []
    for row in redirect_rows:
        old_url = row.get("old_url") or row.get("source_url")
        new_url = row.get("new_url") or row.get("destination_url")
        if not old_url or not new_url:
            continue
        redirects.append(
            {
                "source": old_url,
                "destination": new_url,
                "published": row.get("published"),
                "hits": row.get("hits"),
            }
        )
    return redirects


def summarize_tables(tables: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        name: len(rows)
        for name, rows in sorted(tables.items())
        if not name.startswith("_")
    }


def build_report(
    items: list[dict[str, Any]],
    redirects: list[dict[str, Any]],
    tables: dict[str, list[dict[str, Any]]],
    parse_errors: dict[str, int],
    asset_source: dict[str, Any],
    asset_export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_counts = Counter(item["status"] for item in items)
    total_assets = sum(len(item["asset_refs"]) for item in items)
    missing_assets = sum(len(item["asset_resolution"]["missing"]) for item in items)
    resolved_assets = total_assets - missing_assets
    report = {
        "table_counts": summarize_tables(tables),
        "normalized_counts": {
            "content_items": len(items),
            "redirects": len(redirects),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "asset_counts": {
            "referenced": total_assets,
            "resolved": resolved_assets,
            "missing": missing_assets,
        },
        "asset_source": asset_source,
        "parse_errors": dict(sorted(parse_errors.items())),
    }
    if asset_export is not None:
        report["asset_export"] = asset_export
    return report


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def yaml_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = ["---"]
    ordered_keys = [
        "source_id",
        "source_type",
        "source_table",
        "slug",
        "title",
        "summary",
        "created_at",
        "updated_at",
        "status",
        "category",
        "tags",
        "asset_refs",
        "original_url",
        "legacy_route_guess",
        "author",
    ]
    for key in ordered_keys:
        value = payload.get(key)
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {yaml_scalar(item)}")
            else:
                lines.append(f"{key}: []")
            continue
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return lines


def write_outputs(content_root: Path, result: ExtractionResult) -> None:
    articles_dir = content_root / "articles"
    meta_dir = content_root / "_meta"
    articles_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    for item in result.items:
        filename = f"{item['source_id']}-{item['slug']}.md"
        front_matter = yaml_lines(item)
        body = item["body"].strip()
        document = "\n".join(front_matter)
        if body:
            document = f"{document}\n{body}\n"
        else:
            document = f"{document}\n"
        (articles_dir / filename).write_text(document, encoding="utf-8")

    (meta_dir / "content-manifest.json").write_text(
        json.dumps(result.items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (meta_dir / "extraction-report.json").write_text(
        json.dumps(result.report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (meta_dir / "redirects.json").write_text(
        json.dumps(result.redirects, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    for filename, payload in result.meta.items():
        (meta_dir / filename).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def run_extraction(
    db_root: Path,
    joomla_root: Path,
    export_assets_root: Path | None = None,
    extract_archive_root: Path | None = None,
) -> ExtractionResult:
    if not db_root.exists():
        raise FileNotFoundError(f"Database backup directory does not exist: {db_root}")
    if not joomla_root.exists():
        raise FileNotFoundError(f"Joomla backup directory does not exist: {joomla_root}")

    load_result = load_sql_records(db_root)
    tables = select_core_tables(load_result.tables)
    if not tables.get("content"):
        raise RuntimeError(
            "No Joomla content rows were found. Put a SQL dump under backups/raw/db/ "
            "and make sure it contains INSERT statements for the content table."
        )

    asset_lookup = build_asset_lookup(joomla_root)
    items = build_items(tables, asset_lookup)
    redirects = build_redirects(tables.get("redirect_links", []))
    legacy_route_catalog = build_legacy_route_catalog(tables.get("sefurls_bak", []))
    menu_index = build_menu_index(tables.get("menu", []))
    category_index = build_category_index(tables.get("categories", []))
    public_nav = build_public_nav(menu_index, items, category_index)
    tags_index = build_tags_index(items)
    homepage_intent = build_homepage_intent(tables.get("content_frontpage", []), menu_index, items)
    social_metadata = build_social_metadata(
        legacy_route_catalog,
        tables.get("itpm_urls", []),
        tables.get("itpm_tags", []),
    )
    unresolved_relative_links = build_unresolved_relative_links(items)
    missing_assets_audit = build_missing_assets_audit(items, asset_lookup)
    secondary_content_inventory = build_secondary_content_inventory(tables)
    template_inventory = build_template_inventory(asset_lookup)
    content_audit = build_content_audit(items, unresolved_relative_links)
    asset_export = None
    if export_assets_root is not None:
        asset_export = export_resolved_assets(items, asset_lookup, export_assets_root)
    archive_export = None
    if extract_archive_root is not None:
        archive_export = extract_archive_tree(asset_lookup, extract_archive_root)
    report = build_report(
        items,
        redirects,
        tables,
        load_result.parse_errors,
        asset_lookup.asset_source,
        asset_export,
    )
    report["content_audit"] = content_audit
    report["template_inventory"] = {
        "template_count": len(template_inventory),
        "names": [row["name"] for row in template_inventory],
    }
    report["public_nav"] = {
        "item_count": len(public_nav),
    }
    report["tags"] = {
        "tag_count": len(tags_index),
        "items_with_tags": content_audit["items_with_tags"],
    }
    report["homepage_intent"] = {
        "featured_count": homepage_intent["featured_count"],
        "home_menu_present": homepage_intent["home_menu"] is not None,
    }
    report["social_metadata"] = {
        "url_count": len(social_metadata),
        "tagged_url_count": sum(1 for row in social_metadata if row["metadata"]),
    }
    missing_asset_classes = Counter(row["classification"] for row in missing_assets_audit)
    missing_asset_actions = Counter(row["suggested_action"] for row in missing_assets_audit)
    report["missing_assets_audit"] = {
        "unique_missing_assets": len(missing_assets_audit),
        "by_classification": dict(sorted(missing_asset_classes.items())),
        "by_suggested_action": dict(sorted(missing_asset_actions.items())),
    }
    report["secondary_content_inventory"] = secondary_content_inventory
    if archive_export is not None:
        report["archive_export"] = archive_export
    meta = {
        "menu-index.json": menu_index,
        "public-nav.json": public_nav,
        "category-index.json": category_index,
        "tags-index.json": tags_index,
        "homepage-intent.json": homepage_intent,
        "social-metadata.json": social_metadata,
        "legacy-routes.json": legacy_route_catalog,
        "missing-assets.json": missing_assets_audit,
        "secondary-content-inventory.json": secondary_content_inventory,
        "unresolved-relative-links.json": unresolved_relative_links,
        "template-inventory.json": template_inventory,
    }
    return ExtractionResult(items=items, redirects=redirects, report=report, meta=meta)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Joomla backup content into normalized Markdown and JSON manifests."
    )
    parser.add_argument(
        "--db-root",
        default="backups/raw/db",
        help="Directory containing one or more Joomla SQL dump files (.sql or .sql.gz).",
    )
    parser.add_argument(
        "--joomla-root",
        default="backups/raw/joomla-site",
        help="Directory containing the Joomla filesystem backup used for asset resolution.",
    )
    parser.add_argument(
        "--content-root",
        default="content",
        help="Directory where normalized content and manifests will be written.",
    )
    parser.add_argument(
        "--extract-assets",
        action="store_true",
        help="Materialize resolved asset files from the Joomla backup into --assets-output-root.",
    )
    parser.add_argument(
        "--assets-output-root",
        default="content/assets/source",
        help="Directory where resolved assets should be written when --extract-assets is used.",
    )
    parser.add_argument(
        "--extract-archive",
        action="store_true",
        help="Unpack the Joomla Akeeba archive into --archive-output-root.",
    )
    parser.add_argument(
        "--archive-output-root",
        default="backups/extracted/joomla-site",
        help="Directory where the full Joomla archive should be unpacked when --extract-archive is used.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    db_root = Path(args.db_root).resolve()
    joomla_root = Path(args.joomla_root).resolve()
    content_root = Path(args.content_root).resolve()
    assets_output_root = Path(args.assets_output_root).resolve() if args.extract_assets else None
    archive_output_root = Path(args.archive_output_root).resolve() if args.extract_archive else None

    try:
        result = run_extraction(
            db_root=db_root,
            joomla_root=joomla_root,
            export_assets_root=assets_output_root,
            extract_archive_root=archive_output_root,
        )
    except Exception as exc:  # pragma: no cover
        print(f"Extraction failed: {exc}", file=sys.stderr)
        return 1

    write_outputs(content_root=content_root, result=result)
    print(
        f"Extracted {len(result.items)} content items and {len(result.redirects)} redirects "
        f"into {content_root}"
    )
    if args.extract_assets:
        export_summary = result.report.get("asset_export", {})
        print(
            f"Exported {export_summary.get('exported', 0)} assets "
            f"to {export_summary.get('output_root', assets_output_root)}"
        )
    if args.extract_archive:
        archive_summary = result.report.get("archive_export", {})
        print(
            f"Unpacked {archive_summary.get('files', 0)} files "
            f"to {archive_summary.get('output_root', archive_output_root)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
