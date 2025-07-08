# Semaphore Classification Service Python Client z

Python client for the Semaphore Classification Service with enhanced features.

## Install

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from semaphore_classification_client import SemaphoreClassificationClient

# API key will be loaded from .env file automatically
client = SemaphoreClassificationClient()
# Or pass API key directly: client = SemaphoreClassificationClient(api_key="your-api-key")
client.authenticate()
result = client.classify_text("Your text here")
print(result)
```

## Enhanced Features

### Text Classification with Parameters
```python
result = client.classify_text(
    text="Your document text",
    title="Document Title",
    threshold=48,  # 1-99, default = 48
    language="en"
)
```

### File Classification
```python
result = client.classify_file(
    file_path="document.pdf",
    title="Document Title",
    threshold=48
)
```

### Result Parsing
```python
# Parse raw XML into structured data
parsed = client.parse_classification_results(result)

# Get top classifications sorted by score
top_results = client.get_top_classifications(result, max_results=10)
```

### Semaphore Helper
```bash
# Process files and output Generic_UPWARD classifications (similar to Java helper)
python3 semaphore-helper.py /path/to/documents

# Include scoring in output
python3 semaphore-helper.py /path/to/documents --include-scoring

# Output in JSON format for programmatic use
python3 semaphore-helper.py /path/to/documents --json

# Output in CSV format for programmatic use
python3 semaphore-helper.py /path/to/documents --csv

# Process with custom settings
python3 semaphore-helper.py /path/to/documents \
  --threshold 48 \
  --max-topics 15 \
  --recursive

## API

- `SemaphoreClassificationClient(api_key=None)` - Initialize client
- `authenticate()` - Get session token
- `classify_text(text, title=None, threshold=None, language=None)` - Classify text
- `classify_file(file_path, title=None, threshold=None, language=None)` - Classify file
- `parse_classification_results(result)` - Parse XML response
- `get_top_classifications(result, max_results=10)` - Get top results
- `get_service_info()` - Get service info

## Environment

Set `SEMAPHORE_API_KEY` environment variable or pass API key directly.

### Using .env file (recommended)
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
SEMAPHORE_API_KEY=your-actual-api-key-here
```

## Files

- `semaphore_classification_client.py` - Enhanced main client
- `semaphore-helper.py` - Helper script for processing files (similar to Java helper) 