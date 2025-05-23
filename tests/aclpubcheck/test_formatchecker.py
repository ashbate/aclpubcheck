import unittest
from unittest.mock import patch, MagicMock, call
import types
import os
import tempfile
import json
from aclpubcheck.formatchecker import Formatter, Error, Warn, Page, Margin

class TestFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = Formatter()
        # Patch pdfplumber.open and PDFNameCheck
        self.patcher_pdfplumber = patch('aclpubcheck.formatchecker.pdfplumber.open')
        self.mock_pdfplumber_open = self.patcher_pdfplumber.start()
        self.patcher_namecheck = patch('aclpubcheck.formatchecker.PDFNameCheck')
        self.mock_namecheck = self.patcher_namecheck.start()
        self.addCleanup(self.patcher_pdfplumber.stop)
        self.addCleanup(self.patcher_namecheck.stop)

    def tearDown(self):
        self.patcher_pdfplumber.stop()
        self.patcher_namecheck.stop()

    def make_mock_page(self, width=Page.WIDTH.value, height=Page.HEIGHT.value, images=None, words=None, text=None, hyperlinks=None, chars=None):
        page = MagicMock()
        page.width = width
        page.height = height
        page.images = images or []
        page.extract_words.return_value = words or []
        page.extract_text.return_value = text or ''
        page.hyperlinks = hyperlinks or []
        page.chars = chars or []
        # For cropping and to_image
        page.crop.return_value = page
        page.to_image.return_value = MagicMock(original=[self.formatter.background_color]*100)
        return page

    def test_check_page_size(self):
        # One page correct, one page wrong size
        page1 = self.make_mock_page()
        page2 = self.make_mock_page(width=600, height=900)
        self.formatter.pdf = MagicMock(pages=[page1, page2])
        self.formatter.logs = {}
        self.formatter.page_errors = set()
        self.formatter.check_page_size()
        self.assertIn(Error.SIZE, self.formatter.logs)
        self.assertIn(2, self.formatter.page_errors)

    def test_check_page_margin_no_violations(self):
        # No images or words violating margins
        page = self.make_mock_page()
        self.formatter.pdf = MagicMock(pages=[page])
        self.formatter.logs = {}
        self.formatter.page_errors = set()
        with patch('aclpubcheck.formatchecker.args', MagicMock(disable_bottom_check=False)):
            self.formatter.check_page_margin(tempfile.gettempdir())
        self.assertNotIn(Error.MARGIN, self.formatter.logs)

    def test_check_page_margin_with_violations(self):
        # Add a word violating the right margin
        word = {'x0': Page.WIDTH.value-60, 'x1': Page.WIDTH.value+10, 'top': 100, 'bottom': 120, 'non_stroking_color': (1,1,1), 'stroking_color': (1,1,1)}
        page = self.make_mock_page(words=[word])
        self.formatter.pdf = MagicMock(pages=[page])
        self.formatter.logs = {}
        self.formatter.page_errors = set()
        with patch('aclpubcheck.formatchecker.args', MagicMock(disable_bottom_check=False)):
            self.formatter.check_page_margin(tempfile.gettempdir())
        self.assertIn(Error.MARGIN, self.formatter.logs)

    def test_check_page_num_within_limit(self):
        # 3 pages, type 'short' (limit 5)
        pages = [self.make_mock_page() for _ in range(3)]
        self.formatter.pdf = MagicMock(pages=pages)
        self.formatter.logs = {}
        self.formatter.page_errors = set()
        self.formatter.check_page_num('short')
        self.assertNotIn(Error.PAGELIMIT, self.formatter.logs)

    def test_check_page_num_exceeds_limit(self):
        # 6 pages, type 'short' (limit 5), marker on page 6
        pages = [self.make_mock_page(text='') for _ in range(6)]
        pages[5].extract_text.return_value = 'References\n'  # marker on page 6
        self.formatter.pdf = MagicMock(pages=pages)
        self.formatter.logs = {}
        self.formatter.page_errors = set()
        self.formatter.check_page_num('short')
        self.assertIn(Error.PAGELIMIT, self.formatter.logs)

    def test_check_font_main_font(self):
        # Main font is correct and >35%
        chars = [{'fontname': 'NimbusRomNo9L-Regu'}]*10 + [{'fontname': 'OtherFont'}]*5
        page = self.make_mock_page(chars=chars)
        self.formatter.pdf = MagicMock(pages=[page])
        self.formatter.logs = {}
        self.formatter.check_font()
        self.assertNotIn(Error.FONT, self.formatter.logs)

    def test_check_font_wrong_font(self):
        # Main font is wrong
        chars = [{'fontname': 'WrongFont'}]*10 + [{'fontname': 'OtherFont'}]*5
        page = self.make_mock_page(chars=chars)
        self.formatter.pdf = MagicMock(pages=[page])
        self.formatter.logs = {}
        self.formatter.check_font()
        self.assertIn(Error.FONT, self.formatter.logs)

    def test_make_name_check_config(self):
        self.formatter.pdfpath = 'dummy.pdf'
        config = self.formatter.make_name_check_config()
        self.assertEqual(config.file, 'dummy.pdf')
        self.assertTrue(config.first_name)
        self.assertTrue(config.last_name)
        self.assertEqual(config.ref_string, 'References')

    def test_check_references(self):
        # Simulate references, arxiv, doi, and hyperlinks
        hyperlinks = [{'uri': 'https://doi.org/10.1234/abc'}, {'uri': 'https://arxiv.org/abs/1234'}]
        page = self.make_mock_page(text='References\nSome ref', hyperlinks=hyperlinks)
        self.formatter.pdf = MagicMock(pages=[page])
        self.formatter.logs = {}
        with patch('aclpubcheck.formatchecker.args', MagicMock(disable_name_check=False)):
            self.formatter.check_references()
        self.assertIn(Warn.BIB, self.formatter.logs)

if __name__ == '__main__':
    unittest.main() 
