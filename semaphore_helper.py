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
import time
from pathlib import Path
from semaphore_classification_client import SemaphoreClassificationClient
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configuration
DOWNLOAD_SCRIPT = os.getenv('DOWNLOAD_SCRIPT', 'fallback_path_here')

def classify_file(client: SemaphoreClassificationClient, file_path: str, 
                 threshold: Optional[int] = None, title: Optional[str] = None) -> Dict[str, Any]:
    """Classify a single file and return results with automatic token refresh on 401 errors."""
    import requests
    
    def _classify_with_retry(use_file=True):
        """Helper function to classify with automatic token refresh on 401."""
        try:
            if use_file:
                return client.classify_file(file_path, title=title, threshold=threshold)
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                return client.classify_text(text, title=title, threshold=threshold)
        except requests.exceptions.HTTPError as e:
            # Check if it's a 401 Unauthorized error (token expired)
            if e.response is not None and e.response.status_code == 401:
                # Re-authenticate and retry once
                client.authenticate()
                if use_file:
                    return client.classify_file(file_path, title=title, threshold=threshold)
                else:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                    return client.classify_text(text, title=title, threshold=threshold)
            else:
                raise  # Re-raise if it's not a 401 error
    
    try:
        # Try to classify as file first (for supported formats)
        result = _classify_with_retry(use_file=True)
    except Exception as e:
        # Fallback to reading as text
        try:
            result = _classify_with_retry(use_file=False)
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
    parser.add_argument("--preservica-asset-refs", nargs="+", metavar="REF", help="Download one or more Preservica assets by reference before classification (e.g. 9bad5acf-e7a1-458a-927d-2d1e7f15974d)")
    parser.add_argument("--preservica-assets-file", metavar="FILE", help="Path to a text file of Preservica asset references, one per line")
    parser.add_argument("--keep-files", action="store_true", help="Keep downloaded files after processing (default: auto-delete when using Preservica)")
    parser.add_argument("--exclude-extensions", nargs="+", default=[], help="Exclude files with these extensions (e.g., mp4 avi mov)")
    parser.add_argument("--include-extensions", nargs="+", default=[], help="Only process files with these extensions (e.g., pdf txt doc)")
    
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
    
    # Handle direct asset ref download if specified
    if args.preservica_assets_file:
        try:
            with open(args.preservica_assets_file, 'r') as f:
                args.preservica_asset_refs = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(args.preservica_asset_refs)} reference(s) from {args.preservica_assets_file}")
        except Exception as e:
            print(f"Failed to read assets file: {e}")
            sys.exit(1)

    if args.preservica_asset_refs:
        print(f"Downloading {len(args.preservica_asset_refs)} asset(s) from Preservica")

        pres_username = os.getenv('USERNAME')
        pres_password = os.getenv('PASSWORD')
        pres_tenant = os.getenv('TENANT')
        pres_server = os.getenv('SERVER')

        missing = [name for name, val in [('USERNAME', pres_username), ('PASSWORD', pres_password),
                                           ('TENANT', pres_tenant), ('SERVER', pres_server)] if not val]
        if missing:
            print(f"Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)

        try:
            from pyPreservica import EntityAPI
        except ImportError:
            print("pyPreservica is not installed. Run: pip install pyPreservica")
            sys.exit(1)

        pres_client = EntityAPI(username=pres_username, password=pres_password,
                                tenant=pres_tenant, server=pres_server)

        download_dir = Path(args.directory)
        download_dir.mkdir(parents=True, exist_ok=True)

        for ref in args.preservica_asset_refs:
            print(f"  Downloading: {ref}")
            try:
                asset = pres_client.asset(ref)
                for bitstream in pres_client.bitstreams_for_asset(asset):
                    ext = Path(bitstream.filename).suffix
                    download_path = download_dir / f"{ref}{ext}"
                    pres_client.bitstream_content(bitstream, download_path)
                    print(f"    Saved: {download_path.name}")
            except Exception as e:
                print(f"  Failed to download {ref}: {e}")
                sys.exit(1)

        print("Downloaded assets from Preservica successfully")

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

    # Apply file type filtering
    if args.exclude_extensions or args.include_extensions:
        filtered_files = []
        for file_path in files_to_process:
            file_ext = file_path.suffix.lower().lstrip('.')
            
            # If include_extensions is specified, only process those extensions
            if args.include_extensions:
                if file_ext in [ext.lower().lstrip('.') for ext in args.include_extensions]:
                    filtered_files.append(file_path)
            # Otherwise, apply exclude_extensions filter
            elif args.exclude_extensions:
                if file_ext not in [ext.lower().lstrip('.') for ext in args.exclude_extensions]:
                    filtered_files.append(file_path)
            else:
                filtered_files.append(file_path)
        
        files_to_process = filtered_files
        print(f"🔍 After filtering: {len(files_to_process)} files to process")

    print(f"📁 Found {len(files_to_process)} files to process")
    
    # Process files
    results = []
    raw_results = []
    
    # Open CSV file for real-time writing if CSV output is requested
    csv_writer = None
    csv_file = None
    max_topics_seen = 0
    if args.csv:
        import csv
        csv_file = open(args.csv, 'w', newline='', encoding='utf-8')
        # Write header with max_topics columns (we'll update if needed)
        header = ["assetId", "error"] + ["dc:subject"] * args.max_topics
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(header)
    
    # Use tqdm for progress indication when processing multiple files
    if len(files_to_process) > 1:
        pbar = tqdm(files_to_process, desc="Processing files", unit="file")
    else:
        pbar = files_to_process
    
    try:
        for file_path in pbar:
            # Update progress bar with current filename
            if len(files_to_process) > 1:
                pbar.set_postfix(file=file_path.name[:30] + "..." if len(file_path.name) > 30 else file_path.name)
            
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
                    if args.json:
                        results.append(file_result)
                    elif args.csv:
                        # Write CSV row in real-time
                        num_topics = len(file_result["classifications"])
                        if num_topics > max_topics_seen:
                            max_topics_seen = num_topics
                        
                        row = [file_result["filename"]]
                        row.append("")  # error column (empty for success)
                        topics = [c["topic"] for c in file_result["classifications"]]
                        # Pad with empty strings if fewer topics than max_topics
                        topics += [""] * (args.max_topics - len(topics))
                        row.extend(topics)
                        csv_writer.writerow(row)
                        csv_file.flush()  # Ensure it's written to disk immediately
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
                    if args.json:
                        results.append(file_result)
                    elif args.csv:
                        # Write CSV row in real-time for error case
                        row = [file_result["filename"]]
                        row.append(file_result["error"])
                        # Fill topic columns with empty strings
                        row.extend([""] * args.max_topics)
                        csv_writer.writerow(row)
                        csv_file.flush()  # Ensure it's written to disk immediately
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
                if args.json:
                    results.append(file_result)
                elif args.csv:
                    # Write CSV row in real-time for exception case
                    row = [file_result["filename"]]
                    row.append(file_result["error"])
                    # Fill topic columns with empty strings
                    row.extend([""] * args.max_topics)
                    csv_writer.writerow(row)
                    csv_file.flush()  # Ensure it's written to disk immediately
                else:
                    print(f"{file_path}")
                    print(f"Failed: {e}")
                    print()
            
            # Sleep 1 second between requests to avoid rate limiting
            time.sleep(1)
    finally:
        # Close CSV file if it was opened
        if csv_file:
            csv_file.close()
            print(f"✅ CSV output written to: {args.csv}")
    
    # Output structured results
    if args.json:
        print(json.dumps(results, indent=2))

    if args.raw_json:
        print(json.dumps(raw_results, indent=2, ensure_ascii=False))

    # Cleanup: Delete downloaded files unless --keep-files is specified
    if (args.preservica_folder_ref or args.preservica_asset_refs or args.preservica_assets_file) and not args.keep_files:
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
