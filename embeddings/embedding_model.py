"""
============================================================
Project : RAG Chatbot
File    : embedding_model.py

Purpose:
    Create the embedding model used to convert
    document chunks into vector representations.

Author:
    Sandy
============================================================
"""

# ---------------------------------------------------
# Import Required Library
# ---------------------------------------------------

from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings

# ---------------------------------------------------
# Import Configuration
# ---------------------------------------------------

from config import EMBEDDING_MODEL

# ---------------------------------------------------
# Function : get_embedding_model()
#
# Purpose:
# Create and return the embedding model.
# ---------------------------------------------------

@lru_cache(maxsize=1)
def get_embedding_model():

    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    try:
        model_path = snapshot_download(EMBEDDING_MODEL, local_files_only=True)
    except LocalEntryNotFoundError:
        model_path = EMBEDDING_MODEL
    embedding_model = HuggingFaceEmbeddings(

        model_name=model_path,

        model_kwargs={
            "device": "cpu",
            "trust_remote_code": False
        },

        encode_kwargs={
            "normalize_embeddings": True
        }

    )

    return embedding_model
