"""
Text processing utilities for PDF content
"""
from typing import Dict, List
from .utils import get_representative_span, get_block_bbox


class TextProcessor:
    def __init__(self):
        pass
    
    def reconstruct_block_text(self, block: Dict) -> str:
        """Reconstruct complete text from a block preserving the full heading text"""
        all_text = []
        
        for line in block["lines"]:
            line_text = ""
            prev_span_end = None
            
            # Sort spans by x-position
            sorted_spans = sorted(line["spans"], key=lambda s: s["bbox"][0])
            
            for span in sorted_spans:
                span_text = span["text"]
                span_start_x = span["bbox"][0]
                
                # Add spacing between spans if needed
                if prev_span_end and span_start_x - prev_span_end > 3:
                    if not line_text.endswith(' '):
                        line_text += " "
                
                line_text += span_text
                prev_span_end = span["bbox"][2]
            
            if line_text.strip():
                all_text.append(line_text.strip())
        
        # Join lines with spaces for headings that might span multiple lines
        return " ".join(all_text)
    
    def extract_formatted_text_blocks(self, page, page_num: int) -> List[Dict]:
        """Extract text blocks with formatting from a single page"""
        text_dict = page.get_text("dict")
        page_height = page.rect.height
        page_width = page.rect.width
        
        text_blocks = []
        
        for block_idx, block in enumerate(text_dict["blocks"]):
            if "lines" in block:  # Text block
                # Reconstruct complete text for the entire block
                block_text = self.reconstruct_block_text(block)
                
                if block_text.strip():
                    # Get representative formatting for the block
                    representative_span = get_representative_span(block)
                    
                    if representative_span:
                        text_block = {
                            "text": block_text.strip(),
                            "font_size": round(representative_span["size"], 1),
                            "font_family": representative_span["font"],
                            "flags": representative_span["flags"],
                            "bbox": get_block_bbox(block),
                            "page": page_num,
                            "page_height": page_height,
                            "page_width": page_width,
                            "block_type": "text"
                        }
                        text_blocks.append(text_block)
        
        return text_blocks
    
    def merge_multiline_headings(self, headings: List[Dict]) -> List[Dict]:
        """Merge headings that span multiple lines"""
        if not headings:
            return []
        
        merged = []
        i = 0
        
        while i < len(headings):
            current = headings[i]
            
            # Check if next heading should be merged
            if i + 1 < len(headings):
                next_heading = headings[i + 1]
                
                if self.should_merge_headings(current, next_heading):
                    merged_text = f"{current['text']} {next_heading['text']}"
                    merged.append({
                        "level": current["level"],
                        "text": merged_text.strip(),
                        "page": current["page"]
                    })
                    i += 2
                    continue
            
            merged.append({
                "level": current["level"],
                "text": current["text"],
                "page": current["page"]
            })
            i += 1
        
        return merged
    
    def should_merge_headings(self, heading1: Dict, heading2: Dict) -> bool:
        """Check if two headings should be merged"""
        # Must be on same page and same level
        if (heading1["page"] != heading2["page"] or 
            heading1["level"] != heading2["level"]):
            return False
        
        # Check vertical proximity
        y1 = heading1["bbox"][3]
        y2 = heading2["bbox"][1]
        if y2 - y1 > 30:
            return False
        
        # Don't merge if first heading ends with period
        if heading1["text"].rstrip().endswith('.'):
            return False
        
        # Check combined length is reasonable
        combined_length = len(heading1["text"]) + len(heading2["text"])
        if combined_length > 150:
            return False
        
        return True
