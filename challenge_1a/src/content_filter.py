import re
from typing import List, Dict, Set, Tuple
from collections import Counter
import pdfplumber
import numpy as np
from .utils import is_page_number


class ContentFilter:
    def __init__(self):
        self.headers_footers: Set[str] = set()
        self.table_patterns: Set[str] = set()
        self.toc_content: Set[str] = set()
        self.toc_pages: Set[int] = set()
        self.table_regions: Dict[int, List[Tuple[float, float, float, float]]] = {}  # page -> list of table bboxes
        self.visual_tables: Dict[int, List[Dict]] = {}  # page -> list of detected tables
    
    def identify_visual_tables(self, pdf_path: str) -> None:
        """Use pdfplumber to detect actual table structures visually"""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Detect tables using pdfplumber's table detection
                    tables = page.find_tables(table_settings={
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                        "min_words_vertical": 2,
                        "min_words_horizontal": 2,
                    })
                    
                    if not tables:
                        # Try with more lenient settings if strict doesn't find anything
                        tables = page.find_tables(table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "intersection_tolerance": 15,
                            "min_words_vertical": 2,
                            "min_words_horizontal": 2,
                        })
                    
                    self.visual_tables[page_num] = []
                    self.table_regions[page_num] = []
                    
                    for table in tables:
                        # Validate it's actually a table (multiple rows and columns)
                        if self._is_valid_table_structure(table, page):
                            table_bbox = table.bbox  # (x0, y0, x1, y1)
                            self.table_regions[page_num].append(table_bbox)
                            
                            # Store table data for content analysis
                            try:
                                table_data = table.extract()
                                self.visual_tables[page_num].append({
                                    'bbox': table_bbox,
                                    'data': table_data,
                                    'rows': len(table_data) if table_data else 0,
                                    'cols': len(table_data[0]) if table_data and table_data[0] else 0
                                })
                            except Exception:
                                # If extraction fails, still mark the region as a table
                                self.visual_tables[page_num].append({
                                    'bbox': table_bbox,
                                    'data': None,
                                    'rows': 0,
                                    'cols': 0
                                })
        
        except Exception as e:
            print(f"Warning: Could not perform visual table detection: {e}")
            # Fallback to pattern-based detection only
            pass
    
    def _is_valid_table_structure(self, table, page) -> bool:
        """Validate that detected table has multiple rows and columns"""
        try:
            # Get table data
            table_data = table.extract()
            
            if not table_data:
                return False
            
            # Check minimum requirements for a table
            rows = len(table_data)
            cols = len(table_data[0]) if table_data[0] else 0
            
            # Must have at least 2 rows and 2 columns to be considered a table
            if rows < 2 or cols < 2:
                return False
            
            # Check that it's not just a single column of text (which might be a list)
            if cols == 1:
                return False
            
            # Verify there's actual content in multiple cells
            non_empty_cells = 0
            total_cells = 0
            
            for row in table_data:
                for cell in row:
                    total_cells += 1
                    if cell and str(cell).strip():
                        non_empty_cells += 1
            
            # At least 30% of cells should have content
            if total_cells > 0 and (non_empty_cells / total_cells) < 0.3:
                return False
            
            # Check for table-like patterns in content
            has_headers = self._has_table_headers(table_data)
            has_structured_data = self._has_structured_data(table_data)
            
            return has_headers or has_structured_data
        
        except Exception:
            # If we can't extract data, use basic size heuristics
            bbox = table.bbox
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            
            # Must be reasonably sized
            return width > 100 and height > 50
    
    def _has_table_headers(self, table_data: List[List]) -> bool:
        """Check if first row looks like table headers"""
        if not table_data or len(table_data) < 2:
            return False
        
        first_row = table_data[0]
        if not first_row:
            return False
        
        # Look for common table header patterns
        header_patterns = [
            r'(name|title|description|type|date|version|status|amount|quantity|id|no\.?)',
            r'(s\.?no\.?|sr\.?no\.?|item|category|remarks|comments)',
            r'(page|chapter|section|subsection)'
        ]
        
        header_like_count = 0
        for cell in first_row:
            if cell and str(cell).strip():
                cell_text = str(cell).lower().strip()
                for pattern in header_patterns:
                    if re.search(pattern, cell_text):
                        header_like_count += 1
                        break
        
        # If more than half the cells look like headers
        return header_like_count >= len(first_row) / 2
    
    def _has_structured_data(self, table_data: List[List]) -> bool:
        """Check if table contains structured data patterns"""
        if not table_data or len(table_data) < 2:
            return False
        
        # Look for patterns that suggest structured data
        numeric_columns = 0
        date_columns = 0
        total_columns = len(table_data[0]) if table_data[0] else 0
        
        if total_columns == 0:
            return False
        
        # Analyze each column
        for col_idx in range(total_columns):
            column_values = []
            for row in table_data[1:]:  # Skip header row
                if col_idx < len(row) and row[col_idx]:
                    column_values.append(str(row[col_idx]).strip())
            
            if not column_values:
                continue
            
            # Check if column contains mostly numbers
            numeric_count = sum(1 for val in column_values if re.match(r'^\d+(\.\d+)?$', val))
            if numeric_count >= len(column_values) * 0.7:
                numeric_columns += 1
            
            # Check if column contains dates
            date_count = sum(1 for val in column_values if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}', val))
            if date_count >= len(column_values) * 0.5:
                date_columns += 1
        
        # If we have structured data patterns
        return numeric_columns >= 1 or date_columns >= 1
    
    def is_text_in_table(self, text_block: Dict) -> bool:
        """Check if a text block falls within any detected table region"""
        page = text_block["page"]
        
        if page not in self.table_regions:
            return False
        
        # Get text block position
        if "bbox" not in text_block:
            return False
        
        text_bbox = text_block["bbox"]  # [x0, y0, x1, y1]
        text_x0, text_y0, text_x1, text_y1 = text_bbox
        
        # Check against all table regions on this page
        for table_bbox in self.table_regions[page]:
            table_x0, table_y0, table_x1, table_y1 = table_bbox
            
            # Check if text block overlaps with table region
            # Allow small tolerance for text that might be slightly outside table borders
            tolerance = 5
            
            if (text_x0 >= table_x0 - tolerance and 
                text_x1 <= table_x1 + tolerance and
                text_y0 >= table_y0 - tolerance and
                text_y1 <= table_y1 + tolerance):
                return True
        
        return False
    
    def identify_table_of_contents(self, text_blocks: List[Dict]) -> None:
        """Identify table of contents pages and content"""
        # Step 1: Find TOC heading and identify TOC pages
        for block in text_blocks:
            text = block["text"].strip().lower()
            
            # Look for TOC headings
            toc_patterns = [
                r'^table\s+of\s+contents?$',
                r'^contents?$',
                r'^index$',
                r'^\s*toc\s*$',
            ]
            
            for pattern in toc_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    self.toc_pages.add(block["page"])
                    # Also check adjacent pages for multi-page TOCs
                    self.toc_pages.add(block["page"] + 1)
                    if block["page"] > 1:
                        self.toc_pages.add(block["page"] - 1)
                    break
        
        # Step 2: Identify TOC content patterns on TOC pages
        for block in text_blocks:
            if block["page"] in self.toc_pages:
                text = block["text"].strip()
                
                # Skip the TOC heading itself
                if self.is_toc_heading(text):
                    continue
                
                # Identify TOC entry patterns
                if self.is_toc_entry(text):
                    self.toc_content.add(text)
    
    def is_toc_heading(self, text: str) -> bool:
        """Check if text is a TOC heading (to preserve)"""
        text_lower = text.strip().lower()
        
        toc_heading_patterns = [
            r'^table\s+of\s+contents?$',
            r'^contents?$',
            r'^index$',
            r'^\s*toc\s*$',
        ]
        
        return any(re.match(pattern, text_lower) for pattern in toc_heading_patterns)
    
    def is_toc_entry(self, text: str) -> bool:
        """Identify table of contents entries to filter out"""
        text = text.strip()
        
        # Skip very short text
        if len(text) < 3:
            return False
        
        # TOC entry patterns
        toc_entry_patterns = [
            # Pattern: "1. Introduction .................. 5"
            r'.+\.{3,}.+\d+\s*$',
            
            # Pattern: "Chapter 1    Introduction    5"
            r'^.+\s+\d+\s*$',
            
            # Pattern: "1.1 Overview 10"
            r'^\d+(\.\d+)*\s+.+\s+\d+\s*$',
            
            # Pattern: "Introduction.....5" or "Introduction    5"
            r'^[^\.]+[\.\s]{2,}\d+\s*$',
            
            # Pattern: Just page numbers on their own line in TOC
            r'^\d{1,3}\s*$',
            
            # Pattern: "See page 15" or "Page 15"
            r'.*(see\s+)?page\s+\d+',
            
            # Pattern: Multiple numbers with dots (subsection page refs)
            r'^\d+\.\d+\s+\d+\.\d+\s+\d+',
            
            # Pattern: Title followed by page number with various separators
            r'^.+[\.\-_\s]{2,}\d+\s*$',
            
            # Pattern: Roman numerals with page numbers
            r'^[ivxlcdm]+[\.\s]+.+\s+\d+\s*$',
        ]
        
        for pattern in toc_entry_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        # Additional heuristic: If on a TOC page and contains page numbers
        if re.search(r'\b\d{1,3}\b', text):
            # Check if it looks like a TOC entry (has both text and numbers)
            words = text.split()
            has_text = any(word.isalpha() and len(word) > 2 for word in words)
            has_numbers = any(word.isdigit() for word in words)
            
            if has_text and has_numbers:
                return True
        
        return False
    
    def identify_table_patterns(self, text_blocks: List[Dict]) -> None:
        """Identify table content patterns to exclude from headings"""
        for block in text_blocks:
            text = block["text"].strip()
            
            # Table patterns to identify
            table_indicators = [
                # Version history table patterns
                r'^\d+\.\d+\s+\d+\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+\d{4}',
                
                # Table of contents patterns with page numbers
                r'^[\d\.]+\s+[\d\.]+$',  # Just numbers like "2.1 2.2"
                
                # Date patterns in tables
                r'^\d{1,2}\s+(JUNE|JULY|NOVEMBER|DECEMBER)\s+\d{4}',
                
                # Multiple numbers separated by spaces (likely table data)
                r'^\d+(\s+\d+)+$',
                
                # Copyright/page number patterns
                r'^©.*\d{4}$',
                r'^Page\s+\d+\s+of\s+\d+',
                r'^Version\s+\d{4}',
                r'May\s+\d{1,2},\s+\d{4}',
                
                # Table header patterns
                r'^Version\s+Date\s+Remarks$',
                r'^Syllabus\s+Days$',
            ]
            
            for pattern in table_indicators:
                if re.match(pattern, text, re.IGNORECASE):
                    self.table_patterns.add(text)
                    break
    
    def identify_headers_footers(self, text_blocks: List[Dict]) -> None:
        """Identify recurring headers and footers, but preserve large non-repeating footer content"""
        page_positions = {}
        
        for block in text_blocks:
            page = block["page"]
            y_pos = block["bbox"][1]
            text = block["text"].strip()
            
            if page not in page_positions:
                page_positions[page] = {"top": [], "bottom": []}
            
            # Top 15% of page (more restrictive for headers)
            if y_pos < block["page_height"] * 0.15:
                page_positions[page]["top"].append(text)
            # Bottom 15% of page
            elif y_pos > block["page_height"] * 0.85:
                page_positions[page]["bottom"].append(text)
        
        # Find patterns that repeat across pages
        all_tops = []
        all_bottoms = []
        
        for page_data in page_positions.values():
            all_tops.extend(page_data["top"])
            all_bottoms.extend(page_data["bottom"])
        
        top_counter = Counter(all_tops)
        bottom_counter = Counter(all_bottoms)
        
        # Mark as headers/footers ONLY if they appear on multiple pages AND are short
        min_occurrences = max(2, len(page_positions) // 3)
        
        # For headers - filter if recurring
        for text, count in top_counter.items():
            if count >= min_occurrences and not is_page_number(text):
                self.headers_footers.add(text)
        
        # For footers - be more selective
        for text, count in bottom_counter.items():
            if count >= min_occurrences:
                if (len(text) < 50 or
                    is_page_number(text) or
                    any(keyword in text.lower() for keyword in 
                        ['copyright', '©', 'page', 'confidential', 'proprietary', 'all rights reserved'])):
                    self.headers_footers.add(text)
                elif count >= len(page_positions) * 0.8:
                    self.headers_footers.add(text)
    
    def is_likely_table_content(self, text: str) -> bool:
        """Enhanced table content detection"""
        text = text.strip()
        
        # Already identified table patterns
        if text in self.table_patterns:
            return True
        
        # Additional table patterns
        table_patterns = [
            # Multiple numbers/dots pattern (table of contents)
            r'^\d+(\.\d+)*\s+\d+(\.\d+)*$',
            
            # Version/date patterns
            r'^\d+\.\d+.*\d{4}',
            
            # Multiple short words/numbers (likely table cells)
            r'^(\w{1,3}\s+){3,}',
            
            # Copyright and page info
            r'^©.*International.*Board',
            r'^Page\s+\d+',
            r'^May\s+\d+,\s+\d{4}',
            
            # Very short standalone text (likely table data)
            r'^\w{1,5}$',
        ]
        
        return any(re.match(pattern, text, re.IGNORECASE) for pattern in table_patterns)
    
    def is_valid_content_block(self, block: Dict) -> bool:
        """Check if a block contains valid content (not table/header/footer/TOC content)"""
        text = block["text"].strip()
        
        # Basic filters
        if (len(text) < 5 or
            text in self.table_patterns or
            text in self.headers_footers or
            text in self.toc_content or
            is_page_number(text) or
            self.is_likely_table_content(text)):
            return False
        
        # NEW: Strict visual table check - exclude any text inside detected tables
        if self.is_text_in_table(block):
            return False
        
        # Special case: Preserve TOC headings themselves
        if self.is_toc_heading(text):
            return True
        
        # Filter out TOC entries
        if self.is_toc_entry(text):
            return False
        
        return True

    def process_all_filters(self, text_blocks: List[Dict], pdf_path: str = None) -> None:
        """Run all filtering methods in the correct order"""
        # NEW: Visual table detection first (if PDF path is provided)
        if pdf_path:
            self.identify_visual_tables(pdf_path)
        
        # Order matters: TOC identification should come first
        self.identify_table_of_contents(text_blocks)
        self.identify_table_patterns(text_blocks)
        self.identify_headers_footers(text_blocks)
    
    def get_table_debug_info(self) -> Dict:
        """Get debug information about detected tables"""
        debug_info = {}
        for page, tables in self.visual_tables.items():
            debug_info[page] = []
            for table in tables:
                debug_info[page].append({
                    'bbox': table['bbox'],
                    'rows': table['rows'],
                    'cols': table['cols'],
                    'has_data': table['data'] is not None
                })
        return debug_info

