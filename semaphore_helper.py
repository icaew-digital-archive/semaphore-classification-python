#!/usr/bin/env python3
"""
Semaphore helper script that processes files and outputs Generic_UPWARD classifications sorted by score.
Similar to the Java-based semaphore-helper.py but using the Python client.
"""

import argparse
import os
import sys
import json
from pathlib import Path
from semaphore_classification_client import SemaphoreClassificationClient
from typing import Optional, Dict, Any

def get_supported_extensions():
    """Return list of file extensions that are likely to contain text."""
    return [
        '.txt', '.md', '.rst', '.py', '.js', '.html', '.htm', '.xml', '.json',
        '.csv', '.tsv', '.log', '.cfg', '.conf', '.ini', '.yaml', '.yml',
        '.doc', '.docx', '.pdf', '.rtf', '.odt', '.pages',
        '.xls', '.xlsx', '.ods', '.numbers',
        '.ppt', '.pptx', '.odp', '.key'
    ]

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
    parser = argparse.ArgumentParser(description="Process files with Semaphore Classification Service")
    parser.add_argument("directory", help="Directory containing files to classify")
    parser.add_argument("--threshold", type=int, default=48, help="Classification threshold (1-99, default: 48)")
    parser.add_argument("--recursive", action="store_true", help="Process subdirectories recursively")
    parser.add_argument("--api-key", help="Semaphore API key (overrides environment variable)")
    parser.add_argument("--include-scoring", action="store_true", help="Include score values in output")
    parser.add_argument("--max-topics", type=int, default=10, help="Maximum number of topics to show per file")
    parser.add_argument("--json", action="store_true", help="Output in JSON format for programmatic use")
    parser.add_argument("--csv", type=str, metavar="FILENAME", help="Output in CSV format to specified file")
    parser.add_argument("--raw-json", action="store_true", help="Print full raw classification responses to stdout as JSON")
    
    args = parser.parse_args()
    
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
    
    # Collect files
    files_to_process = []
    extensions = get_supported_extensions()
    
    if args.recursive:
        for ext in extensions:
            files_to_process.extend(directory.rglob(f"*{ext}"))
    else:
        for ext in extensions:
            files_to_process.extend(directory.glob(f"*{ext}"))
    
    files_to_process = [f for f in files_to_process if f.is_file()]
    
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

            # Prepare header: filename, error, then 'topic' columns
            header = ["filename", "error"] + ["topic"] * max_topics

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

if __name__ == "__main__":
    main() 