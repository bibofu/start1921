from pathlib import Path

import pymupdf
import pytest
from history_agent.extraction.models import PageRecord
from history_agent.extraction.text import build_page_record
from history_agent.processing.structure import (
    infer_year_structure,
    section_path_for_page,
    structure_for_document,
)


def _pages(texts: dict[int, str]) -> dict[int, PageRecord]:
    return {
        page: build_page_record(
            document_id="fixture",
            file_sha256="hash",
            pdf_page=page,
            text=text,
            image_object_count=0,
            run_id="test",
        )
        for page, text in texts.items()
    }


def _pdf(path: Path, bookmarks: list[list[int | str]], page_count: int = 20) -> None:
    with pymupdf.open() as document:
        for _ in range(page_count):
            document.new_page()
        document.set_toc(bookmarks)
        for xref, (_, title, _) in zip(document.get_outline_xrefs(), bookmarks, strict=True):
            # Force UTF-16 as used by the source scan; set_toc alone writes an
            # ASCII title's NUL as a middle dot instead of retaining it.
            encoded_title = "feff" + str(title).encode("utf-16-be").hex()
            document.xref_set_key(xref, "Title", f"<{encoded_title}>")
        document.save(path)


@pytest.mark.parametrize("nul", ["", "\x00"])
def test_page_number_bookmarks_fall_back_to_body_years(work_path: Path, nul: str) -> None:
    path = work_path / "fixture.pdf"
    _pdf(path, [[1, f"封面{nul}", 1], [1, f"目录{nul}", 3], [1, f"1{nul}", 4]])
    entries = structure_for_document(
        document_id="fixture",
        title="邓小平年谱",
        source_path=path,
        pages=_pages({3: "目\n录\n1947年\n（649）", 4: "649\n1947 年 四十三岁\n1月活动。"}),
        page_count=20,
    )

    assert [(entry.title, entry.pdf_page_start, entry.source) for entry in entries] == [
        ("1947年", 4, "year_heading")
    ]


@pytest.mark.parametrize(
    "bookmarks",
    [
        [[1, "1957年", 1], [1, "1958年", 1]],
        [[1, "封面", 1], [1, "目录", 6], [1, "1957年", 1], [1, "1958年", 1]],
    ],
)
def test_broken_year_destinations_do_not_override_body(
    work_path: Path, bookmarks: list[list[int | str]]
) -> None:
    path = work_path / "fixture.pdf"
    _pdf(path, bookmarks)
    entries = structure_for_document(
        document_id="fixture",
        title="邓小平年谱",
        source_path=path,
        pages=_pages(
            {
                6: "目录\n1957年\n（1335）\n1958年\n（1413）",
                7: "1957年五十三岁",
                12: "1958年五十四岁",
            }
        ),
        page_count=20,
    )

    assert [(entry.title, entry.pdf_page_start, entry.pdf_page_end) for entry in entries] == [
        ("1957年", 7, 11),
        ("1958年", 12, 20),
    ]
    assert section_path_for_page(entries, 1) == []


def test_year_inference_handles_age_columns_and_excludes_contents_and_prose() -> None:
    entries = infer_year_structure(
        document_id="fixture",
        pages=_pages(
            {
                1: "目录\n1904年诞生\n（1）\n1920年十六岁\n（8）",
                2: "[周恩来年谱]1921年（十七岁）……11",
                3: "1921年十七岁\n（11）\n1925年二十一岁\n（21）",
                4: "材料记载他在1921年十七岁时参加活动。\n1922年十八岁时，他继续学习。",
                8: "1\n1904年诞生\n8月22日出生。",
                15: "8\n1920年十六岁\n正文。",
                17: "1920年10月\n继续学习。",
                18: "11\n1921年十七岁\n1月12日活动。",
                28: "21\n1925年\n二十一岁\n1月发表文章。",
                30: "1925年6月\n材料引用1926年的回忆。",
            }
        ),
        page_count=31,
    )

    assert [(entry.title, entry.pdf_page_start) for entry in entries] == [
        ("1904年", 8),
        ("1920年", 15),
        ("1921年", 18),
        ("1925年", 28),
    ]
    assert section_path_for_page(entries, 17) == ["1920年"]
    assert section_path_for_page(entries, 18) == ["1921年"]


def test_existing_parenthesized_year_heading_remains_supported() -> None:
    entries = infer_year_structure(
        document_id="fixture",
        pages=_pages(
            {
                9: "[周恩来年谱]1956 年（五十八岁）......677",
                20: "[周恩来年谱]1956 年（五十八岁）\n正文。",
            }
        ),
        page_count=30,
    )

    assert [(entry.title, entry.pdf_page_start) for entry in entries] == [("1956年", 20)]


def test_valid_semantic_bookmarks_keep_priority(work_path: Path) -> None:
    path = work_path / "fixture.pdf"
    _pdf(path, [[1, "1920年", 2], [1, "1921年", 5], [2, "中国共产党的成立", 6]])
    entries = structure_for_document(
        document_id="fixture",
        title="毛泽东年谱",
        source_path=path,
        pages=_pages({3: "1920年二十七岁", 7: "1921年二十八岁"}),
        page_count=20,
    )

    assert [(entry.title, entry.pdf_page_start, entry.source) for entry in entries] == [
        ("1920年", 2, "pdf_outline"),
        ("1921年", 5, "pdf_outline"),
        ("中国共产党的成立", 6, "pdf_outline"),
    ]
