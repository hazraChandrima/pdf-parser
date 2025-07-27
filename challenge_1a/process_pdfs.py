#!/usr/bin/env python3
"""
Main PDF processing script for Adobe Hackathon Challenge 1a
Batch processes all PDFs in input directory and generates JSON outputs
"""
import os
import sys
import time
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.pdf_extractor import extract_pdf_outline


def process_single_pdf(pdf_path: Path, output_dir: Path) -> dict:
    """Process a single PDF file and return result info"""
    try:
        start_time = time.time()
        
        # Generate output path
        output_file = output_dir / f"{pdf_path.stem}.json"
        
        # Extract outline using the modular extractor
        result = extract_pdf_outline(str(pdf_path), str(output_file))
        
        processing_time = time.time() - start_time
        
        return {
            "file": pdf_path.name,
            "success": True,
            "processing_time": processing_time,
            "headings_count": len(result.get("outline", [])),
            "title": result.get("title", "Unknown"),
            "output_file": str(output_file)
        }
        
    except Exception as e:
        return {
            "file": pdf_path.name,
            "success": False,
            "error": str(e),
            "processing_time": 0,
            "headings_count": 0
        }


def process_pdfs():
    """Main function to process all PDFs in the input directory"""
    # Docker container paths as specified in README
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    
    # Validate directories
    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all PDF files
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in input directory")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    
    # Process PDFs
    total_start_time = time.time()
    results = []
    
    # Determine optimal number of workers (max 4 to stay within resource limits)
    num_workers = min(4, mp.cpu_count(), len(pdf_files))
    
    if len(pdf_files) == 1 or num_workers == 1:
        # Process sequentially for single file or single worker
        for pdf_file in pdf_files:
            print(f"Processing: {pdf_file.name}")
            result = process_single_pdf(pdf_file, output_dir)
            results.append(result)
            
            if result["success"]:
                print(f"  ✓ Completed in {result['processing_time']:.2f}s "
                      f"({result['headings_count']} headings)")
            else:
                print(f"  ✗ Failed: {result['error']}")
    else:
        # Process in parallel for multiple files
        print(f"Processing with {num_workers} workers...")
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            future_to_pdf = {
                executor.submit(process_single_pdf, pdf_file, output_dir): pdf_file 
                for pdf_file in pdf_files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_pdf):
                pdf_file = future_to_pdf[future]
                result = future.result()
                results.append(result)
                
                if result["success"]:
                    print(f"✓ {result['file']}: {result['processing_time']:.2f}s "
                          f"({result['headings_count']} headings)")
                else:
                    print(f"✗ {result['file']}: {result['error']}")
    
    # Summary
    total_time = time.time() - total_start_time
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    total_headings = sum(r["headings_count"] for r in results if r["success"])
    
    print(f"\n{'='*50}")
    print(f"Processing Summary:")
    print(f"  Total files: {len(pdf_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total headings extracted: {total_headings}")
    print(f"  Total processing time: {total_time:.2f} seconds")
    
    if successful > 0:
        avg_time = sum(r["processing_time"] for r in results if r["success"]) / successful
        print(f"  Average time per file: {avg_time:.2f} seconds")
    
    # List output files
    print(f"\nOutput files generated:")
    for result in results:
        if result["success"]:
            print(f"  {result['output_file']}")
    
    # Show any failures
    if failed > 0:
        print(f"\nFailed files:")
        for result in results:
            if not result["success"]:
                print(f"  {result['file']}: {result['error']}")


if __name__ == "__main__":
    try:
        process_pdfs()
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
