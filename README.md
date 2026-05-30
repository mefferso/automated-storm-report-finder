[README.md](https://github.com/user-attachments/files/28422703/README.md)
# fb-storm-report-hunter

Local Windows/Python proof-of-concept for scanning a curated list of Facebook pages for possible storm reports.

This tool uses Playwright to open a real browser with a persistent local profile. You manually log into Facebook once, and future scans reuse that profile.

## What it does

- Reads Facebook page URLs from `sources.csv`
- Reads search terms from `keywords.txt`
- Opens each source in a visible browser window
- Scrolls the page
- Expands visible "See more" / comment buttons when possible
- Extracts visible page text
- Finds keyword matches
- Writes possible storm-report candidates to `output/storm_candidates.csv`

## What it does NOT do

- It does not post, like, comment, message, or modify anything
- It does not bypass Facebook permissions
- It does not use the Facebook API
- It does not guarantee every comment will be visible
- It does not replace human verification for LSRs

## Windows setup

### 1. Install Python

Install Python 3.11 or newer from python.org.

During install, check:

```text
Add python.exe to PATH
```

### 2. Open PowerShell in this folder

```powershell
cd path\to\fb-storm-report-hunter
```

### 3. Create virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 4. Install packages

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### 5. First Facebook login

```powershell
python login_facebook_once.py
```

A browser will open. Log into Facebook manually. Close the browser after confirming you are logged in.

### 6. Run a scan

```powershell
python scan_facebook.py --max-sources 5
```

For a larger run:

```powershell
python scan_facebook.py --max-sources 68 --scrolls 8
```

Results go here:

```text
output/storm_candidates.csv
```

## Suggested operating mode

Start with 5 sources, make sure the browser stays logged in, then increase.

Do not run this aggressively. Keep the scroll count modest, and review results manually.
