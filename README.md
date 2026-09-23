# LLM-SQL Data Analyst

A small toolkit that turns natural-language questions into read-only SQL queries, executes them against a MySQL/MariaDB database, and presents human-friendly summaries and optional visualizations using Google Gemini (via the google-genai SDK) and Streamlit.

This repository contains a lightweight pipeline that:

- Extracts schema metadata (and enriches it with short LLM-generated column descriptions).
- Uses Gemini to translate user questions into SQL (read-only SELECT/WITH only).
- Executes the generated SQL against a configured MySQL database.
- Uses Gemini again to convert results into a concise human-readable summary.
- Optionally generates Streamlit visualization code for display in the UI.

This is an experimental / demo project intended as an internship workspace and proof-of-concept.

## Features

- Natural language -> SQL generation using Google Gemini.
- Safe execution guard: only read-only queries are permitted.
- Schema metadata extraction with LLM-assisted column descriptions.
- Simple JSON-backed conversation memory to cache previous interactions.
- Streamlit UI to ask questions and show summaries, SQL, table preview, and suggested visualizations.

## Repo layout

- `app/`
	- `database_utils.py` - DB connection helpers, schema extraction, and query execution.
	- `main.py` - Pipeline orchestration (metadata -> SQL gen -> execute -> restructure -> memory store).
- `llm/`
	- `llm_chain.py` - LLM wrappers for SQL generation and result restructuring.
	- `memory.py` - Lightweight conversation memory (JSON file backed).
	- `visualization.py` - LLM-based Streamlit visualization code generator.
- `ui/`
	- `streamlit_app.py` - Streamlit web UI for interactive queries.
- `requirements.txt` - Python dependencies (suggested packages used by the code).
- `conversation_memory.json` - memory store created at runtime (may be empty)
- `output.json` / `output___.json` - schema metadata files created by `database_utils` (see notes).

## Quick prerequisites

- Python 3.11+ recommended.
- A MySQL-compatible database (MySQL or MariaDB) with credentials available.
- A Google Gemini API key (set as `GEMINI_API_KEY`) and access to the google-genai package.

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Environment variables

Create a `.env` file in the repository root with at least the following values:

```
GEMINI_API_KEY=your_gemini_api_key_here
user=<db_username>
password=<db_password>
host=<db_host>
database=<db_name>
```

Notes:
- `app.database_utils` uses `mysql.connector` (MySQL/MariaDB). Ensure the `user`, `password`, `host`, and `database` names are correct.
- The project has a few docstring/comments that mention PostgreSQL in places, but the actual code uses MySQL. Verify the DB type before running.

## How to generate schema metadata

This step inspects your database and (optionally) asks the LLM to generate short human-readable descriptions for columns.

```powershell
# Run the schema extractor (writes a JSON file with metadata)
python app\database_utils.py
```

The extractor writes a file named `output___.json` by default. The UI/pipeline (`app/main.py`) expects a file named `output.json` when loading cached metadata. After extracting metadata, either rename or copy the generated file:

```powershell
copy output___.json output.json
```

Tip: If you prefer, modify `app/database_utils.py` to write directly to `output.json` or update `app/main.py` to load the generated filename.

## Running the Streamlit UI

Start the interactive web UI:

```powershell
streamlit run ui\streamlit_app.py
```

The UI will let you enter natural-language questions. The app will:

- Load the schema context from `output.json`.
- Try to find a cached answer in `conversation_memory.json`.
<!-- - If none is found, call the LLM to generate SQL, execute it, and present a summary and optional visualization. -->

<!-- ## Running the pipeline from the command line

You can also run the pipeline programmatically (there's an example in `app/main.py`):

```powershell
python app\main.py
``` -->

Or call the `run_query_pipeline(user_question)` function from `app/main` in your own scripts.


## Known caveats and inconsistencies

- `app/database_utils.py` currently writes `output___.json` while `app/main.py` reads `output.json`. Either rename the file after generation or update one of the modules.
- Some docstrings mention PostgreSQL, but the implementation is MySQL-based (uses `mysql.connector`, backticks, and `ORDER BY RAND()`). Adjust docstrings or refactor the DB code if you intend to use PostgreSQL.
- The conversation memory LLM helper (`llm/memory.py`) uses Gemini for a context-aware retrieval step; it returns a simple dictionary with a `summary` when a relevant entry is found.

## Troubleshooting

- If you see connection errors, verify `.env` credentials and that your database allows connections from your machine.
- If the LLM fails to initialize, ensure `GEMINI_API_KEY` is set and valid.
- If Streamlit fails to render suggested visualizations, check the printed visualization code in the app logs and the `safe_globals` mapping used by `exec` (the generated code expects `st` and `df_results`).

## Suggested next steps / improvements

- Unify the output filename for schema metadata.
- Add unit tests around SQL sanitization and the memory store.
- Replace the simplistic memory retrieval with embedding-based similarity search for better recall.
- Add role-based access control and stricter SQL validation for production use.

## Contributing

If you'd like to contribute, fork the repo and open a PR. Small improvements like docs fixes, filename consistency, and tests are very welcome.

## License

This repository does not include a license file. Add a `LICENSE` if you plan to publish this project publicly.

---

If you want, I can also:

- fix the `output___.json` vs `output.json` mismatch automatically,
- add a `.env.example` file,
- or create a short CONTRIBUTING.md — tell me which and I will implement it.
