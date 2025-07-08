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
    parser.add_argument("--csv", action="store_true", help="Output in CSV format for programmatic use")
    
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
        import sys
        writer = csv.writer(sys.stdout)
        writer.writerow(["file", "filename", "topic", "score", "error"])
        for result in results:
            if result["error"]:
                writer.writerow([result["file"], result["filename"], "", "", result["error"]])
            else:
                for classification in result["classifications"]:
                    writer.writerow([
                        result["file"], 
                        result["filename"], 
                        classification["topic"], 
                        classification["score"],
                        ""
                    ])

if __name__ == "__main__":
    main() 