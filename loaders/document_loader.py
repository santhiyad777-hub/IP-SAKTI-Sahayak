"""
============================================================
Project : RAG Chatbot
File    : document_loader.py

Purpose:
Load supported office, text, and structured data files
    and convert them into LangChain Documents.

Author:
    Sandy
============================================================
"""

# -----------------------------
# Import Required Libraries
# -----------------------------

import os
import json
import xml.etree.ElementTree as ET

from docx import Document as WordDocument
from langchain_core.documents import Document




# ---------------------------------------------------
# Function : load_document()
#
# Purpose:
# Automatically detect the document type
# and load it.
# ---------------------------------------------------

def load_document(file_path):

    # Get file extension
    extension = os.path.splitext(file_path)[1].lower()

    # ---------------- PDF ----------------

    if extension == ".pdf":
        from pypdf import PdfReader
        reader=PdfReader(file_path)
        if len(reader.pages)>2000:raise ValueError("PDF page limit exceeded")
        return [_document(page.extract_text() or "",file_path,page=index) for index,page in enumerate(reader.pages)]

    # ---------------- TXT ----------------

    elif extension == ".txt":
        with open(file_path,encoding="utf-8") as stream:
            return [_document(stream.read(),file_path)]

    # ---------------- CSV ----------------

    elif extension == ".csv":
        import csv
        with open(file_path,encoding="utf-8",newline="") as stream:
            return [_document("\n".join(f"{key}: {value}" for key,value in row.items()),file_path,row=index)
                    for index,row in enumerate(csv.DictReader(stream))]

    # ---------------- DOCX ----------------

    elif extension == ".docx":
        return _load_docx(file_path)

    # ---------------- PowerPoint ----------------

    elif extension == ".pptx":
        return _load_pptx(file_path)

    # ---------------- Excel ----------------

    elif extension in {".xlsx", ".xls"}:
        return _load_excel(file_path)

    # ---------------- Markdown / HTML ----------------

    elif extension in {".md", ".html", ".htm"}:
        return _load_text_or_html(file_path, extension)

    # ---------------- JSON / XML ----------------

    elif extension in {".json", ".xml"}:
        return _load_structured_data(file_path, extension)

    # ---------------- Unsupported ----------------

    else:

        raise ValueError(
            f"Unsupported file type : {extension}"
        )

    # Return LangChain Documents

    raise ValueError("Unsupported document type")


def _document(content, file_path, **metadata):
    """Create a document while retaining location metadata for citations."""
    return Document(page_content=content, metadata={"source": file_path, **metadata})


def _load_docx(file_path):
    document = WordDocument(file_path)
    blocks = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style else ""
        prefix = "# " if style.startswith("Heading") else ""
        blocks.append(f"{prefix}{text}")

    for table_number, table in enumerate(document.tables, start=1):
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        if rows:
            blocks.append(f"Table {table_number}:\n" + "\n".join(rows))

    return [_document("\n\n".join(blocks), file_path)] if blocks else []


def _load_pptx(file_path):
    try:
        from pptx import Presentation
    except ImportError as error:
        raise ValueError("PowerPoint support requires python-pptx. Run: python -m pip install python-pptx") from error
    presentation = Presentation(file_path)
    documents = []
    for slide_number, slide in enumerate(presentation.slides, start=1):
        text = []
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text.strip():
                text.append(shape.text.strip())
            if getattr(shape, "has_table", False):
                text.extend(" | ".join(cell.text.strip() for cell in row.cells) for row in shape.table.rows)
        if text:
            documents.append(_document("\n".join(text), file_path, slide=slide_number))
    return documents


def _load_excel(file_path):
    try:
        import pandas as pd
    except ImportError as error:
        raise ValueError("Excel support requires pandas and openpyxl. Run: python -m pip install pandas openpyxl xlrd") from error
    sheets = pd.read_excel(file_path, sheet_name=None)
    documents = []
    for sheet_name, dataframe in sheets.items():
        dataframe = dataframe.fillna("")
        content = dataframe.to_csv(index=False)
        if content.strip():
            documents.append(_document(content, file_path, sheet=str(sheet_name)))
    return documents


def _load_text_or_html(file_path, extension):
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        content = file.read()
    if extension in {".html", ".htm"}:
        try:
            from bs4 import BeautifulSoup
        except ImportError as error:
            raise ValueError("HTML support requires beautifulsoup4. Run: python -m pip install beautifulsoup4") from error
        soup = BeautifulSoup(content, "html.parser")
        content = soup.get_text("\n", strip=True)
    return [_document(content, file_path)] if content.strip() else []


def _load_structured_data(file_path, extension):
    with open(file_path, "r", encoding="utf-8", errors="replace") as file:
        raw_content = file.read()
    if extension == ".json":
        content = json.dumps(json.loads(raw_content), indent=2, ensure_ascii=False)
    else:
        root = ET.fromstring(raw_content)
        content = "\n".join(f"{element.tag}: {(element.text or '').strip()}" for element in root.iter())
    return [_document(content, file_path)] if content.strip() else []
