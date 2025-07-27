"""
Main PDF outline extraction module
"""
import pymupdf  # PyMuPDF
import json
from typing import List, Dict
from .text_processor import TextProcessor
from .content_filter import ContentFilter
from .font_analyzer import FontAnalyzer
from .heading_classifier import HeadingClassifier


class PDFOutlineExtractor:
    def __init__(self):
        self.content_filter = ContentFilter()
        self.font_analyzer = FontAnalyzer(self.content_filter)
        self.heading_classifier = HeadingClassifier(self.content_filter, self.font_analyzer)
        self.text_processor = TextProcessor()
    
    def extract_outline(self, pdf_path: str, debug_output: str = None) -> Dict:
        """Main method to extract outline from PDF"""
        try:
            # Step 1: Extract text with formatting at block level
            text_blocks = self.extract_formatted_text(pdf_path, debug_output)
            
            if not text_blocks:
                return {"title": "Empty Document", "outline": []}
            
            # Step 2: Identify and filter table content
            self.content_filter.identify_table_patterns(text_blocks)
            
            # Step 3: Identify headers/footers
            self.content_filter.identify_headers_footers(text_blocks)
            
            # Step 4: Analyze font patterns for hierarchy
            self.font_analyzer.analyze_font_patterns(text_blocks)
            
            # Step 5: Extract title
            title = self.heading_classifier.detect_title(text_blocks)
            
            # Step 6: Extract headings with improved filtering
            headings = self.heading_classifier.classify_headings(text_blocks)
            
            # Step 7: Merge multi-line headings
            headings = self.text_processor.merge_multiline_headings(headings)
            
            # Step 8: Final validation and cleanup
            headings = self.heading_classifier.validate_and_clean_headings(headings)
            
            return {
                "title": title,
                "outline": headings
            }
            
        except Exception as e:
            print(f"Error processing PDF: {e}")
            import traceback
            traceback.print_exc()
            return {"title": "Error Processing Document", "outline": []}

    def extract_formatted_text(self, pdf_path: str, debug_output: str = None) -> List[Dict]:
        """Extract text elements with formatting at block level to preserve complete headings"""
        doc = pymupdf.open(pdf_path)
        all_text_blocks = []
        
        debug_file = None
        if debug_output:
            debug_file = open(debug_output, 'w', encoding='utf-8')
            debug_file.write("PDF Block-Level Formatting Debug Output\n")
            debug_file.write("=" * 50 + "\n\n")
        
        try:
            for page_num, page in enumerate(doc, 1):
                page_blocks = self.text_processor.extract_formatted_text_blocks(page, page_num)
                all_text_blocks.extend(page_blocks)
                
                if debug_file:
                    self._write_debug_info(debug_file, page, page_num, page_blocks)
        
        finally:
            if debug_file:
                debug_file.close()
                print(f"Debug formatting information saved to: {debug_output}")
            doc.close()
        
        return all_text_blocks
    
    def _write_debug_info(self, debug_file, page, page_num: int, page_blocks: List[Dict]):
        """Write debug information for a page"""
        page_height = page.rect.height
        page_width = page.rect.width
        
        debug_file.write(f"PAGE {page_num}\n")
        debug_file.write(f"Page dimensions: {page_width:.1f} x {page_height:.1f}\n")
        debug_file.write("-" * 40 + "\n")
        
        for i, block in enumerate(page_blocks, 1):
            is_bold = bool(block["flags"] & 16)
            is_italic = bool(block["flags"] & 2)
            
            debug_file.write(f"Block {i}:\n")
            debug_file.write(f"  Text: '{block['text']}'\n")
            debug_file.write(f"  Font: {block['font_family']}\n")
            debug_file.write(f"  Size: {block['font_size']:.1f}\n")
            debug_file.write(f"  Flags: {block['flags']} (Bold: {is_bold}, Italic: {is_italic})\n")
            debug_file.write(f"  BBox: {block['bbox']}\n")
            debug_file.write("\n")
        
        debug_file.write(f"End of Page {page_num}\n")
        debug_file.write("=" * 50 + "\n\n")


def extract_pdf_outline(pdf_path: str, output_path: str = None, debug_path: str = None) -> Dict:
    """Extract outline from PDF - Main function"""
    extractor = PDFOutlineExtractor()
    result = extractor.extract_outline(pdf_path, debug_path)
    
    # Validate output format
    if not isinstance(result, dict) or "title" not in result or "outline" not in result:
        result = {"title": "Processing Error", "outline": []}
    
    if not isinstance(result["outline"], list):
        result["outline"] = []
    
    # Validate each heading
    validated_outline = []
    for heading in result["outline"]:
        if (isinstance(heading, dict) and 
            "level" in heading and 
            "text" in heading and 
            "page" in heading and
            heading["level"] in ["H1", "H2", "H3"]):
            validated_outline.append(heading)
    
    result["outline"] = validated_outline
    
    # Save to file if requested
    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Output saved to {output_path}")
        except Exception as e:
            print(f"Error saving output: {e}")
    
    return result
