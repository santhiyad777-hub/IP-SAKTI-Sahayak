"""
============================================================
Project : RAG Chatbot
File    : document_tracker.py

Purpose:
    Keep track of indexed documents.
    Prevent duplicate indexing.

Author:
    Sandy
============================================================
"""

import json
import os

from config import BASE_DIR
TRACKER_FILE = str(BASE_DIR / "knowledge_base/documents.json")


def load_tracker():

    if not os.path.exists(TRACKER_FILE):
        return []

    with open(TRACKER_FILE, "r") as file:

        return json.load(file)


def save_tracker(data):

    with open(TRACKER_FILE, "w") as file:

        json.dump(data, file, indent=4)


def document_exists(file_hash):

    documents = load_tracker()

    for document in documents:

        if document["hash"] == file_hash:
            return True

    return False


def add_document(file_name, file_hash):

    documents = load_tracker()

    if document_exists(file_hash):
        return

    documents.append({

        "file_name": file_name,

        "hash": file_hash

    })

    save_tracker(documents)


def remove_document(file_name):

    """Remove all tracker records for a deleted upload."""

    documents = load_tracker()

    save_tracker([
        document
        for document in documents
        if document.get("file_name") != file_name
    ])
