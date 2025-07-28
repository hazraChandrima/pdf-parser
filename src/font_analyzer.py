"""
Font pattern analysis for determining heading hierarchy
"""
from typing import List, Dict
from collections import Counter


class FontAnalyzer:
    def __init__(self, content_filter):
        self.content_filter = content_filter
        self.font_stats = None
    
    def analyze_font_patterns(self, text_blocks: List[Dict]) -> Dict:
        """Analyze font patterns for proper heading hierarchy"""
        # Filter out table content, headers/footers
        valid_blocks = []
        for block in text_blocks:
            if self.content_filter.is_valid_content_block(block):
                valid_blocks.append(block)
        
        if not valid_blocks:
            return {
                "body_font_size": 12.0,
                "body_font_family": "Arial",
                "font_size_hierarchy": []
            }
        
        # Get font size distribution
        font_sizes = [block["font_size"] for block in valid_blocks]
        size_counter = Counter(font_sizes)
        
        # Most common size is likely body text
        body_font_size = size_counter.most_common(1)[0][0]
        
        # Create hierarchy from unique sizes, sorted descending
        unique_sizes = sorted(set(font_sizes), reverse=True)
        
        # Separate heading sizes from body size
        heading_sizes = [size for size in unique_sizes if size > body_font_size]
        
        # Get most common font family
        font_families = [block["font_family"] for block in valid_blocks]
        body_font_family = Counter(font_families).most_common(1)[0][0]
        
        self.font_stats = {
            "body_font_size": body_font_size,
            "body_font_family": body_font_family,
            "font_size_hierarchy": heading_sizes + [body_font_size],
            "unique_sizes": unique_sizes
        }
        
        return self.font_stats
    
    def has_visual_distinction(self, block: Dict) -> bool:
        """Check if block has visual distinction from body text"""
        if not self.font_stats:
            return False
        
        is_bold = bool(block["flags"] & 16)
        is_italic = bool(block["flags"] & 2)
        is_larger = block["font_size"] > self.font_stats["body_font_size"]
        is_different_font = block["font_family"] != self.font_stats["body_font_family"]
        
        return is_bold or is_italic or is_larger or is_different_font
    
    def get_font_size_level(self, font_size: float) -> int:
        """Get heading level based on font size hierarchy"""
        if not self.font_stats or not self.font_stats["font_size_hierarchy"]:
            return 2
        
        hierarchy = self.font_stats["font_size_hierarchy"]
        body_size = self.font_stats["body_font_size"]
        
        # Find relative position in size hierarchy
        larger_sizes = [size for size in hierarchy if size > font_size]
        position = len(larger_sizes)
        
        if font_size > body_size + 2:
            return 1
        elif font_size > body_size:
            return 2
        else:
            return 3
