import pytest
from history_agent.processing.cleaning import (
    is_barcode_cover_page,
    is_scan_metadata_page,
    is_table_of_contents_page,
)


@pytest.mark.parametrize(
    "text",
    [
        "[ Gener al I nf or nat i on]\n书名=邓小平年谱.19041974上\n"
        "作者=编者\n页数=647\nSS号=12493645",
        "[ G e n e r a l I n f o r ma t i o n ]\n书名：邓小平年谱\n"
        "页数：1333\nSS号:12493860\nDX号:000007558937",
        "[General Inf or nati on]\n书名=邓小平年谱.19041974下\n页数=3413\nDX号=\n出版日期=2009.12",
    ],
)
def test_scanner_metadata_ocr_variants_are_excluded(text: str) -> None:
    assert is_scan_metadata_page(text)


@pytest.mark.parametrize(
    "text",
    [
        "书名=测试\n页数=647\nSS号=123\n正文讨论扫描元数据的意义。",
        "[General Information]\n书名=测试\n正文介绍图书内容。",
        "正文引用 [General Information] 字段。\n书名=测试\n页数=647\nSS号=123",
        "1974年12月\n出版社=中央文献出版社\n书名=测试\n页数=647",
    ],
)
def test_metadata_mentions_in_prose_or_incomplete_headers_are_retained(text: str) -> None:
    assert not is_scan_metadata_page(text)


@pytest.mark.parametrize(
    "text",
    [
        "目\n录\n1904 年\n(1)\n1909年\n(2)\n1910年\n(3)",
        "目\n录\n1947年\n（649）\n1948 年\n（707）\n1949 年\n（794）",
        "目\n录\n1957 年\n（1335)\n1958 年\n.\n（1413）\n1959 年\n(1478)\n后\n记\n（2078）",
        "目录\n1920年十六岁\n（8）\n1921年十七岁\n（11）\n1922年十八岁\n（15）",
    ],
)
def test_chronology_contents_with_ocr_missing_dot_leaders_are_excluded(text: str) -> None:
    assert is_table_of_contents_page(text)


def test_explicit_bookmark_export_is_excluded_but_body_is_not() -> None:
    export = "封面\n书名\n版权\n前言\n目录\n1957年\n1958年\n1959年\n后记"
    assert is_table_of_contents_page(export)
    assert not is_table_of_contents_page(export + "\n这些年份都有具体的历史事件。")
    assert not is_table_of_contents_page("1957年五十三岁\n1958年\n1959年\n1月2日出席会议。")
    assert not is_table_of_contents_page("目录\n1957年\n1958年\n1959年\n这里讨论各年活动。")
    assert not is_table_of_contents_page("1957年\n（1335）\n1958年\n（1413）\n1959年\n（1478）")


def test_isbn_and_price_only_back_cover_is_excluded_but_prose_is_not() -> None:
    text = "ISBN978-7-5073-2768-7\n9\n787507327687\n定价：240.00元（上、中、下）"
    assert is_barcode_cover_page(text)
    assert not is_barcode_cover_page(text + "\n正文讨论这一版本的出版经过。")
    assert not is_barcode_cover_page("ISBN978-7-5073-2768-7\n正文讨论书目。")
