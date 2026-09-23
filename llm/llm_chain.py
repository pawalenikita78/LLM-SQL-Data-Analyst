"""llm/llm_chain.py: Handles interactions with the Gemini LLM.

This module wraps the Google Gemini ``genai`` client and provides two helpers:
- ``generate_sql_query``: produce SQL from a user question and schema context
- ``restructure_results``: summarize SQL results for the user
"""
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize Gemini client (use a clear module-level name for linting)
try:
    # Use gemini-2.5-flash for faster response times for chat/generation
    LLM_CLIENT = genai.Client(api_key=api_key)
except Exception as exc:  # pylint: disable=broad-exception-caught
    print(f"Error initializing Gemini LLM: {exc}")
    LLM_CLIENT = None  # Handle the failure gracefully

def generate_sql_query(schema_context: str, user_query: str) -> str:
    """
    Uses Gemini to translate a natural language query into a PostgreSQL SQL query.

    Args:
        schema_context: Detailed description of the database schema.
        user_query: The user's question.

    Returns:
        The generated SQL query string.
    """
    if not LLM_CLIENT:
        return "ERROR: LLM not initialized."

    try:
        user_prompt = user_query
        system_prompt = (
            "You are an expert SQL query generator.\n\n"
            "Based on this schema, generate a valid MySQL SQL query for:\n"
            f'"{user_prompt}"\n\n'
            "Return only the SQL query without explanations.\n"
            f"{schema_context}"
        )

        response = LLM_CLIENT.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]),
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5,
            ),
        )

        generated_query = response.candidates[0].content.parts[0].text

        # Simple validation based on prompt rules
        if not generated_query or "QUERY_NOT_POSSIBLE" in generated_query:
            return "QUERY_NOT_POSSIBLE"

        # Remove potential unwanted markdown formatting
        if generated_query.startswith("```sql"):
            generated_query = generated_query.replace("```sql", "").strip()
        if generated_query.endswith("```"):
            generated_query = generated_query.replace("```", "").strip()

        return generated_query.strip()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error during SQL generation: {exc}")
        return "ERROR: Failed to generate SQL query."
    



def restructure_results(user_question: str, sql_results_csv: str) -> str:
    """
    Uses Gemini to transform raw SQL results into a user-friendly summary.

    Args:
        user_question: The original user question.
        sql_results_csv: The raw SQL results formatted as a CSV string.

    Returns:
        A human-readable summary of the results.
    """
    if not LLM_CLIENT:
        return "ERROR: LLM not initialized."

    try:
        user_prompt = user_question
        system_prompt = f"""
        You are a data analyst.
        Below is a sample of the query result:
        {sql_results_csv}

        Write a 2–3 sentence summary describing:
                - What this data represents
                - Only related to dataframe
                - Key insights

        """
        print("system_prompt for restructuring:", system_prompt)

        # Invoke the LLM
        response = LLM_CLIENT.models.generate_content(
            model='gemini-2.5-flash',  # Fast and capable model for text generation
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]),
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.5,  # Keep temperature low for factual, non-creative responses
            ),
        )
        return response.candidates[0].content.parts[0].text
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error during result restructuring: {exc}")
        return "ERROR: Failed to restructure results."
    

