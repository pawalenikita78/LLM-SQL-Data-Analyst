"""
ui/streamlit_app.py: Streamlit user interface for the LLM-SQL application.
To run: streamlit run ui/streamlit_app.py
"""
import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
import streamlit as st
import pandas as pd
from app.main import run_query_pipeline # Import the main function
from llm.visualization import decide_and_generate_visualization

def display_results(df: pd.DataFrame, summary: str, sql_query: str = None):
    """Displays the final results in a structured format."""
    st.markdown("---")
    
    st.subheader("🤖 Insights & Explanation")
    st.markdown(summary)
    
    if sql_query:
        st.subheader("📝 SQL Query Used")
        st.code(sql_query, language="sql")
        
    if not df.empty:
        st.subheader("📋 Raw Data Table")
        st.dataframe(df)

def main_app():
    """Main function to run the Streamlit application."""
    
    st.set_page_config(
        page_title="LLM-SQL Data Analyst", 
        page_icon="🔍", 
        layout="wide"
    )
    
    st.title("Ask Your Data! 📊")
    st.caption("Natural Language to SQL Query Engine powered by Gemini & PostgreSQL.")

    # User Input
    user_query = st.text_input(
        "Enter your question about the database (e.g., 'What are the top 5 selling categories and their total revenue?')",
        key="user_query_input"
    )

    if st.button("Generate Insights", type="primary") and user_query:
        # State management for loading/caching
        with st.spinner("Processing... Generating SQL, executing query, and structuring results..."):
            
            # Execute the full pipeline
            df_results, final_summary, error_message, sql_query = run_query_pipeline(user_query)
            

        st.markdown("---")
        
        if error_message:
            st.error(f"❌ Pipeline Failed: {error_message}")
        elif final_summary and "cannot answer" in final_summary: # Handle "QUERY_NOT_POSSIBLE" case
            st.warning(final_summary)
        else:
            # Success state
            if df_results is not None and not df_results.empty:
                    display_results(df_results, final_summary, sql_query)

                    # Attempt to generate and render a visualization using the LLM helper
                    try:
                        print("Generating visualization code via Gemini... in streamlit_app.py")
                        viz_code = decide_and_generate_visualization(user_query, final_summary or "", df_results)
                    except Exception as e:
                        viz_code = ""
                        st.warning(f"Visualization generation failed: {e}")

                    # If LLM returned a non-empty code snippet, execute it in a controlled globals dict
                    if viz_code:
                        st.markdown("---")
                        st.subheader("📈 Suggested Visualization")

                        # Clean code fences if present
                        viz_code = viz_code.strip()
                        if viz_code.startswith("```"):
                            # remove backticks and optional language hint
                            viz_code = viz_code.split('\n', 1)[-1]
                            if viz_code.endswith("```"):
                                viz_code = viz_code[:-3].strip()

                        # Prepare a minimal globals mapping so executed code can access streamlit and the dataframe
                        safe_globals = {"st": st, "pd": pd, "df_results": df_results}

                        try:
                            exec(viz_code, safe_globals)
                        except Exception as e:
                            st.error(f"Failed to render visualization code: {e}")
            elif final_summary:
                # Handle queries that return an empty set but a valid summary
                st.info("Query executed successfully, but returned no data.")
                st.subheader("🤖 Explanation")
                st.markdown(final_summary)
            else:
                st.error("An unknown error occurred during processing.")

if __name__ == "__main__":
    main_app()