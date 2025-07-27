"""
Heading detection and classification
"""
import re
from typing import List, Dict
from .utils import is_left_or_center_aligned, is_footer_area, clean_heading_text


class HeadingClassifier:
    def __init__(self, content_filter, font_analyzer):
        self.content_filter = content_filter
        self.font_analyzer = font_analyzer
    
    def classify_headings(self, text_blocks: List[Dict]) -> List[Dict]:
        """Classify text blocks as headings with proper filtering"""
        headings = []
        
        for block in text_blocks:
            if self.is_valid_heading(block):
                level = self.determine_heading_level(block)
                clean_text = clean_heading_text(block["text"])
                
                headings.append({
                    "level": level,
                    "text": clean_text,
                    "page": block["page"],
                    "font_size": block["font_size"],
                    "bbox": block["bbox"]
                })
        
        return headings
    
    def is_valid_heading(self, block: Dict) -> bool:
        """Enhanced heading validation with footer content consideration"""
        text = block["text"].strip()
        
        # Basic filters
        if (len(text) < 3 or
            len(text) > 200 or
            text in self.content_filter.table_patterns or
            self.content_filter.is_likely_table_content(text)):
            return False
        
        # Check if it's in headers_footers, but give large footer content a chance
        if text in self.content_filter.headers_footers:
            # If it's substantial content in footer area, consider it
            if (len(text) > 30 and  # Substantial text
                is_footer_area(block) and  # In footer area
                not any(keyword in text.lower() for keyword in 
                       ['copyright', '©', 'page', 'confidential', 'proprietary'])):
                # Allow it to be considered as heading if it has other heading characteristics
                pass
            else:
                return False
        
        # Position check - must be left or center aligned
        if not is_left_or_center_aligned(block):
            return False
        
        # Visual distinction check
        has_visual_distinction = self.font_analyzer.has_visual_distinction(block)
        
        # Check for heading patterns
        is_numbered_heading = re.match(r'^\d+\.', text)
        is_subsection = re.match(r'^\d+\.\d+', text)
        is_section_name = any(word in text.lower() for word in 
                             ["introduction", "overview", "content", "references", 
                              "acknowledgements", "history", "outcomes"])
        
        # Accept if it has visual distinction AND looks like a heading
        if has_visual_distinction:
            # Must look like a proper heading
            if (is_numbered_heading or is_subsection or is_section_name or
                text.endswith(':') or 
                (text[0].isupper() and len(text.split()) <= 10)):
                return True
        
        return False
    
    def determine_heading_level(self, block: Dict) -> str:
        """Determine heading level based on font size and content"""
        text = block["text"].strip()
        font_size = block["font_size"]
        
        # Content-based classification
        if re.match(r'^\d+\.', text):  # "1.", "2.", etc.
            return "H1"
        elif re.match(r'^\d+\.\d+', text):  # "2.1", "2.2", etc.
            return "H2"
        elif text in ["Revision History", "Table of Contents", "Acknowledgements"]:
            return "H1"
        
        # Font size-based classification
        font_level = self.font_analyzer.get_font_size_level(font_size)
        return f"H{font_level}"
    
    def validate_and_clean_headings(self, headings: List[Dict]) -> List[Dict]:
        """Final validation and cleanup of headings"""
        validated = []
        
        for heading in headings:
            text = heading["text"].strip()
            
            # Skip very short or very long text
            if len(text) < 3 or len(text) > 200:
                continue
            
            # Skip if it looks like table content
            if self.content_filter.is_likely_table_content(text):
                continue
            
            # Clean the text
            cleaned_text = clean_heading_text(text)
            
            if len(cleaned_text) >= 3:
                validated.append({
                    "level": heading["level"],
                    "text": cleaned_text,
                    "page": heading["page"]
                })
        
        return validated
    
    def detect_title(self, text_blocks: List[Dict]) -> str:
        """Detect document title"""
        # Look at first few pages
        early_blocks = [b for b in text_blocks if b["page"] <= 2]
        candidates = []
        
        for block in early_blocks:
            text = block["text"].strip()
            
            # Skip problematic content
            if (len(text) < 5 or
                text in self.content_filter.table_patterns or
                text in self.content_filter.headers_footers or
                self.content_filter.is_likely_table_content(text)):
                continue
            
            # Look for title characteristics
            score = 0
            
            # Font size scoring
            if block["font_size"] >= 20:
                score += 20
            elif block["font_size"] >= 16:
                score += 15
            elif block["font_size"] >= 14:
                score += 10
            
            # Position scoring (prefer upper part of page)
            y_position = block["bbox"][1]
            position_ratio = 1 - (y_position / block["page_height"])
            score += position_ratio * 15
            
            # Page preference (first page most likely)
            score += (3 - block["page"]) * 10
            
            # Content indicators
            if any(word in text.lower() for word in ["foundation", "level", "extension", "overview"]):
                score += 15
            
            # Length preference
            if 10 <= len(text) <= 100:
                score += 10
            
            candidates.append({"text": text, "score": score})
        
        if candidates:
            best = max(candidates, key=lambda x: x["score"])
            return clean_heading_text(best["text"])
        
        return "Untitled Document"
