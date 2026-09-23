"""Small helper to ask Gemini whether a visualization is appropriate and
produce Streamlit code when helpful.

This module constructs a focused system prompt and asks Gemini to return a
Streamlit code snippet that uses a DataFrame named `df_results`. If the LLM
returns no appropriate code, the helper returns an empty string.
"""

import os
from dotenv import load_dotenv

import pandas as pd
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")


def decide_and_generate_visualization(
    user_query: str, chatbot_summary: str, data_df: pd.DataFrame
) -> str:
    """Return Streamlit code to visualize `data_df`, or empty string.

    The function asks Gemini to choose the best chart (bar, line, area) or to
    return BLANK when no visualization is appropriate. The returned code must
    reference `df_results` as the DataFrame variable.
    """

    system_prompt = (
        "You are an expert Streamlit visualization code generator.\n"
        "Decide the best chart for the question and data, using `df_results` as the DataFrame variable.\n"
        "Use st.bar_chart for comparisons/rankings, st.line_chart for time-series/trends,"
        " or return BLANK for simple listings.\n"
        "Output ONLY executable Streamlit Python code; do not include explanation text."
    )

    # 3. Construct the full prompt (user-facing content)
    prompt = f"Question: {user_query}\nSummary: {chatbot_summary}\nDataFrame columns: {list(data_df.columns)}"

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
            ],
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )

        # Extract LLM text from the response structure used elsewhere in the repo
        code_text = response.candidates[0].content.parts[0].text.strip()

        # Remove markdown fences if present
        if code_text.startswith("```python"):
            code_text = code_text.replace("```python", "").replace("```", "").strip()

        # Security check: only allow known Streamlit functions
        allowed_funcs = ("st.bar_chart", "st.line_chart", "st.area_chart","st.altair_chart", "st.pyplot", "st.map")
        if not code_text or not any(func in code_text for func in allowed_funcs):
            return ""

        print("Generated Visualization Code:\n", code_text)
        return code_text
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"Error generating visualization code: {exc}")
        return ""
    
