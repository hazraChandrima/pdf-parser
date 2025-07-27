"""
Content filtering for tables, headers, footers, and other non-heading content
"""
import re
from typing import List, Dict, Set
from collections import Counter
from .utils import is_page_number


class ContentFilter:
    def __init__(self):
        self.headers_footers: Set[str] = set()
        self.table_patterns: Set[str] = set()
    
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
            # Bottom 15% of page (but we'll be selective about what gets filtered)
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
        
        # For footers - be more selective, only filter if:
        # 1. They repeat across multiple pages AND
        # 2. They are short (likely page numbers, copyright, etc.) OR
        # 3. They are clearly boilerplate text
        for text, count in bottom_counter.items():
            if count >= min_occurrences:
                # Only filter short repetitive footers or obvious boilerplate
                if (len(text) < 50 or  # Short text like page numbers
                    is_page_number(text) or
                    any(keyword in text.lower() for keyword in 
                        ['copyright', '©', 'page', 'confidential', 'proprietary', 'all rights reserved'])):
                    self.headers_footers.add(text)
                # Large footers that repeat should be examined more carefully
                # Only filter if they appear on most pages (likely true footers)
                elif count >= len(page_positions) * 0.8:  # Appears on 80%+ of pages
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
        """Check if a block contains valid content (not table/header/footer)"""
        text = block["text"].strip()
        
        # Basic filters
        if (len(text) < 5 or
            text in self.table_patterns or
            text in self.headers_footers or
            is_page_number(text) or
            self.is_likely_table_content(text)):
            return False
        
        return True
