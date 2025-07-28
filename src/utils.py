"""
Utility functions for PDF processing
"""
import re
from typing import List, Dict


def is_left_or_center_aligned(block: Dict) -> bool:
    """Check if text is left or center aligned"""
    x_position = block["bbox"][0]
    page_width = block["page_width"]
    center_x = page_width / 2
    
    return (x_position < page_width * 0.7 or 
            abs(x_position - center_x) < page_width * 0.25)


def is_page_number(text: str) -> bool:
    """Check if text is a page number"""
    text = text.strip()
    
    patterns = [
        r'^\d{1,3}$',
        r'^Page\s+\d+',
        r'^\d+\s+of\s+\d+$',
        r'^[ivxlcdm]{1,6}$'
    ]
    
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in patterns)


def is_footer_area(block: Dict) -> bool:
    """Check if block is in footer area"""
    y_position = block["bbox"][1]
    page_height = block["page_height"]
    return y_position > page_height * 0.85


def get_block_bbox(block: Dict) -> List[float]:
    """Get bounding box for entire block"""
    if not block["lines"]:
        return [0, 0, 0, 0]
    
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')
    
    for line in block["lines"]:
        for span in line["spans"]:
            bbox = span["bbox"]
            min_x = min(min_x, bbox[0])
            min_y = min(min_y, bbox[1])
            max_x = max(max_x, bbox[2])
            max_y = max(max_y, bbox[3])
    
    return [min_x, min_y, max_x, max_y]


def get_representative_span(block: Dict) -> Dict:
    """Get representative span for formatting info, preferring largest or most prominent"""
    all_spans = []
    for line in block["lines"]:
        all_spans.extend(line["spans"])
    
    if not all_spans:
        return None
    
    # Filter out empty spans
    non_empty_spans = [s for s in all_spans if s["text"].strip()]
    if not non_empty_spans:
        return all_spans[0]
    
    # Prefer spans with formatting (bold, larger size) or longest text
    def span_priority(span):
        text_length = len(span["text"].strip())
        is_bold = bool(span["flags"] & 16)
        font_size = span["size"]
        
        priority = text_length
        if is_bold:
            priority += 100
        priority += font_size * 2
        
        return priority
    
    return max(non_empty_spans, key=span_priority)


def clean_heading_text(text: str) -> str:
    """Clean heading text"""
    # Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # Remove leading bullets
    cleaned = re.sub(r'^[\•\-\*\+►▪▫◦‣⁃\s]+', '', cleaned)
    
    # Remove trailing periods if not abbreviations
    if (cleaned.endswith('.') and 
        len(cleaned.split()) > 1 and 
        len(cleaned.split()[-1]) > 3):
        cleaned = cleaned.rstrip('.')
    
    return cleaned.strip()


def clean_title_text(text: str) -> str:
    """Clean title text"""
    cleaned = re.sub(r'\s+', ' ', text.strip())
    return cleaned
