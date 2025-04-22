"""
Main entry point for the batchscan command-line tool.
"""
import argparse
import os
import sys
import time

from batchscan.core.batch_scanner import BatchScanner


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="batchscan",
        description="Batch scan and analyze images using AI",
    )
    
    parser.add_argument(
        "directory",
        help="Directory containing images to scan",
        nargs="?",
        default=".",
    )
    
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Scan directories recursively",
    )
    
    parser.add_argument(
        "-d", "--database",
        default="photos.db",
        help="Database file path (default: photos.db in current directory)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed processing information",
    )
    
    return parser.parse_args()


def main():
    """Main function to execute when the module is run."""
    args = parse_arguments()
    
    # Resolve relative paths
    directory = os.path.abspath(args.directory)
    database = os.path.abspath(args.database)
    
    print(f"Starting batch scan of: {directory}")
    print(f"Using database: {database}")

    # Initialize scanner
    scanner = BatchScanner(db_file=database)
    
    start_time = time.time()
    
    # Perform scan based on arguments
    if args.recursive:
        print(f"Scanning recursively...")
        results = scanner.scan_recursive(directory)
    else:
        results = scanner.scan_directory(directory)
    
    elapsed_time = time.time() - start_time
    
    # Print results
    print("\nScan completed!")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    
    if "error" in results:
        print(f"Error: {results['error']}")
        return 1
        
    if args.recursive:
        print(f"Directories scanned: {results['directories_scanned']}")
        
    print(f"Total images found: {results['total_images']}")
    print(f"Images processed: {results['processed']}")
    print(f"Images skipped (already processed): {results['skipped']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())