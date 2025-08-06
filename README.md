# Speech Scraper Pipeline

This project automates the process of extracting, summarizing, and storing speeches published on congressional websites. It fetches speech content from structured URLs, uses OpenAI to generate press release-style summaries, and stores the results in a MySQL database. The system supports flexible command-line execution, logging, and optional email summaries.

---

## Features

* 🔍 Scrapes speech content from structured URLs (House or Senate)
* 🧠 Uses OpenAI API to generate summaries and headlines
* 💾 Stores structured results in a MySQL database
* 🧪 Supports test mode using a local CSV file
* 📜 Robust logging and error handling

---

## Requirements

* Python 3.8+
* MySQL database
* OpenAI API key

Make sure to install dependencies!

## Usage

The program supports two modes using CLI flags:

```bash
python main.py [options]
```

### CLI Options

| Flag | Description                                                  |
| ---- | ------------------------------------------------------------ |
| `-t` | Test mode: processes a range of rows from a local CSV file   |
| `-p` | Production mode: pulls and processes speech data from TNS DB |

### Example

Run a test on the test CSV:

```bash
python main.py -t
```

Run the production scraper to process data from the TNS database:

```bash
python main.py -p
```

---

## File Structure

* `main.py` — Entry point for CLI parsing and execution control
* `url_functions.py` — Speech URL retrieval and parsing
* `db_functions.py` — MySQL connection and data insertion
* `email_utils.py` — Email sending utility for summary reports

---

## Configuration

### Database

Update `configs/db_config.yml` with your MySQL credentials:

```yaml
host: localhost
user: your_username
password: your_password
database: your_database
```

### OpenAI API

Save your API key to `utils/key.txt`.

---