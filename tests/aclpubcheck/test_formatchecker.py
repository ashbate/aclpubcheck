import unittest
from unittest.mock import MagicMock, patch
from collections import defaultdict
from aclpubcheck.formatchecker import Formatter, Error, Warn, Page, Margin

class TestFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = Formatter()

    @patch('aclpubcheck.formatchecker.pdfplumber.open')
    def test_format_check_success(self, mock_pdfplumber_open):
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(width=Page.WIDTH.value, height=Page.HEIGHT.value, chars=[], images=[], extract_text=MagicMock(return_value='References\n')), MagicMock(width=Page.WIDTH.value, height=Page.HEIGHT.value, chars=[], images=[], extract_text=MagicMock(return_value='References\n'))]
        mock_pdfplumber_open.return_value = mock_pdf
        self.formatter.check_page_size = MagicMock()
        self.formatter.check_page_margin = MagicMock()
        self.formatter.check_page_num = MagicMock()
        self.formatter.check_font = MagicMock()
        self.formatter.check_references = MagicMock()
        self.formatter.logs = defaultdict(list)
        result = self.formatter.format_check('dummy.pdf', 'long')
        self.assertIsInstance(result, dict)

    @patch('aclpubcheck.formatchecker.pdfplumber.open')
    def test_format_check_with_errors(self, mock_pdfplumber_open):
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock(width=Page.WIDTH.value, height=Page.HEIGHT.value, chars=[], images=[], extract_text=MagicMock(return_value='References\n'))]
        mock_pdfplumber_open.return_value = mock_pdf
        self.formatter.check_page_size = MagicMock()
        self.formatter.check_page_margin = MagicMock()
        self.formatter.check_page_num = MagicMock()
        self.formatter.check_font = MagicMock()
        self.formatter.logs = defaultdict(list)
        self.formatter.logs[Error.SIZE] = ['Page #1 is not A4.']
        result = self.formatter.format_check('dummy.pdf', 'long')
        self.assertIn('Error.SIZE', str(result))

    def test_init(self):
        f = Formatter()
        self.assertEqual(f.right_offset, 4.5)
        self.assertEqual(f.left_offset, 2)
        self.assertEqual(f.top_offset, 1)
        self.assertEqual(f.bottom_offset, 1)
        self.assertEqual(f.background_color, 255)
        self.assertIsNotNone(f.pdf_namecheck)

    def test_make_name_check_config(self):
        self.formatter.pdfpath = 'dummy.pdf'
        config = self.formatter.make_name_check_config()
        self.assertEqual(config.file, 'dummy.pdf')
        self.assertFalse(config.show_names)
        self.assertTrue(config.first_name)
        self.assertEqual(config.ref_string, 'References')
        self.assertEqual(config.mode, 'ensemble')

    @patch('aclpubcheck.formatchecker.Page')
    def test_check_page_size(self, mock_page_enum):
        self.formatter.pdf = MagicMock()
        page = MagicMock()
        page.width = Page.WIDTH.value
        page.height = Page.HEIGHT.value
        self.formatter.pdf.pages = [page]
        self.formatter.logs = defaultdict(list)
        self.formatter.page_errors = set()
        self.formatter.check_page_size()
        self.assertEqual(self.formatter.logs[Error.SIZE], [])

    @patch('aclpubcheck.formatchecker.Margin')
    def test_check_page_margin(self, mock_margin_enum):
        self.formatter.pdf = MagicMock()
        page = MagicMock()
        page.images = []
        page.extract_words.return_value = []
        self.formatter.pdf.pages = [page]
        self.formatter.logs = defaultdict(list)
        self.formatter.page_errors = set()
        self.formatter.check_page_margin('output_dir')
        self.assertIsInstance(self.formatter.logs, defaultdict)

    def test_check_page_num(self):
        self.formatter.pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = 'References\n'
        self.formatter.pdf.pages = [page for _ in range(9)]
        self.formatter.logs = defaultdict(list)
        self.formatter.check_page_num('long')
        self.assertIsInstance(self.formatter.logs, defaultdict)

    def test_check_font(self):
        self.formatter.pdf = MagicMock()
        page = MagicMock()
        page.chars = [{'fontname': 'NimbusRomNo9L-Regu'} for _ in range(100)]
        self.formatter.pdf.pages = [page]
        self.formatter.logs = defaultdict(list)
        self.formatter.check_font()
        self.assertIsInstance(self.formatter.logs, defaultdict)

    @patch('aclpubcheck.formatchecker.PDFNameCheck')
    def test_check_references(self, mock_pdfnamecheck):
        self.formatter.pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = 'References\n'
        page.hyperlinks = [{'uri': 'https://doi.org/123'}, {'uri': 'https://arxiv.org/456'}]
        self.formatter.pdf.pages = [page]
        self.formatter.logs = defaultdict(list)
        global args
        args = type('Args', (), {'disable_name_check': False})
        self.formatter.check_references()
        self.assertIsInstance(self.formatter.logs, defaultdict)

if __name__ == '__main__':
    unittest.main()
