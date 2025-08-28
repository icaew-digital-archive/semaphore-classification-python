#!/usr/bin/env python3
"""
Semaphore helper script that processes files and outputs Generic_UPWARD classifications sorted by score.

This script can also integrate with Preservica to download assets before classification.
It requires the DOWNLOAD_SCRIPT environment variable to be set to the path of 
download_preservica_assets.py script for Preservica integration to work.
"""

import argparse
import os
import sys
import json
import subprocess
from pathlib import Path
from semaphore_classification_client import SemaphoreClassificationClient
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DOWNLOAD_SCRIPT = os.getenv('DOWNLOAD_SCRIPT', 'fallback_path_here')

def classify_file(client: SemaphoreClassificationClient, file_path: str, 
                 threshold: Optional[int] = None, title: Optional[str] = None) -> Dict[str, Any]:
    """Classify a single file and return results."""
    try:
        # Try to classify as file first (for supported formats)
        result = client.classify_file(file_path, title=title, threshold=threshold)
    except Exception as e:
        # Fallback to reading as text
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            result = client.classify_text(text, title=title, threshold=threshold)
        except Exception as e2:
            return {"error": f"Failed to process {file_path}: {str(e2)}"}
    
    return result

def main():
    """
    Main function that processes files for classification.
    
    Features:
    - File classification using Semaphore Classification Service
    - Optional Preservica integration for asset downloading
    - Multiple output formats (JSON, CSV, human-readable)
    - Recursive directory processing
    """
    parser = argparse.ArgumentParser(description="Process files with Semaphore Classification Service. Can also download assets from Preservica before classification.")
    parser.add_argument("directory", nargs='?', default='./downloads', help="Directory containing files to classify (default: ./downloads)")
    parser.add_argument("--threshold", type=int, default=48, help="Classification threshold (1-99, default: 48)")
    parser.add_argument("--recursive", action="store_true", help="Process subdirectories recursively")
    parser.add_argument("--api-key", help="Semaphore API key (overrides environment variable)")
    parser.add_argument("--include-scoring", action="store_true", help="Include score values in output")
    parser.add_argument("--max-topics", type=int, default=10, help="Maximum number of topics to show per file")
    parser.add_argument("--json", action="store_true", help="Output in JSON format for programmatic use")
    parser.add_argument("--csv", type=str, metavar="FILENAME", help="Output in CSV format to specified file")
    parser.add_argument("--raw-json", action="store_true", help="Print full raw classification responses to stdout as JSON")
    parser.add_argument("--preservica-folder-ref", help="Download assets from Preservica folder before classification (requires DOWNLOAD_SCRIPT env var)")
    parser.add_argument("--keep-files", action="store_true", help="Keep downloaded files after processing (default: auto-delete when using Preservica)")
    
    args = parser.parse_args()
    
    # Handle Preservica download if specified
    if args.preservica_folder_ref:
        print(f"📥 Downloading assets from Preservica folder: {args.preservica_folder_ref}")
        
        # Validate download script path
        if not os.path.exists(DOWNLOAD_SCRIPT):
            print(f"❌ Download script not found at: {DOWNLOAD_SCRIPT}")
            print("   Please set the DOWNLOAD_SCRIPT environment variable or update the .env file")
            print("   Expected location: /home/digital-archivist/Documents/custom scripts/digital-archiving-scripts/pypreservica scripts/download_preservica_assets.py")
            sys.exit(1)
            
        try:
            # Call the download_preservica_assets.py script
            cmd = [
                sys.executable, DOWNLOAD_SCRIPT, "--use-asset-ref",
                "--folder", args.preservica_folder_ref,
                args.directory
            ]
            print(f"Running command: {' '.join(cmd)}")
            # Pass the current environment to the subprocess
            env = os.environ.copy()
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=os.getcwd(), env=env)
            print("✅ Preservica download completed successfully")
            if result.stdout:
                print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to download from Preservica: {e}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            sys.exit(1)
        except FileNotFoundError:
            print("❌ download_preservica_assets.py script not found in current directory")
            sys.exit(1)
    
    # Initialize client
    try:
        client = SemaphoreClassificationClient(api_key=args.api_key)
        client.authenticate()
        print(f"✅ Authenticated successfully")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        sys.exit(1)
    
    # Get files to process
    directory = Path(args.directory)
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)
    
    # Collect all files (no extension filtering)
    if args.recursive:
        files_to_process = [f for f in directory.rglob("*") if f.is_file()]
    else:
        files_to_process = [f for f in directory.glob("*") if f.is_file()]

    print(f"📁 Found {len(files_to_process)} files to process")
    
    # Process files
    results = []
    raw_results = []
    
    for file_path in files_to_process:
        file_result = {
            "file": str(file_path),
            "filename": file_path.name,
            "classifications": [],
            "error": None
        }
        
        try:
            result = classify_file(client, str(file_path), 
                                 threshold=args.threshold, 
                                 title=file_path.stem)
            
            # Save the raw result for this file
            if args.raw_json:
                raw_results.append({
                    "file": str(file_path),
                    "filename": file_path.name,
                    "raw_result": result
                })

            # Parse results
            if "error" not in result:
                parsed = client.parse_classification_results(result)
                
                # Get Generic_UPWARD classifications only
                generic_upward = parsed.get("classifications", {}).get("Generic_UPWARD", [])
                
                # Sort by score (descending) and remove duplicates
                unique_classifications = {}
                for item in generic_upward:
                    if item['score'] is not None:
                        value = item['value']
                        score = item['score']
                        if value not in unique_classifications or score > unique_classifications[value]:
                            unique_classifications[value] = score
                
                # Sort by score and take top results
                sorted_classifications = sorted(unique_classifications.items(), 
                                              key=lambda x: x[1], reverse=True)
                
                # Store classifications
                for value, score in sorted_classifications[:args.max_topics]:
                    file_result["classifications"].append({
                        "topic": value,
                        "score": score
                    })
                
                # Output based on format
                if args.json or args.csv:
                    results.append(file_result)
                else:
                    # Human-readable output
                    print(file_path)
                    for classification in file_result["classifications"]:
                        if args.include_scoring:
                            print(f"{classification['topic']} ({classification['score']:.2f})")
                        else:
                            print(f"{classification['topic']}")
                    print()
                
            else:
                file_result["error"] = result["error"]
                if args.raw_json:
                    raw_results.append({
                        "file": str(file_path),
                        "filename": file_path.name,
                        "raw_result": {"error": result["error"]}
                    })
                if args.json or args.csv:
                    results.append(file_result)
                else:
                    print(f"{file_path}")
                    print(f"Error: {result['error']}")
                    print()
                
        except Exception as e:
            file_result["error"] = str(e)
            if args.raw_json:
                raw_results.append({
                    "file": str(file_path),
                    "filename": file_path.name,
                    "raw_result": {"error": str(e)}
                })
            if args.json or args.csv:
                results.append(file_result)
            else:
                print(f"{file_path}")
                print(f"Failed: {e}")
                print()
    
    # Output structured results
    if args.json:
        print(json.dumps(results, indent=2))
    elif args.csv:
        import csv
        try:
            # Find the maximum number of topics for any file
            max_topics = 0
            for result in results:
                if not result["error"]:
                    num_topics = len(result["classifications"])
                    if num_topics > max_topics:
                        max_topics = num_topics

            # Prepare header: assetId, error, then 'topic' columns
            header = ["assetId", "error"] + ["dc:subject"] * max_topics

            with open(args.csv, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(header)

                for result in results:
                    row = [result["filename"]]
                    row.append(result["error"] if result["error"] else "")
                    if not result["error"]:
                        topics = [c["topic"] for c in result["classifications"]]
                        # Pad with empty strings if fewer topics than max
                        topics += [""] * (max_topics - len(topics))
                        row.extend(topics)
                    else:
                        # If error, fill topic columns with empty strings
                        row.extend([""] * max_topics)
                    writer.writerow(row)
            print(f"✅ CSV output written to: {args.csv}")
        except Exception as e:
            print(f"❌ Failed to write CSV file: {e}")
            sys.exit(1)

    if args.raw_json:
        print(json.dumps(raw_results, indent=2, ensure_ascii=False))

    # Cleanup: Delete downloaded files unless --keep-files is specified
    if args.preservica_folder_ref and not args.keep_files:
        print(f"🧹 Cleaning up downloaded files from {args.directory}")
        try:
            directory = Path(args.directory)
            if directory.exists():
                for file_path in directory.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        print(f"  Deleted: {file_path.name}")
                # Remove the directory if it's empty
                if not any(directory.iterdir()):
                    directory.rmdir()
                    print(f"  Removed empty directory: {directory}")
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️  Warning: Failed to cleanup some files: {e}")

if __name__ == "__main__":
    main() 
