from __future__ import annotations

import re
from collections import Counter

from history_agent.extraction.models import PageRecord

CLEANER_VERSION = "page-cleaner-v2"
PAGE_NUMBER_LINE = re.compile(r"^[\s—–-]*\d{1,4}[\s—–-]*$")
HEADING_PATTERNS = (
    re.compile(r"^第[一二三四五六七八九十百零〇0-9]+[章节编部卷篇].{0,40}$"),
    re.compile(r"^(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?.{0,30}$"),
    re.compile(r"^(目录|前言|序言|引言|后记|附录|出版说明|编者说明)$"),
)
PARAGRAPH_END = re.compile(r"[。！？；：…）”』】]$")
DOT_LEADER = re.compile(r"\.{5,}|…{5,}")
SCAN_METADATA_FIELD = re.compile(r"^(书名|作者|页数|SS号|DX号|出版日期|出版社)\s*[=＝:：]", re.I)
CONTENTS_YEAR_LABEL = re.compile(
    r"(?:18|19|20)\d{2}年(?:[（(]?[〇零一二三四五六七八九十百两\d]{1,12}岁[）)]?|诞生)?"
)
CONTENTS_PAGE_LABEL = re.compile(r"[（(]?\d{1,4}[）)]?")


def detect_repeated_marginal_lines(pages: dict[int, PageRecord]) -> set[str]:
    counts: Counter[str] = Counter()
    for record in pages.values():
        lines = [line.strip() for line in record.normalized_text.splitlines() if line.strip()]
        for line in set(lines[:2] + lines[-2:]):
            if 1 < len(line) <= 50 and not PAGE_NUMBER_LINE.fullmatch(line):
                counts[line] += 1
    threshold = max(5, round(len(pages) * 0.04))
    return {line for line, count in counts.items() if count >= threshold}


def is_heading(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern in HEADING_PATTERNS)


def is_table_of_contents_page(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_lines = "".join(lines[:12])
    leader_lines = sum(bool(DOT_LEADER.search(line)) for line in lines)
    if "目录" in first_lines and leader_lines >= 3:
        return True
    compact_lines = [re.sub(r"\s+", "", line) for line in lines]
    for index, line in enumerate(compact_lines[:12]):
        header_end = index + 1 if line == "目录" else None
        if compact_lines[index:index + 2] == ["目", "录"]:
            header_end = index + 2
        if header_end is not None:
            items = [
                re.sub(r"[.·…]+", "", item)
                for item in compact_lines[header_end:]
                if re.sub(r"[.·…]+", "", item)
            ]
            if items[-3:-1] == ["后", "记"]:
                items[-3:-1] = ["后记"]
            if len(items) >= 6 and len(items) % 2 == 0:
                pairs = list(zip(items[::2], items[1::2], strict=True))
                if (
                    sum(bool(CONTENTS_YEAR_LABEL.fullmatch(label)) for label, _ in pairs) >= 3
                    and all(
                        (CONTENTS_YEAR_LABEL.fullmatch(label) or label == "后记")
                        and CONTENTS_PAGE_LABEL.fullmatch(page)
                        for label, page in pairs
                    )
                ):
                    return True
    # Some scans append an exported bookmark list without page references.
    # Require the complete export prefix and only section/year labels, so a
    # chronology's real year heading followed by prose cannot match.
    export_prefix = ["封面", "书名", "版权", "前言", "目录"]
    year_labels = sum(bool(re.fullmatch(r"(?:18|19|20)\d{2}年", line)) for line in compact_lines)
    return (
        compact_lines[:5] == export_prefix
        and year_labels >= 3
        and all(
            line in {*export_prefix, "后记"} or re.fullmatch(r"(?:18|19|20)\d{2}年", line)
            for line in compact_lines
        )
    )


def is_scan_metadata_page(text: str) -> bool:
    """Recognize a scanner's appended metadata sheet, not mentions in prose."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    header = re.sub(r"\s+", "", lines[0]).lower()
    if header not in {
        "[generalinformation]", "【generalinformation】",
        "[generalinfornation]", "【generalinfornation】",
    }:
        return False
    fields = {
        match.group(1).lower()
        for line in lines[1:]
        if (match := SCAN_METADATA_FIELD.match(re.sub(r"\s+", "", line)))
    }
    return len(fields) >= 3


def is_barcode_cover_page(text: str) -> bool:
    """Exclude an ISBN/price-only back cover while retaining any prose page."""
    lines = [re.sub(r"\s+", "", line) for line in text.splitlines() if line.strip()]
    if not lines or not re.fullmatch(r"ISBN[\d-]{10,20}", lines[0], re.I):
        return False
    price = re.compile(r"定价[:：]\d+(?:\.\d+)?元(?:[（(][^）)]{1,15}[）)])?")
    return any(price.fullmatch(line) for line in lines[1:]) and all(
        line.isdigit() or price.fullmatch(line) for line in lines[1:]
    )


def clean_page_text(text: str, repeated_lines: set[str]) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"[ \t\u3000]+", " ", raw_line).strip()
        if line in repeated_lines or PAGE_NUMBER_LINE.fullmatch(line):
            continue
        cleaned_lines.append(line)

    paragraphs: list[str] = []
    buffer = ""
    for line in cleaned_lines:
        if not line:
            if buffer:
                paragraphs.append(buffer)
                buffer = ""
            continue
        if is_heading(line):
            if buffer:
                paragraphs.append(buffer)
                buffer = ""
            paragraphs.append(line)
            continue
        buffer += line
        if PARAGRAPH_END.search(line):
            paragraphs.append(buffer)
            buffer = ""
    if buffer:
        paragraphs.append(buffer)
    return "\n".join(paragraph for paragraph in paragraphs if paragraph)
