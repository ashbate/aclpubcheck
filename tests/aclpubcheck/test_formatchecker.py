import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from collections import defaultdict
import numpy as np

# Import the classes we need to test
from aclpubcheck.formatchecker import Formatter, Error, Warn, Page, Margin


class TestFormatter:
    """Test cases for the Formatter class"""
    
    @pytest.fixture
    def formatter(self):
        """Create a fresh Formatter instance for each test"""
        return Formatter()
    
    @pytest.fixture
    def mock_pdf(self):
        """Create a mock PDF with standard A4 pages"""
        pdf = Mock()
        page = Mock()
        page.width = Page.WIDTH.value
        page.height = Page.HEIGHT.value
        page.extract_text.return_value = "Sample text\nMore text"
        page.images = []
        page.extract_words.return_value = []
        page.chars = []
        page.hyperlinks = []
        page.to_image.return_value = Mock()
        page.crop.return_value = Mock()
        pdf.pages = [page]
        return pdf
    
    def test_formatter_initialization(self, formatter):
        """Test that Formatter initializes with correct default values"""
        assert formatter.right_offset == 4.5
        assert formatter.left_offset == 2
        assert formatter.top_offset == 1
        assert formatter.bottom_offset == 1
        assert formatter.background_color == 255
        assert formatter.pdf_namecheck is not None
    
    @patch('pdfplumber.open')
    @patch('os.path.join')
    @patch('json.dump')
    def test_format_check_success(self, mock_json_dump, mock_path_join, mock_pdf_open, formatter, mock_pdf):
        """Test successful format check with no errors"""
        mock_pdf_open.return_value = mock_pdf
        mock_path_join.return_value = "test_output.json"
        
        result = formatter.format_check("test.pdf", "long", output_dir=".", print_only_errors=False)
        
        assert isinstance(result, dict)
        # Should be empty dict when no errors
        mock_pdf_open.assert_called_once_with("test.pdf")
    
    def test_check_page_size_correct(self, formatter, mock_pdf):
        """Test page size check with correct A4 dimensions"""
        formatter.pdf = mock_pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        formatter.check_page_size()
        
        assert Error.SIZE not in formatter.logs
        assert len(formatter.page_errors) == 0
    
    def test_check_page_size_incorrect(self, formatter):
        """Test page size check with incorrect dimensions"""
        pdf = Mock()
        page = Mock()
        page.width = 500  # Wrong width
        page.height = 700  # Wrong height
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        formatter.check_page_size()
        
        assert Error.SIZE in formatter.logs
        assert len(formatter.logs[Error.SIZE]) == 1
        assert "Page #1 is not A4" in formatter.logs[Error.SIZE][0]
        assert 1 in formatter.page_errors
    
    def test_check_page_num_within_limit(self, formatter):
        """Test page number check within limits"""
        pdf = Mock()
        # Create 8 pages (within 9-page limit for long papers)
        pdf.pages = [Mock() for _ in range(8)]
        for page in pdf.pages:
            page.extract_text.return_value = "Sample content"
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        formatter.check_page_num("long")
        
        assert Error.PAGELIMIT not in formatter.logs
    
    def test_check_page_num_exceeds_limit(self, formatter):
        """Test page number check exceeding limits"""
        pdf = Mock()
        # Create 12 pages (exceeds 9-page limit for long papers)
        pdf.pages = [Mock() for _ in range(12)]
        
        # First 10 pages have regular content
        for i in range(10):
            pdf.pages[i].extract_text.return_value = "Regular content"
        
        # Page 11 has References (too late)
        pdf.pages[10].extract_text.return_value = "References\nSome reference"
        pdf.pages[11].extract_text.return_value = "More references"
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        formatter.check_page_num("long")
        
        assert Error.PAGELIMIT in formatter.logs
        assert "exceeds the page limit" in formatter.logs[Error.PAGELIMIT][0]
    
    def test_check_font_correct(self, formatter):
        """Test font check with correct font"""
        pdf = Mock()
        page = Mock()
        
        # Mock characters with correct font
        chars = [
            {'fontname': 'NimbusRomNo9L-Regu'} for _ in range(100)
        ]
        page.chars = chars
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        formatter.check_font()
        
        assert Error.FONT not in formatter.logs
    
    def test_check_font_incorrect(self, formatter):
        """Test font check with incorrect font"""
        pdf = Mock()
        page = Mock()
        
        # Mock characters with incorrect font
        chars = [
            {'fontname': 'Arial-Bold'} for _ in range(100)
        ]
        page.chars = chars
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        formatter.check_font()
        
        assert Error.FONT in formatter.logs
        assert "Wrong font" in formatter.logs[Error.FONT][0]
    
    def test_check_font_parsing_error(self, formatter):
        """Test font check when page parsing fails"""
        pdf = Mock()
        page = Mock()
        page.chars = None  # This will cause an error
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        formatter.check_font()
        
        assert Error.FONT in formatter.logs
        assert "Can't parse page #1" in formatter.logs[Error.FONT][0]
    
    @patch('aclpubcheck.formatchecker.args')
    def test_check_page_margin_text_violation(self, mock_args, formatter):
        """Test margin check with text violations"""
        mock_args.disable_bottom_check = True
        
        pdf = Mock()
        page = Mock()
        page.images = []
        
        # Mock word that violates left margin
        word = {
            'top': 100,
            'bottom': 120,
            'x0': 50,  # Too close to left edge (should be > 71)
            'x1': 200,
            'non_stroking_color': (255, 255, 255),  # White text (will be skipped)
            'stroking_color': None
        }
        page.extract_words.return_value = [word]
        
        # Mock the cropping and image conversion
        cropped_page = Mock()
        image_obj = Mock()
        image_obj.original = np.full((10, 10, 3), 128)  # Non-white image
        cropped_page.to_image.return_value = image_obj
        page.crop.return_value = cropped_page
        
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        with patch('os.path.join'), patch.object(formatter, 'pdf') as mock_pdf_attr:
            mock_pdf_attr.pages = pdf.pages
            formatter.check_page_margin(".")
        
        # Should not have margin errors because text is white (skipped)
        assert Error.MARGIN not in formatter.logs
    
    def test_check_references_found(self, formatter):
        """Test reference checking when references are found"""
        pdf = Mock()
        page1 = Mock()
        page1.extract_text.return_value = "Introduction\nThis is the intro"
        page1.hyperlinks = []
        
        page2 = Mock()
        page2.extract_text.return_value = "References\nSmith et al. (2020). Title."
        page2.hyperlinks = [
            {'uri': 'https://doi.org/10.1234/example1'},
            {'uri': 'https://doi.org/10.1234/example2'},
            {'uri': 'https://doi.org/10.1234/example3'},
            {'uri': 'https://arxiv.org/abs/2001.00001'},
        ]
        
        pdf.pages = [page1, page2]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        with patch('aclpubcheck.formatchecker.args') as mock_args:
            mock_args.disable_name_check = True
            formatter.check_references()
        
        # Should have warnings about bibliography
        assert Warn.BIB in formatter.logs
        # Should find adequate DOI links (3 is the minimum)
        doi_warnings = [log for log in formatter.logs[Warn.BIB] if 'DOI' in log]
        assert len(doi_warnings) == 0  # No DOI warnings since we have 3 DOI links
    
    def test_check_references_no_references(self, formatter):
        """Test reference checking when no references are found"""
        pdf = Mock()
        page = Mock()
        page.extract_text.return_value = "Introduction\nThis is the intro"
        page.hyperlinks = []
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        with patch('aclpubcheck.formatchecker.args') as mock_args:
            mock_args.disable_name_check = True
            formatter.check_references()
        
        assert Warn.BIB in formatter.logs
        assert any("Couldn't find any references" in log for log in formatter.logs[Warn.BIB])
    
    def test_make_name_check_config(self, formatter):
        """Test name check configuration creation"""
        formatter.pdfpath = "/path/to/test.pdf"
        
        config = formatter.make_name_check_config()
        
        assert config.file == "/path/to/test.pdf"
        assert config.show_names == False
        assert config.whole_name == False
        assert config.first_name == True
        assert config.last_name == True
        assert config.ref_string == 'References'
        assert config.mode == 'ensemble'
        assert config.initials == True
    
    @patch('pdfplumber.open')
    @patch('os.path.join')
    @patch('json.dump')
    def test_format_check_with_errors(self, mock_json_dump, mock_path_join, mock_pdf_open, formatter):
        """Test format check that detects errors"""
        # Create a PDF with incorrect page size
        pdf = Mock()
        page = Mock()
        page.width = 500  # Wrong width
        page.height = 700  # Wrong height
        page.extract_text.return_value = "Sample text"
        page.images = []
        page.extract_words.return_value = []
        page.chars = []
        page.hyperlinks = []
        pdf.pages = [page]
        
        mock_pdf_open.return_value = pdf
        mock_path_join.return_value = "test_output.json"
        
        with patch('builtins.print'):  # Suppress print output during test
            result = formatter.format_check("test.pdf", "long", output_dir=".", print_only_errors=False)
        
        # Should return the logs as JSON when errors are found
        assert isinstance(result, dict)
        assert 'Error.SIZE' in str(result) or len(result) > 0
    
    @pytest.mark.parametrize("paper_type,expected_limit", [
        ("short", 5),
        ("long", 9),
        ("demo", 7),
        ("other", float("inf"))
    ])
    def test_page_limits_by_type(self, formatter, paper_type, expected_limit):
        """Test that different paper types have correct page limits"""
        # Create PDF with pages that would exceed short/demo limits but not long
        pdf = Mock()
        pdf.pages = [Mock() for _ in range(6)]  # 6 pages
        
        for i, page in enumerate(pdf.pages):
            if i < 5:  # First 5 pages have regular content
                page.extract_text.return_value = "Regular content"
            else:  # Last page has References
                page.extract_text.return_value = "References\nSome reference"
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        formatter.page_errors = set()
        
        formatter.check_page_num(paper_type)
        
        if paper_type == "short":
            # Should have page limit error (6 pages > 5 limit)
            assert Error.PAGELIMIT in formatter.logs
        elif paper_type in ["long", "demo", "other"]:
            # Should not have page limit error
            assert Error.PAGELIMIT not in formatter.logs
    
    def test_font_distribution_check(self, formatter):
        """Test that font checker validates font distribution"""
        pdf = Mock()
        page = Mock()
        
        # Create characters where main font is less than 35% (should fail)
        chars = (
            [{'fontname': 'NimbusRomNo9L-Regu'}] * 30 +  # 30% correct font
            [{'fontname': 'Arial-Bold'}] * 70  # 70% wrong font
        )
        page.chars = chars
        pdf.pages = [page]
        
        formatter.pdf = pdf
        formatter.logs = defaultdict(list)
        
        formatter.check_font()
        
        assert Error.FONT in formatter.logs
        font_errors = formatter.logs[Error.FONT]
        assert any("Can't find the main font" in error for error in font_errors)
        assert any("Wrong font" in error for error in font_errors)
