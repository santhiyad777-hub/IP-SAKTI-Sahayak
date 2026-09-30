"""
============================================================
Project : RAG Chatbot
File    : splitter.py

Purpose:
    Split large documents into smaller chunks
    for efficient retrieval.

Author:
    Sandy
============================================================
"""

# ---------------------------------------------------
# Import Required Library
# ---------------------------------------------------

from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------
# Import Configuration
# ---------------------------------------------------

from config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

# ---------------------------------------------------
# Function : split_documents()
#
# Purpose:
# Convert large documents into smaller chunks.
# ---------------------------------------------------

def split_documents(documents):

    # Create Text Splitter

    text_splitter = RecursiveCharacterTextSplitter(

        chunk_size=CHUNK_SIZE,

        chunk_overlap=CHUNK_OVERLAP,

        length_function=len,

        is_separator_regex=False

    )

    # Split Documents

    chunks = text_splitter.split_documents(documents)

    return chunks
