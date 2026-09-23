"""
app/database_utils.py: Manages MySQL connection, metadata extraction, and query execution.
"""
from typing import Any, Dict, List, Tuple
import json
import os

from dotenv import load_dotenv
import mysql.connector
from google import genai
from google.genai import types

load_dotenv()  # Load environment variables from .env file

# GEMINI API key for LLM calls
api_key = os.getenv("GEMINI_API_KEY")


def get_db_connection():
    """Establishes a connection to the mysql database."""
    try:
        print("Connecting to database...")
        conn = mysql.connector.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            database=os.getenv("database"),
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None


def llm_generate_description(
    table_name: str, column_name: str, data_type: str, sample_data: List[str]
) -> str:
    """
    Uses the Gemini LLM to generate a concise, human-readable description
    for a database column based on its data type and sampled values.
    """
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:  # pragma: no cover - environment dependent
        return f"LLM Initialization Error: {e}"

    system_prompt = (
        "You are a database metadata expert. Your task is to generate a single, "
        "concise (1-2 sentence) human-readable description for a database column. "
        "Use the provided table name, column name, data type, and sampled values as context."
    )

    user_prompt = (
        "Generate a 1-2 sentence description for the following column:\n\n"
        f"- Table: {table_name}\n"
        f"- Column: {column_name}\n"
        f"- Data Type: {data_type}\n"
        f"- Sampled Data Values: [{', '.join(sample_data)}]\n\n"
        "Example output format: \"This column tracks the unique ID for each customer\n"
        "and serves as the primary key for the table.\""
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_prompt)],
                ),
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt, temperature=0.1
            ),
        )
        return response.text.strip()

    except Exception as e:  # pragma: no cover - runtime/LLM dependent
        print(f"LLM Description Generation Failed for {table_name}.{column_name}: {e}")
        return "<<ERROR: LLM failed to generate description.>>"


def extract_schema_metadata(schema_name: str = "neuleap") -> str:
    """
    Extracts table and column metadata, using LLM for description generation
    and listing distinct values for low-cardinality columns.
    """
    conn = get_db_connection()
    if not conn:
        return "ERROR: Could not connect to database for schema extraction"

    cursor = conn.cursor(dictionary=True)
    schema_dict: Dict[str, Any] = {}

    low_cardinality_threshold = 20
    sample_rows_for_llm = 20

    try:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE';",
            (schema_name,),
        )
        tables = [row["TABLE_NAME"] for row in cursor.fetchall()]

        for table in tables:
            table_data: Dict[str, Any] = {
                "_description": (
                    f"<<A 1-2 line summary of what the {table} table contains.>>"
                )
            }
            columns_data: Dict[str, Dict[str, str]] = {}

            cursor.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s;",
                (schema_name, table),
            )
            columns = cursor.fetchall()

            for col in columns:
                col_name = col["COLUMN_NAME"]
                data_type = col["DATA_TYPE"]
                known_values_list: List[str] = []

                # Sample values for LLM
                sample_values: List[str] = []
                try:
                    cursor.execute(
                        f"SELECT `{col_name}` FROM `{schema_name}`.`{table}` "
                        f"ORDER BY RAND() LIMIT {sample_rows_for_llm};"
                    )
                    sample_values = [
                        str(r[col_name]) if r[col_name] is not None else "NULL"
                        for r in cursor.fetchall()
                    ]
                except mysql.connector.Error as e_sample:
                    print(f"Warning: Failed to sample data for {table}.{col_name}: {e_sample}")

                if sample_values:
                    llm_description = llm_generate_description(
                        table, col_name, data_type, sample_values
                    )
                else:
                    llm_description = f"The {col_name} column is of type {data_type}."

                # Check low-cardinality
                try:
                    cursor.execute(
                        f"SELECT COUNT(DISTINCT `{col_name}`) AS unique_count "
                        f"FROM `{schema_name}`.`{table}`;"
                    )
                    unique_count = cursor.fetchone()["unique_count"]

                    if unique_count and 0 < unique_count <= low_cardinality_threshold:
                        cursor.execute(
                            f"SELECT DISTINCT `{col_name}` FROM `{schema_name}`.`{table}` "
                            f"ORDER BY 1 LIMIT {low_cardinality_threshold};"
                        )
                        known_values_list = [str(r[col_name]) for r in cursor.fetchall()]
                except mysql.connector.Error as e_card:
                    print(f"Warning: Failed to check cardinality for {table}.{col_name}: {e_card}")

                details_string = f"Data Type: {data_type}"
                if known_values_list:
                    details_string += (
                        f" | Known Values (<= {low_cardinality_threshold} unique): "
                        f"{', '.join(known_values_list)}"
                    )

                columns_data[col_name] = {
                    "_description": llm_description,
                    "details": details_string,
                }

            table_data["columns"] = columns_data
            schema_dict[table] = table_data

    except mysql.connector.Error as e:
        return f"ERROR: Failed to query schema information: {e}"
    finally:
        cursor.close()
        conn.close()

    with open("output___.json", "w", encoding="utf-8") as f:
        json.dump(schema_dict, f, indent=2, sort_keys=False)

    return json.dumps(schema_dict, indent=2, sort_keys=False)


def execute_sql_query(sql_query: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes a read-only SQL query on MySQL and returns the results.

    Returns a tuple of (results list, error string).
    """
    conn = get_db_connection()
    if not conn:
        return [], "ERROR: Could not connect to database for query execution."

    cursor = conn.cursor()
    results: List[Dict[str, Any]] = []
    error = ""

    normalized_query = sql_query.strip().upper()
    if not (normalized_query.startswith("SELECT") or normalized_query.startswith("WITH")):
        conn.close()
        return [], "SECURITY ERROR: Only read-only SELECT or WITH statements are allowed."

    try:
        cursor.execute(sql_query)
        column_names = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        for row in rows:
            results.append(dict(zip(column_names, row)))

    except mysql.connector.Error as e:
        error = f"SQL EXECUTION ERROR: {e}"
    except Exception as e:  # pragma: no cover - unexpected runtime
        error = f"An unexpected error occurred: {e}"
    finally:
        cursor.close()
        conn.close()

    return results, error


def test_connection():
    try:
        conn = get_db_connection()
        print("Connection established successfully!")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")


if __name__ == "__main__":
    # Simple test to extract metadata
    extract_schema_metadata("neuleap")