# Semaphore Classification Service Python Client

A Python client and CLI for the Semaphore Classification Service.

## Install

```bash
pip install -r requirements.txt
```

## Usage

### Python Client

```python
from semaphore_classification_client import SemaphoreClassificationClient

client = SemaphoreClassificationClient()  # Loads API key from .env or env var
client.authenticate()
result = client.classify_text("Your text here")
print(result)
```

### CLI Helper

Process a directory of files and output results:

```bash
python3 semaphore_helper.py /path/to/documents
```

**Options:**
- `--include-scoring` — Show scores in terminal output
- `--json` — Output all results as JSON to terminal
- `--csv results.csv` — Output results as a CSV file (one row per file, topics as columns)
- `--raw-json` — Print full, unfiltered API responses to terminal
- `--threshold 48` — Set classification threshold (default: 48)
- `--max-topics 10` — Max topics per file (default: 10)
- `--recursive` — Process subdirectories

**Example CSV Output:**
| assetId    | error | dc:subject           | dc:subject             | ... |
|------------|-------|----------------------|------------------------|-----|
| file1.pdf  |       | Topic A              | Topic B                |     |
| file2.pdf  |       | Topic C              |                        |     |

## API Overview

- `SemaphoreClassificationClient(api_key=None)`
- `authenticate()`
- `classify_text(text, ...)`
- `classify_file(file_path, ...)`
- `parse_classification_results(result)`
- `get_top_classifications(result, max_results=10)`
- `get_service_info()`

## Environment

Create a `.env` file in the project root with the following variables:

```bash
# Semaphore API key
SEMAPHORE_API_KEY=your_api_key_here

# Path to the download_preservica_assets.py script (for Preservica integration)
DOWNLOAD_SCRIPT=/path/to/your/download_preservica_assets.py
```


---

For more, see the code and docstrings! 