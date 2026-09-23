"""
llm/memory.py

Simple conversation memory for caching previous question -> (sql_query, results, summary).
This is an intentionally lightweight, dependency-free implementation.

Behavior:
- Stores a list of recent interactions to a JSON file (default: conversation_memory.json).
- Uses a token-set Jaccard similarity to detect similar/follow-up questions.
- Can persist and reload across runs.

This is safe and easy to extend later to use embeddings or a vector DB.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()  # Load environment variables from .env file
api_key = os.getenv("GEMINI_API_KEY")


# Initialize Gemini client (use a clear module-level name for linting)
try:
    # Use gemini-2.5-flash for faster response times for chat/generation
    LLM_CLIENT = genai.Client(api_key=api_key)
except Exception as exc:  # pylint: disable=broad-exception-caught
    print(f"Error initializing Gemini LLM: {exc}")
    LLM_CLIENT = None  # Handle the failure gracefully

def _normalize_text(text: str) -> List[str]:
    text = text.lower()
    # remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = [t for t in text.split() if len(t) > 1]
    # small stopword filter (keeps footprint tiny and dependency-free)
    stopwords = set(
        [
            "the",
            "is",
            "in",
            "at",
            "which",
            "on",
            "and",
            "a",
            "an",
            "of",
            "for",
            "to",
            "by",
            "with",
            "that",
            "this",
            "these",
            "those",
            "are",
            "be",
        ]
    )
    return [t for t in tokens if t not in stopwords]


def _jaccard_similarity(a: List[str], b: List[str]) -> float:
    set_a = set(a)
    set_b = set(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    inter = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(inter) / len(union)


class ConversationMemory:
    """Lightweight conversation memory stored as a JSON file.

    The memory keeps recent interactions (question, sql_query, results, summary)
    and exposes `find_similar` and `store` helpers.
    """

    def __init__(self, path: str = "conversation_memory.json", max_entries: int = 200):
        self.path = path
        self.max_entries = max_entries
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._entries = json.load(f)
            except Exception:  # pylint: disable=broad-exception-caught
                # If loading fails, start fresh to avoid crashing the pipeline
                self._entries = []

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception:
            # Non-fatal: don't raise errors from the memory layer
            # Keep the exception quiet in production but log in development if needed
            pass  # pylint: disable=broad-exception-caught

    def find_similar(self, user_query: str, path: str) -> Optional[Dict[str, Any]]:
        """Search the stored conversation for a similar prior question.

        Returns a dict with at least a 'summary' key when a cached answer is found,
        otherwise returns None.
        """
        if not LLM_CLIENT:
            return None

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                context = f.read()
        else:
            return None

        user_prompt = user_query
        system_prompt = (
                        """
            You are an intelligent memory retrieval assistant. The user has asked the following question:
            "{user_prompt}"

            You are provided with the conversation history below. Use this context to answer the question only if the answer can be found within it.
            If the user's query cannot be answered based on the given context, respond with 'None' instead of generating a new answer.

            Context:
            {context}
            """).format(user_prompt=user_prompt, context=context)

        try:
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

            res = response.candidates[0].content.parts[0].text
            if res.strip().lower() == "none":
                return None
            # Return a minimal dict so callers can rehydrate results if present
            return {"summary": res}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error during memory retrieval: {exc}")
            return None

    def store(self, question: str, sql_query: Optional[str], results: Optional[List[Dict[str, Any]]], summary: Optional[str]) -> None:
        """Store an interaction in memory.

        Parameters:
            question: original user question
            sql_query: generated SQL (may be None)
            results: list of serializable result dicts
            summary: human-readable summary
        """
        entry = {
            "question": question,
            "question_tokens": _normalize_text(question),
            "sql_query": sql_query,
            "summary": summary,
            # results should be a list of serializable dicts (e.g., df.to_dict(orient='records'))
            "results": results or [],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self._entries.append(entry)
        # keep size bounded
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        self._save()


# Provide a small module-level helper for convenience
def get_memory(path: str = "conversation_memory.json", max_entries: int = 200) -> ConversationMemory:
    """Return a singleton ConversationMemory instance.

    The instance is cached on the function object to avoid module-level globals
    and to keep usage simple in scripts.
    """
    if not getattr(get_memory, "_instance", None):
        get_memory._instance = ConversationMemory(path=path, max_entries=max_entries)
    return get_memory._instance
