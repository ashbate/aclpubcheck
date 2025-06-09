import pytest
from collections import defaultdict
from argparse import Namespace
import types

import aclpubcheck.formatchecker as formatchecker

class DummyPDF:
    """Dummy PDF object that simulates pdfplumber.open result."""
    def __init__(self, pages):
        self.pages = pages

class DummyPage:
    def __init__(self, width=595, height=842, extract_text_out=None, images=None, chars=None, hyperlinks=None):
        self.width = width
        self.height = height
        self._extract_text_out = extract_text_out if extract_text_out is not None else "Sample text"
        self.images = images if images is not None else []
        self.chars = chars if chars is not None else []
        self.hyperlinks = hyperlinks if hyperlinks is not None else []
        self._to_image = None
    def extract_text(self):
        return self._extract_text_out
    def to_image(self, resolution=150):
        if self._to_image is not None:
            return self._to_image
        return DummyImage()
    def crop(self, bbox):
        return self  # For test, cropping returns self
    def extract_words(self, extra_attrs=None):
        return []  # Default: no words unless set

class DummyImage:
    def __init__(self, mean_value=0):
        self.original = [mean_value]
    def draw_rect(self, bbox, fill=None, stroke=None, stroke_width=None):
        pass
    def save(self, path, format=None):
        pass

class DummyPDFNameCheck:
    def execute(self, config):
        return ["Namecheck output"]

@pytest.fixture(autouse=True)
def patch_pdfplumber_and_namecheck(monkeypatch):
    monkeypatch.setattr(formatchecker, 'pdfplumber', types.SimpleNamespace(open=lambda path: DummyPDF([])))
    monkeypatch.setattr(formatchecker, 'PDFNameCheck', DummyPDFNameCheck)
    # Patch global args used in check_page_margin/check_references
    formatchecker.args = Namespace(disable_name_check=False, disable_bottom_check=False)
    yield
    # Undo if needed (pytest fixture)

def make_formatter_with_pdf(pages):
    f = formatchecker.Formatter()
    f.pdf = DummyPDF(pages)
    f.logs = defaultdict(list)
    f.page_errors = set()
    f.pdfpath = 'dummy.pdf'
    return f

def test_formatter_init_initializes_values():
    """Test that Formatter.__init__ sets correct default values."""
    f = formatchecker.Formatter()
    assert f.right_offset == 4.5
    assert f.left_offset == 2
    assert f.top_offset == 1
    assert f.bottom_offset == 1
    assert hasattr(f, 'pdf_namecheck')
    assert f.background_color == 255

def test_check_page_size_with_all_a4():
    """Test that check_page_size does not log errors when all pages A4 size."""
    pages = [DummyPage(width=595, height=842) for _ in range(3)]
    f = make_formatter_with_pdf(pages)
    f.check_page_size()
    assert formatchecker.Error.SIZE not in f.logs
    assert f.page_errors == set()

def test_check_page_size_with_non_a4():
    """Test that check_page_size logs non-A4 size pages."""
    pages = [DummyPage(width=595, height=842), DummyPage(width=500, height=842)]
    f = make_formatter_with_pdf(pages)
    f.check_page_size()
    assert formatchecker.Error.SIZE in f.logs
    assert "Page #2 is not A4." in f.logs[formatchecker.Error.SIZE][0]
    assert 2 in f.page_errors

def test_check_page_num_no_error_below_limit():
    """Test that check_page_num does not log anything for compliant short paper."""
    # 5 pages, threshold is 5 for short
    pages = [DummyPage() for _ in range(5)]
    f = make_formatter_with_pdf(pages)
    f.check_page_num('short')
    assert formatchecker.Error.PAGELIMIT not in f.logs

def test_check_page_num_above_limit_and_marker_after_limit():
    """Test check_page_num logs error if marker appears after threshold+1 page."""
    text_pages = ["Intro\nMore", "Method\nMore", "Results\nMore", "Results\nMore", "More", "More", "X", "Y", "Z", "References", "foo"]
    pages = [DummyPage(extract_text_out=t) for t in text_pages]
    f = make_formatter_with_pdf(pages)
    f.page_errors = set()  # No errors
    f.check_page_num('short')  # threshold = 5
    assert formatchecker.Error.PAGELIMIT in f.logs
    msg = f.logs[formatchecker.Error.PAGELIMIT][0]
    assert "References" in msg and "page 10" in msg

def test_check_font_most_used_correct_font():
    """Test check_font does not log errors if most used font is correct and present >35%."""
    chars = ([{'fontname': 'NimbusRomNo9L-Regu'}]*60 + [{'fontname': 'OtherFont'}]*40)
    pages = [DummyPage(chars=chars)]
    f = make_formatter_with_pdf(pages)
    f.check_font()
    assert formatchecker.Error.FONT not in f.logs

def test_check_font_most_used_incorrect_or_ratio_low():
    """Test check_font logs errors if wrong main font or ratio too low."""
    chars = ([{'fontname': 'FakeFont'}]*40 + [{'fontname': 'OtherFont'}]*60)
    pages = [DummyPage(chars=chars)]
    f = make_formatter_with_pdf(pages)
    f.check_font()
    assert formatchecker.Error.FONT in f.logs
    assert any("Can't find the main font" in e or "Wrong font" in e for e in f.logs[formatchecker.Error.FONT])

def test_make_name_check_config_returns_namespace():
    """Test make_name_check_config returns an argparse.Namespace with proper values."""
    f = formatchecker.Formatter()
    f.pdfpath = 'x.pdf'
    config = f.make_name_check_config()
    assert isinstance(config, Namespace)
    assert config.file == 'x.pdf'
    assert config.first_name is True
    assert config.last_name is True
    assert config.initials is True
    assert config.mode == 'ensemble'

def test_check_references_warn_for_few_dois_and_arxiv_excess():
    """Test check_references logs warnings for few dois, too many arxiv links, too few links, arxiv count, missing references."""
    # Compose a page with some arxiv, some doi links, few links overall
    hyperlinks = [
        {'uri': 'https://arxiv.org/abs/123'},
        {'uri': 'https://arxiv.org/abs/456'},
        {'uri': 'https://arxiv.org/abs/789'},
        {'uri': 'https://doi.org/10.1/1'}
    ]
    page = DummyPage(
        extract_text_out="Some text\nReferences\nArxiv is mentioned. Arxiv arxiv arxiv arxiv arxiv arxiv arxiv arxiv arxiv arxiv arxiv arxiv",
        hyperlinks=hyperlinks
    )
    f = make_formatter_with_pdf([page])
    # Patch name check config handling to test that code path
    formatchecker.args.disable_name_check = True
    f.pdf_namecheck = DummyPDFNameCheck()
    f.check_references()
    logs = f.logs[formatchecker.Warn.BIB]
    assert any("Bibliography should use ACL Anthology DOIs whenever possible" in l for l in logs)
    assert any("arXiv links more than you should" in l for l in logs)
    assert any("not using paper links" in l for l in logs)
    assert any("arXiv references more than you should" in l for l in logs)
    assert any("Namecheck output" in l for l in logs)

def test_check_references_warns_if_no_references():
    """Test check_references warns if no references section found."""
    page = DummyPage(extract_text_out="Intro\nMethod\nResults", hyperlinks=[])
    f = make_formatter_with_pdf([page])
    formatchecker.args.disable_name_check = False
    f.check_references()
    logs = f.logs[formatchecker.Warn.BIB]
    assert any("Couldn't find any references" in l for l in logs)

def test_format_check_full_flow(monkeypatch, tmp_path):
    """Integration test for format_check with mocks."""
    # Compose one page with wrong size, margin error, bad font, missing reference
    # Patch pdfplumber.open to return a single page
    # Patch np.mean to always challenge margin check
    class MPage:
        width = 500  # not A4
        height = 842
        images = []
        chars = [{'fontname': 'NotAFont'}] * 10
        hyperlinks = []
        def extract_text(self): return "References\nMore"
        def to_image(self, resolution=150): return DummyImage()
        def crop(self, bbox): return self
        def extract_words(self, extra_attrs=None):
            return [{
                'x0': 0, 'x1': 70, 'top': 0, 'bottom': 10, 'non_stroking_color': (20, 20, 20), 'stroking_color': (1,1,1)
            }]
    monkeypatch.setattr(formatchecker.pdfplumber, 'open', lambda path: DummyPDF([MPage()]))
    monkeypatch.setattr(formatchecker, 'PDFNameCheck', DummyPDFNameCheck)
    monkeypatch.setattr(formatchecker.np, 'mean', lambda a: 0)  # Force margin issue
    formatchecker.args = Namespace(disable_name_check=False, disable_bottom_check=False)
    f = formatchecker.Formatter()
    # Should log error for SIZE, MARGIN, FONT, BIB
    result = f.format_check("dummy.pdf", "short", str(tmp_path), print_only_errors=True, check_references=True)
    assert isinstance(result, dict)
    all_msgs = '\n'.join(['\n'.join(v) for v in result.values()])
    assert "not A4" in all_msgs or "Size" in all_msgs
    assert "margin" in all_msgs or "Margin" in all_msgs
    assert "font" in all_msgs or "Font" in all_msgs
    assert "references" in all_msgs or "Bibliography" in all_msgs

def test_check_page_margin_handles_parsing_error(monkeypatch):
    """Test that check_page_margin correctly logs parsing failure."""
    class ErrorPage(DummyPage):
        def crop(self, bbox): raise Exception("Failed cropping")
        def to_image(self, resolution=150): raise Exception("Failed image")
        def extract_words(self, extra_attrs=None): return [{
            'x0': 0, 'x1': 70, 'top': 0, 'bottom': 10, 'non_stroking_color': (20, 20, 20), 'stroking_color': (1,1,1)
        }]
    page = ErrorPage()
    f = make_formatter_with_pdf([page])
    # Have no page_errors (should process page 0)
    f.page_errors = set()
    f.pdf.pages[0] = page
    monkeypatch.setattr(formatchecker.np, 'mean', lambda a: 0)  # Always margin
    formatchecker.args.disable_bottom_check = False
    f.check_page_margin('.')
    assert formatchecker.Error.PARSING in f.logs
    assert "Error occurs when parsing" in f.logs[formatchecker.Error.PARSING][0] or isinstance(f.logs[formatchecker.Error.PARSING][0], str)

def test_check_page_margin_logs_margin_on_image(monkeypatch, tmp_path):
    """Test check_page_margin properly logs an image in the margin."""
    class MarginImagePage(DummyPage):
        images = [{'bottom': 10, 'top': 0, 'x0': 0, 'x1': 70}]
        def to_image(self, resolution=150): return DummyImage()
    page = MarginImagePage()
    f = make_formatter_with_pdf([page])
    monkeypatch.setattr(formatchecker.np, 'mean', lambda a: 0)  # Always margin
    f.check_page_margin(str(tmp_path))
    assert formatchecker.Error.MARGIN in f.logs
    assert any("image on page" in msg or "margin" in msg for msg in f.logs[formatchecker.Error.MARGIN])
