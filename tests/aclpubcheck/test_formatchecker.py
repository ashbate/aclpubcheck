import pytest
from unittest.mock import MagicMock, patch
from aclpubcheck.formatchecker import Formatter, Page, Margin, Error

@pytest.fixture
def formatter():
    return Formatter()

def test_formatter_init_defaults(formatter):
    assert formatter.right_offset == 4.5
    assert formatter.left_offset == 2
    assert formatter.top_offset == 1
    assert formatter.bottom_offset == 1
    assert formatter.background_color == 255
    assert hasattr(formatter, "pdf_namecheck")

def test_make_name_check_config_returns_namespace(formatter):
    formatter.pdfpath = "dummy.pdf"
    config = formatter.make_name_check_config()
    assert config.file == "dummy.pdf"
    assert config.show_names is False
    assert config.first_name is True

def test_check_page_size_logs_error_for_non_a4(formatter):
    mock_page = MagicMock()
    mock_page.width = 600
    mock_page.height = 850
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page]
    formatter.logs = {Error.SIZE: []}
    formatter.page_errors = set()
    formatter.check_page_size()
    assert Error.SIZE in formatter.logs
    assert "not A4" in formatter.logs[Error.SIZE][0]

def test_check_page_size_no_error_for_a4(formatter):
    mock_page = MagicMock()
    mock_page.width = Page.WIDTH.value
    mock_page.height = Page.HEIGHT.value
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page]
    formatter.logs = {Error.SIZE: []}
    formatter.page_errors = set()
    formatter.check_page_size()
    assert formatter.logs[Error.SIZE] == []

def test_check_font_logs_error_for_wrong_font(monkeypatch, formatter):
    mock_page = MagicMock()
    mock_page.chars = [{'fontname': 'FakeFont'}, {'fontname': 'FakeFont'}, {'fontname': 'OtherFont'}]
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page]
    formatter.logs = {Error.FONT: []}
    formatter.check_font()
    assert any("Wrong font" in msg for msg in formatter.logs[Error.FONT])

def test_check_font_logs_error_for_low_main_font(monkeypatch, formatter):
    mock_page = MagicMock()
    # 2 of font1, 4 of font2, so max_font_count/sum_char_count = 4/6 < 0.35
    mock_page.chars = [{'fontname': 'font1'}]*2 + [{'fontname': 'font2'}]*4
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page]
    formatter.logs = {Error.FONT: []}
    # Patch correct_fontnames so font2 is not accepted
    monkeypatch.setattr(formatter, "check_font", Formatter.check_font.__get__(formatter))
    formatter.check_font()
    assert any("Can't find the main font" in msg or "Wrong font" in msg for msg in formatter.logs[Error.FONT])

def test_make_name_check_config_keys(formatter):
    formatter.pdfpath = "test.pdf"
    config = formatter.make_name_check_config()
    keys = vars(config).keys()
    assert "file" in keys
    assert "show_names" in keys
    assert "mode" in keys

def test_check_page_num_no_error_for_short_paper(monkeypatch, formatter):
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Some text\nReferences"
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page] * 5  # short paper threshold is 5
    formatter.logs = {Error.PAGELIMIT: []}
    formatter.page_errors = set()
    formatter.check_page_num("short")
    assert formatter.logs[Error.PAGELIMIT] == []

def test_check_page_num_error_for_long_paper(monkeypatch, formatter):
    # 10 pages, marker on page 10, line 1
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Some text"
    ref_page = MagicMock()
    ref_page.extract_text.return_value = "References"
    formatter.pdf = MagicMock()
    formatter.pdf.pages = [mock_page]*9 + [ref_page]
    formatter.logs = {Error.PAGELIMIT: []}
    formatter.page_errors = set()
    formatter.check_page_num("long")
    assert any("exceeds the page limit" in msg for msg in formatter.logs[Error.PAGELIMIT])

def test_format_check_calls_all_methods(monkeypatch, formatter):
    formatter.number = "1"
    formatter.pdf = MagicMock()
    formatter.logs = {}
    formatter.page_errors = set()
    formatter.pdfpath = "dummy.pdf"
    called = {}
    monkeypatch.setattr(formatter, "check_page_size", lambda: called.setdefault("size", True))
    monkeypatch.setattr(formatter, "check_page_margin", lambda output_dir: called.setdefault("margin", True))
    monkeypatch.setattr(formatter, "check_page_num", lambda paper_type: called.setdefault("num", True))
    monkeypatch.setattr(formatter, "check_font", lambda: called.setdefault("font", True))
    monkeypatch.setattr(formatter, "check_references", lambda: called.setdefault("refs", True))
    with patch("pdfplumber.open", return_value=MagicMock()):
        formatter.format_check("dummy.pdf", "long", check_references=True)
    assert all(k in called for k in ["size", "margin", "num", "font", "refs"])
