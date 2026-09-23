"""Main orchestration for the LLM-SQL pipeline.

This module provides `run_query_pipeline` which loads schema metadata,
generates SQL via the LLM chain, executes it, and restructures results.
"""
import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',))
sys.path.append(parent_dir)

print("directory in main",parent_dir)
from typing import Optional, Tuple


import pandas as pd

from llm import generate_sql_query, restructure_results, get_memory
from .database_utils import execute_sql_query


def run_query_pipeline(
    user_question: str,
) -> Tuple[Optional[pd.DataFrame], Optional[str], Optional[str], Optional[str]]:
    """Run the pipeline and return (df, summary, error, sql).

    Returns:
        (DataFrame|None, summary|None, error_message|None, sql_query|None)
    """
    error_message: Optional[str] = None
    final_df: Optional[pd.DataFrame] = None
    summary: Optional[str] = None
    schema_context: Optional[str] = None
    
    script_dir = os.path.dirname(__file__)
    output_json_path = os.path.join(script_dir, "..", "output.json")

    if os.path.exists(output_json_path):
        print("HIII")
        with open("output.json", "r", encoding="utf-8") as fh:
            schema_context = fh.read()
    else:
        return None, None, "Metadata file output.json not found.", None

    # memory = get_memory()
    # mem_entry = memory.find_similar(user_question, path="conversation_memory.json")
    # if mem_entry:
    #     try:
    #         final_df = pd.DataFrame(mem_entry.get("results", []))
    #     except (ValueError, TypeError):
    #         final_df = None
    #     return final_df, mem_entry.get("summary"), None, mem_entry.get("sql_query")

    sql_query = generate_sql_query(schema_context, user_question)
    if isinstance(sql_query, str) and "ERROR" in sql_query:
        return None, None, f"SQL Generation Failed: {sql_query}", None
    if sql_query == "QUERY_NOT_POSSIBLE":
        return None, "I cannot answer this question based on the available database schema. Please rephrase your question.", None, None

    print("I am in run Query pipeline")
    raw_results, exec_err = execute_sql_query(sql_query)
    if exec_err:
        return None, None, f"SQL Execution Failed: {exec_err}", None

    final_df = pd.DataFrame(raw_results)
    sql_results = final_df.head(20) if not final_df.empty else "No results returned."
    summary = restructure_results(user_question, sql_results)

    # try:
    #     mem_results = final_df.reset_index().to_dict(orient="records") if final_df is not None else []
    #     memory.store(user_question, sql_query, mem_results, summary)
    # except Exception:
    #     # Non-fatal
    #     pass

    
    return final_df, summary, None, sql_query


if __name__ == "__main__":
    example_question = "What are the top 5 selling product categories and their total sales amount?"
    df_results, final_summary, error_msg, sql_query = run_query_pipeline(example_question)
    print("\n" + "=" * 50)
    if error_msg:
        print(f"PIPELINE FAILED: {error_msg}")
    else:
        print(f"User Question: {example_question}")
        print("\n--- FINAL SUMMARY ---")
        print(final_summary)
        print("\n--- RAW DATA PREVIEW ---")
        if df_results is not None:
            print(df_results.head())
        else:
            print("No data frame to display.")
    print("=" * 50)
