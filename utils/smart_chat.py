"""Query understanding and response-only transformation helpers.

These helpers deliberately sit around (not inside) the existing RAG pipeline.
"""

import re

from config import LLM_MODEL
from rag.chatbot import get_llm_client


from utils.language import response_language, is_response_transformation


def normalise_query_for_retrieval(query):
    """Lightweight Tanglish normalization used only as the retrieval query."""
    replacements = {
        " na enna": " what is", " epdi work agum": " how does it work",
        " explain pannu": " explain", " explain pannunga": " explain",
        " use panrathu why": " why is it used", " kudu": " give an example",
    }
    normalized = query
    for source, target in replacements.items():
        normalized = re.sub(re.escape(source), target, normalized, flags=re.IGNORECASE)
    return normalized


def transform_response(instruction, previous_answer, language):
    """Use the LLM only on the previous answer; no documents or retriever are used."""
    prompt = f"""Transform the response below according to the user's instruction.
Do not answer a new question, do not claim to consult documents, and preserve factual meaning.
Reply in {language}. Preserve Markdown where helpful.

User instruction: {instruction}

Previous response:
{previous_answer}
"""
    client = get_llm_client()
    response = client.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]
