import re
from typing import List, Dict, Set
from collections import Counter
from .utils import is_page_number


class ContentFilter:
    def __init__(self):
        self.headers_footers: Set[str] = set()
        self.table_patterns: Set[str] = set()
        self.toc_content: Set[str] = set()  # New: Store TOC content
        self.toc_pages: Set[int] = set()    # New: Track TOC page numbers
    
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
            text in self.toc_content or  # New: Filter TOC content
            is_page_number(text) or
            self.is_likely_table_content(text)):
            return False
        
        # Special case: Preserve TOC headings themselves
        if self.is_toc_heading(text):
            return True
        
        # Filter out TOC entries
        if self.is_toc_entry(text):
            return False
        
        return True

    def process_all_filters(self, text_blocks: List[Dict]) -> None:
        """Run all filtering methods in the correct order"""
        # Order matters: TOC identification should come first
        self.identify_table_of_contents(text_blocks)
        self.identify_table_patterns(text_blocks)
        self.identify_headers_footers(text_blocks)

