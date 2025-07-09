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
| filename   | error | topic                | topic                  | ... |
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

Set your API key in `.env` or as `SEMAPHORE_API_KEY`.

---

For more, see the code and docstrings! 