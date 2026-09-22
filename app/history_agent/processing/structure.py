from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pymupdf

from history_agent.extraction.models import PageRecord
from history_agent.processing.cleaning import (
    is_barcode_cover_page,
    is_scan_metadata_page,
    is_table_of_contents_page,
)
from history_agent.processing.models import StructureEntry

YEAR_HEADING = re.compile(
    r"(?:\[周恩来年谱\])?\s*((?:18|19)\d{2})\s*年?\s*"
    r"(?:[（(][^）)]{1,12}岁[）)]|[〇零一二三四五六七八九十百两\d\s]{1,12}岁|诞生)"
)
BARE_YEAR = re.compile(r"(?:18|19)\d{2}\s*年")
PAGE_LABEL = re.compile(r"[（(]?\d+[）)]?")
FRONT_MATTER_TITLES = {"封面", "封底", "书名", "扉页", "版权", "版权页", "前言", "目录"}


def _outline_label(title: str) -> str:
    # Some scanned PDFs append NUL to every bookmark, including page-number labels.
    return title.replace("\x00", "").strip()


def _entry_id(document_id: str, level: int, title: str, page: int) -> str:
    value = f"{document_id}:{level}:{title}:{page}".encode()
    return hashlib.sha256(value).hexdigest()[:24]


def extract_outline_structure(
    *, document_id: str, source_path: Path, page_count: int
) -> list[StructureEntry]:
    document = pymupdf.open(source_path)
    try:
        raw_entries = document.get_toc(simple=True)
    finally:
        document.close()
    valid = [
        (int(level), str(title).strip(), int(page))
        for level, title, page in raw_entries
        if str(title).strip() and 1 <= int(page) <= page_count
    ]
    if any(current[2] > following[2] for current, following in zip(valid, valid[1:], strict=False)):
        # Ranges cannot be trusted when the tree jumps backwards (for example,
        # every year bookmark in a scanned chronology pointing at the cover).
        return []
    years = [
        (_outline_label(title), page)
        for _, title, page in valid
        if BARE_YEAR.fullmatch(_outline_label(title))
    ]
    if len({title for title, _ in years}) > 1 and len({page for _, page in years}) == 1:
        return []
    valid = [entry for entry in valid if not PAGE_LABEL.fullmatch(_outline_label(entry[1]))]
    if not valid or all(_outline_label(title) in FRONT_MATTER_TITLES for _, title, _ in valid):
        # Cover/contents bookmarks alone do not describe the body of the book.
        return []
    entries: list[StructureEntry] = []
    for index, (level, title, start_page) in enumerate(valid):
        end_page = page_count
        for next_level, _, next_page in valid[index + 1 :]:
            if next_level <= level:
                end_page = max(start_page, next_page - 1)
                break
        entries.append(
            StructureEntry(
                entry_id=_entry_id(document_id, level, title, start_page),
                document_id=document_id,
                level=level,
                title=title,
                pdf_page_start=start_page,
                pdf_page_end=end_page,
                source="pdf_outline",
            )
        )
    return entries


def infer_year_structure(
    *, document_id: str, pages: dict[int, PageRecord], page_count: int
) -> list[StructureEntry]:
    excluded_pages = {
        page
        for page, record in pages.items()
        if is_scan_metadata_page(record.normalized_text)
        or is_table_of_contents_page(record.normalized_text)
        or is_barcode_cover_page(record.normalized_text)
    }
    pages = {page: record for page, record in pages.items() if page not in excluded_pages}
    content_end = page_count
    while content_end in excluded_pages:
        content_end -= 1
    starts: list[tuple[str, int]] = []
    seen: set[str] = set()
    for pdf_page, record in sorted(pages.items()):
        lines = [line.strip() for line in record.normalized_text.splitlines() if line.strip()]
        if any(re.sub(r"\s+", "", line) == "目录" for line in lines) or any(
            current == "目" and following == "录"
            for current, following in zip(lines, lines[1:], strict=False)
        ):
            continue
        heading_lines = [line for line in lines[:3] if not PAGE_LABEL.fullmatch(line)]
        if starts and (heading_lines[:1] == ["后记"] or heading_lines[:2] == ["后", "记"]):
            starts.append(("后记", pdf_page))
            break
        for index, line in enumerate(lines):
            if line.count(".") >= 3 or "……" in line:
                continue
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if BARE_YEAR.fullmatch(line) and next_line:
                # OCR can split one printed heading into its year and age columns.
                line = f"{line} {next_line}"
            match = YEAR_HEADING.fullmatch(line)
            if match and PAGE_LABEL.fullmatch(next_line):
                # A heading followed by only a page reference is a contents entry.
                continue
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                starts.append((f"{match.group(1)}年", pdf_page))
                break
    entries: list[StructureEntry] = []
    for index, (title, start_page) in enumerate(starts):
        end_page = starts[index + 1][1] - 1 if index + 1 < len(starts) else content_end
        entries.append(
            StructureEntry(
                entry_id=_entry_id(document_id, 1, title, start_page),
                document_id=document_id,
                level=1,
                title=title,
                pdf_page_start=start_page,
                pdf_page_end=max(start_page, end_page),
                source="body_heading" if title == "后记" else "year_heading",
            )
        )
    return entries


def structure_for_document(
    *,
    document_id: str,
    title: str,
    source_path: Path,
    pages: dict[int, PageRecord],
    page_count: int,
) -> list[StructureEntry]:
    outline = extract_outline_structure(
        document_id=document_id, source_path=source_path, page_count=page_count
    )
    if outline:
        return outline
    inferred = infer_year_structure(
        document_id=document_id, pages=pages, page_count=page_count
    )
    if inferred:
        return inferred
    return [
        StructureEntry(
            entry_id=_entry_id(document_id, 1, title, 1),
            document_id=document_id,
            level=1,
            title=title,
            pdf_page_start=1,
            pdf_page_end=page_count,
            source="document_root",
        )
    ]


def section_path_for_page(entries: list[StructureEntry], pdf_page: int) -> list[str]:
    active = [
        entry
        for entry in entries
        if entry.pdf_page_start <= pdf_page <= entry.pdf_page_end
    ]
    by_level: dict[int, StructureEntry] = {}
    for entry in active:
        current = by_level.get(entry.level)
        if current is None or entry.pdf_page_start >= current.pdf_page_start:
            by_level[entry.level] = entry
    return [by_level[level].title for level in sorted(by_level)]
