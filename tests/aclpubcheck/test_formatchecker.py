import pytest
from unittest.mock import MagicMock, patch, call
from aclpubcheck.formatchecker import Formatter, Error, Warn, Page, Margin
from argparse import Namespace
import types

@pytest.fixture
def formatter():
    f = Formatter()
    f.pdf_namecheck = MagicMock()
    return f

@pytest.fixture
def dummy_pdf():
    # Create a dummy pdfplumber PDF object with pages
    page = MagicMock()
    page.width = Page.WIDTH.value
    page.height = Page.HEIGHT.value
    page.images = []
    page.extract_words.return_value = []
    page.extract_text.return_value = "References\nSome text"
    page.chars = []
    page.hyperlinks = []
    page.to_image.return_value = MagicMock(original=[255]*10)
    pdf = MagicMock()
    pdf.pages = [page, page]
    return pdf

def test_init():
    f = Formatter()
    assert hasattr(f, 'right_offset')
    assert hasattr(f, 'pdf_namecheck')

def test_format_check_all_clear(formatter, dummy_pdf, tmp_path):
    with patch('pdfplumber.open', return_value=dummy_pdf):
        with patch('json.dump'), patch('builtins.open'), patch('os.path.join', side_effect=lambda *a: str(tmp_path/'file.json')):
            formatter.pdf_namecheck = MagicMock()
            result = formatter.format_check('dummy.pdf', 'long', output_dir=str(tmp_path))
            assert isinstance(result, dict)

def test_check_page_size_no_error(formatter, dummy_pdf):
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.page_errors = set()
    formatter.check_page_size()
    assert Error.SIZE not in formatter.logs

def test_check_page_size_with_error(formatter, dummy_pdf):
    dummy_pdf.pages[0].width = 100
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.page_errors = set()
    formatter.check_page_size()
    assert Error.SIZE in formatter.logs

def test_check_page_margin_no_violations(formatter, dummy_pdf, tmp_path):
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.page_errors = set()
    with patch('os.path.join', side_effect=lambda *a: str(tmp_path/'file.png')):
        formatter.check_page_margin(str(tmp_path))
    # Should not add margin errors
    assert Error.MARGIN not in formatter.logs

def test_check_page_num_under_limit(formatter, dummy_pdf):
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.page_errors = set()
    formatter.check_page_num('long')
    assert Error.PAGELIMIT not in formatter.logs

def test_check_page_num_over_limit(formatter, dummy_pdf):
    # 10 pages, marker on page 10
    dummy_pdf.pages = [MagicMock() for _ in range(10)]
    for i, p in enumerate(dummy_pdf.pages):
        p.extract_text.return_value = "References" if i == 9 else ""
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.page_errors = set()
    formatter.check_page_num('short')
    assert Error.PAGELIMIT in formatter.logs

def test_check_font_main_font_ok(formatter, dummy_pdf):
    dummy_pdf.pages[0].chars = [{'fontname': 'NimbusRomNo9L-Regu'}]*10
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.check_font()
    # Should not log font error
    assert Error.FONT not in formatter.logs or not formatter.logs[Error.FONT]

def test_check_font_wrong_font(formatter, dummy_pdf):
    dummy_pdf.pages[0].chars = [{'fontname': 'SomeOtherFont'}]*10
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    formatter.check_font()
    assert Error.FONT in formatter.logs

def test_make_name_check_config(formatter):
    formatter.pdfpath = 'dummy.pdf'
    config = formatter.make_name_check_config()
    assert isinstance(config, Namespace)
    assert config.file == 'dummy.pdf'

def test_check_references_warns(formatter, dummy_pdf):
    dummy_pdf.pages[0].extract_text.return_value = "References\nSome text arxiv"
    dummy_pdf.pages[0].hyperlinks = [{'uri': 'https://arxiv.org/abs/1234'}]
    formatter.pdf = dummy_pdf
    formatter.logs = {}
    with patch('aclpubcheck.formatchecker.args', new=types.SimpleNamespace(disable_name_check=False)):
        formatter.check_references()
    assert Warn.BIB in formatter.logs 