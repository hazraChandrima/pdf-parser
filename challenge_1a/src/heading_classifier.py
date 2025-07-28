import re
from typing import List, Dict, Optional
from .utils import is_left_or_center_aligned, is_footer_area, clean_heading_text


class HeadingClassifier:
    def __init__(self, content_filter, font_analyzer):
        self.content_filter = content_filter
        self.font_analyzer = font_analyzer
        self.document_title = None  # Store detected title
    
    def classify_headings(self, text_blocks: List[Dict]) -> List[Dict]:
        """Classify text blocks as headings with proper filtering"""
        # First detect the title
        self.document_title = self.detect_title(text_blocks)
        
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
        """Enhanced heading validation with footer content consideration and title exclusion"""
        text = block["text"].strip()
        
        # Exclude the document title from being classified as a heading
        # Check both exact match and if this block's text is contained in the title
        if self.document_title:
            clean_block_text = clean_heading_text(text)
            clean_title = clean_heading_text(self.document_title)
            
            # Exact match
            if clean_block_text == clean_title:
                return False
            
            # Check if this block's text is part of the merged title
            if (len(clean_block_text) > 5 and 
                clean_block_text in clean_title and 
                len(clean_block_text) / len(clean_title) > 0.3):  # At least 30% of title
                return False
        
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
            
            # Skip if it's the document title or part of it
            if self.document_title:
                clean_text_heading = clean_heading_text(text)
                clean_title = clean_heading_text(self.document_title)
                
                # Exact match
                if clean_text_heading == clean_title:
                    continue
                
                # Check if this heading text is a significant part of the title
                if (len(clean_text_heading) > 5 and 
                    clean_text_heading in clean_title and 
                    len(clean_text_heading) / len(clean_title) > 0.3):
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
        """Detect document title by finding the biggest text on first page(s) and merging nearby blocks"""
        # Focus on first 2 pages only
        early_blocks = [b for b in text_blocks if b["page"] <= 2]
        
        if not early_blocks:
            return "Untitled Document"
    
    def _group_nearby_title_blocks(self, blocks: List[Dict]) -> List[List[Dict]]:
        """Group text blocks that are close together and could be part of the same title"""
        if not blocks:
            return []
        
        # Sort blocks by page, then by vertical position (y-coordinate)
        sorted_blocks = sorted(blocks, key=lambda b: (
            b["page"], 
            b["bbox"][1] if "bbox" in b else 0
        ))
        
        groups = []
        current_group = [sorted_blocks[0]]
        
        for i in range(1, len(sorted_blocks)):
            current_block = sorted_blocks[i]
            previous_block = sorted_blocks[i-1]
            
            # Check if blocks should be grouped together
            if self._should_merge_title_blocks(previous_block, current_block):
                current_group.append(current_block)
            else:
                # Start a new group
                if current_group:
                    groups.append(current_group)
                current_group = [current_block]
        
        # Add the last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_merge_title_blocks(self, block1: Dict, block2: Dict) -> bool:
        """Determine if two blocks should be merged as part of the same title"""
        # Must be on the same page
        if block1["page"] != block2["page"]:
            return False
        
        # Check font size similarity (within 3 points)
        font_diff = abs(block1["font_size"] - block2["font_size"])
        if font_diff > 3:
            return False
        
        # Check vertical spacing
        if "bbox" in block1 and "bbox" in block2:
            # Get bottom of first block and top of second block
            block1_bottom = block1["bbox"][3]  # y2 coordinate
            block2_top = block2["bbox"][1]     # y1 coordinate
            
            # Calculate vertical gap
            vertical_gap = abs(block2_top - block1_bottom)
            
            # If gap is small relative to font size, they're likely part of same title
            avg_font_size = (block1["font_size"] + block2["font_size"]) / 2
            max_gap = avg_font_size * 1.5  # Allow gap up to 1.5x the font size
            
            if vertical_gap <= max_gap:
                return True
        
        # Fallback: if we don't have bbox info, use text characteristics
        text1 = block1["text"].strip()
        text2 = block2["text"].strip()
        
        # If both blocks are short and look like title parts, merge them
        if (len(text1) <= 50 and len(text2) <= 50 and 
            not text1.endswith('.') and not text2.startswith('.')):
            return True
        
        return False
    
    def _merge_title_group(self, group: List[Dict]) -> str:
        """Merge a group of blocks into a single title string"""
        if not group:
            return ""
        
        # Sort blocks by vertical position (top to bottom)
        sorted_group = sorted(group, key=lambda b: b["bbox"][1] if "bbox" in b else 0)
        
        merged_parts = []
        for block in sorted_group:
            text = block["text"].strip()
            
            # Skip problematic individual parts
            if (len(text) < 1 or
                text in self.content_filter.table_patterns or
                self.content_filter.is_likely_table_content(text)):
                continue
            
            merged_parts.append(text)
        
        if not merged_parts:
            return ""
        
        # Join with space and clean up
        merged_text = " ".join(merged_parts)
        
        # Clean up multiple spaces and normalize
        merged_text = re.sub(r'\s+', ' ', merged_text).strip()
        
        return clean_heading_text(merged_text)
        
        # Find the maximum font size on the first pages
        max_font_size = max(block["font_size"] for block in early_blocks)
        
        # Get all blocks with the maximum font size or very close to it (within 2 points)
        largest_text_blocks = [
            block for block in early_blocks 
            if abs(block["font_size"] - max_font_size) <= 2
        ]
        
        # Group nearby blocks that could be part of the same title
        title_groups = self._group_nearby_title_blocks(largest_text_blocks)
        
        candidates = []
        
        for group in title_groups:
            # Merge the group into a single title candidate
            merged_text = self._merge_title_group(group)
            
            if not merged_text:
                continue
                
            # Use the first block's properties for positioning
            primary_block = group[0]
            # Skip problematic content for the merged text
            if (len(merged_text) < 5 or
                len(merged_text) > 300 or  # Allow longer titles since we're merging
                merged_text in self.content_filter.table_patterns or
                merged_text in self.content_filter.headers_footers or
                self.content_filter.is_likely_table_content(merged_text)):
                continue
            
            # Skip if it looks like header/footer content
            if any(keyword in merged_text.lower() for keyword in 
                   ['page', 'copyright', '©', 'confidential', 'proprietary', 'draft']):
                continue
            
            # Calculate position score (prefer upper part of page)
            y_position = primary_block["bbox"][1] if "bbox" in primary_block else 0
            page_height = primary_block.get("page_height", 792)  # Default PDF height
            position_ratio = 1 - (y_position / page_height)
            
            score = 0
            
            # Font size scoring - boost for groups with consistent large fonts
            avg_font_size = sum(block["font_size"] for block in group) / len(group)
            score += 100 + (avg_font_size - max_font_size) * 10  # Bonus for larger fonts
            
            # Group size bonus - multi-block titles often more legitimate
            if len(group) > 1:
                score += 20 * len(group)  # Bonus for merged blocks
            
            # Position scoring (prefer upper part of page)
            score += position_ratio * 50
            
            # Page preference (first page most likely)
            if primary_block["page"] == 1:
                score += 30
            elif primary_block["page"] == 2:
                score += 10
            
            # Content quality indicators
            word_count = len(merged_text.split())
            if 2 <= word_count <= 20:  # Good title length
                score += 20
            elif word_count <= 1:
                score -= 20  # Single words less likely to be titles
            elif word_count > 30:
                score -= 30  # Very long text less likely to be title
            
            # Prefer text that looks like a title
            if merged_text[0].isupper() and not merged_text.isupper():  # Title case
                score += 15
            elif merged_text.istitle():  # Proper title case
                score += 25
            elif merged_text.isupper():  # All caps might be title
                score += 10
            
            # Penalize if it looks like a section heading
            if re.match(r'^\d+\.', merged_text) or merged_text.endswith(':'):
                score -= 40
            
            # Boost for common title words
            title_words = ['foundation', 'level', 'extension', 'overview', 'guide', 
                          'manual', 'report', 'study', 'analysis', 'framework']
            if any(word in merged_text.lower() for word in title_words):
                score += 15
            
            candidates.append({
                "text": merged_text, 
                "score": score,
                "font_size": avg_font_size,
                "page": primary_block["page"],
                "block_count": len(group)
            })
        
        if candidates:
            # Sort by score, then by font size, then by page
            candidates.sort(key=lambda x: (x["score"], x["font_size"], -x["page"]), reverse=True)
            best = candidates[0]
            return clean_heading_text(best["text"])
        
        # Fallback: try to find any reasonably sized text on first page
        first_page_blocks = [b for b in text_blocks if b["page"] == 1]
        if first_page_blocks:
            # Sort by font size and position
            first_page_blocks.sort(key=lambda x: (x["font_size"], -x["bbox"][1] if "bbox" in x else 0), reverse=True)
            
            for block in first_page_blocks[:5]:  # Check top 5 candidates
                text = block["text"].strip()
                if (5 <= len(text) <= 100 and 
                    not self.content_filter.is_likely_table_content(text) and
                    text not in self.content_filter.headers_footers):
                    return clean_heading_text(text)
        
        return "Untitled Document"
    
    def get_document_title(self) -> Optional[str]:
        """Get the detected document title"""
        return self.document_title
