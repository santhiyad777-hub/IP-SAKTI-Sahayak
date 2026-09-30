"""IP-SAKTI Sahayak — a persistent, document-grounded RAG chat workspace.

This module owns authenticated presentation, private uploads and durable
account-scoped conversation history.
"""

import json
import os
import re
import subprocess
import tempfile
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from html import escape

import streamlit as st

from config import UPLOAD_FOLDER, BASE_DIR
from ingestion.pipeline import ingest_upload
from utils.bhashini import configured as bhashini_configured, BhashiniError
from rag.chatbot import DISCLAIMER, citation
from rag.conversation import respond
from utils.language import LANGUAGES, messages
from utils.ui_language import tr, NAMES, CATALOG, display_message
from utils.message_versions import migrate_conversation, migrate_message, select_message_language
from loaders.document_loader import load_document
from rag.chatbot import ask_llm
from rag.retriever import retrieve_documents
from utils.file_hash import calculate_file_hash
from utils.splitter import split_documents
from ui.workflow import workflow_panel, passport_panel
from security.ui import require_login, account_controls
from security.auth import ConflictError
from security.downloads import private_download
from security.content import message_markdown
from security.uploads import save_upload, delete_upload
from utils.workspace_tools import record_event
from vectordb.chroma_manager import create_or_update_vector_database, delete_document_from_vector_database


st.set_page_config(page_title="IP-SAKTI Sahayak", page_icon=":herb:", layout="wide", initial_sidebar_state="expanded")
workspace = require_login(BASE_DIR)
UPLOAD_FOLDER = str(workspace.uploads)

def save_language():
    workspace.save_preferences({"language": st.session_state.app_language})

if "app_language" not in st.session_state:
    try:
        saved_language = workspace.read_preferences().get("language")
    except (OSError, ValueError):
        saved_language = st.session_state.get("answer_language", "English")
    st.session_state.app_language = saved_language if saved_language in ["Auto"] + LANGUAGES else "English"
answer_language = st.session_state.app_language
ui_language = st.session_state.get("auto_language", "English") if answer_language == "Auto" else answer_language
def t(text, **values):
    return tr(text, ui_language, **values)
def localize_markup(markup):
    pattern = "|".join(re.escape(text) for text in sorted(CATALOG, key=len, reverse=True))
    return re.sub(pattern, lambda match: t(match.group()), markup)
st.session_state.setdefault("display_translations", {})
def rendered_message(message):
    try:
        before = len(message.get("translated_versions", {}))
        result = display_message(message, message.get("display_language") or ui_language, st.session_state.display_translations,
                               st.session_state.get("use_bhashini", bhashini_configured()))
        if len(message.get("translated_versions", {})) != before:
            st.session_state.versions_changed = True
        return result
    except Exception:
        return t("Translation is temporarily unavailable. Please retry.")



def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def display_time(value):
    try:
        return datetime.fromisoformat(value).strftime("%d-%m-%Y · %H:%M")
    except (TypeError, ValueError):
        return value or ""


def load_conversations():
    return [migrate_conversation(chat) for chat in workspace.list_chats()]


def save_conversations(conversations):
    if not conversations:return
    chat=next((c for c in conversations if c["id"]==st.session_state.get("current_chat_id")),conversations[0])
    try:workspace.save_chat(chat)
    except ConflictError:
        st.error("This conversation changed in another session. Reload before editing again.")
        st.stop()


def make_conversation():
    stamp = now_iso()
    return {"id": str(uuid.uuid4()), "title": "New conversation", "created_at": stamp,
            "updated_at": stamp, "messages": [], "document_names": [], "bookmarks": []}


def current_conversation():
    return next((chat for chat in st.session_state.conversations if chat["id"] == st.session_state.current_chat_id), None)


def persist_current():
    chat = current_conversation()
    if chat:
        chat["messages"] = st.session_state.messages
        chat["updated_at"] = now_iso()
        save_conversations(st.session_state.conversations)


def change_message_language(message_id, widget_key):
    try:
        select_message_language(current_conversation(), message_id, st.session_state[widget_key],
                                st.session_state.get("use_bhashini", bhashini_configured()))
        st.session_state.pop("message_translation_error", None)
        persist_current()
    except Exception:
        st.session_state.message_translation_error = t("Translation is temporarily unavailable. Please retry.")

def open_chat(chat_id):
    chat = next(chat for chat in st.session_state.conversations if chat["id"] == chat_id)
    st.session_state.current_chat_id = chat_id
    st.session_state.smart_cache = {}
    st.session_state.messages = chat.get("messages", [])
    st.session_state.last_sources = []


def new_chat():
    chat = make_conversation()
    st.session_state.conversations.insert(0, chat)
    st.session_state.current_chat_id = chat["id"]
    st.session_state.messages = []
    st.session_state.last_sources = []
    st.session_state.smart_cache = {}
    save_conversations(st.session_state.conversations)


def index_file(file_path):
    count = ingest_upload(file_path, workspace=workspace)
    return t("Indexed {count} chunks", count=count)


def conversation_text(chat, extension="txt"):
    lines = [f"# {chat['title']}" if extension == "md" else chat["title"], ""]
    for message in chat.get("messages", []):
        role = t("You") if message["role"] == "user" else "IP-SAKTI"
        time = display_time(message.get("timestamp") or message.get("time"))
        lines.extend([f"## {role} · {time}" if extension == "md" else f"{role} ({time}):", rendered_message(message), ""])
    return "\n".join(lines)


def markdown_html(text):
    """Render the Markdown produced by the existing chatbot into print-safe HTML."""
    blocks, position = [], 0
    for match in re.finditer(r"```([^\n]*)\n(.*?)```", text, re.DOTALL):
        blocks.append(render_markdown_lines(text[position:match.start()]))
        language = escape(match.group(1).strip())
        blocks.append(f'<pre><code class="language-{language}">{escape(match.group(2))}</code></pre>')
        position = match.end()
    blocks.append(render_markdown_lines(text[position:]))
    return "".join(blocks)


def inline_markdown(text):
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = re.sub(r"\*(.+?)\*|_(.+?)_", lambda m: f"<em>{m.group(1) or m.group(2)}</em>", text)
    text = re.sub(r"\[([^]]+)\]\(([^ )]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>' if m.group(2).startswith(("https://", "http://")) else m.group(1), text)
    return text


def render_markdown_lines(text):
    lines, html, index = text.splitlines(), [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip(): index += 1; continue
        if index + 1 < len(lines) and "|" in line and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            headers = [inline_markdown(cell.strip()) for cell in line.strip().strip("|").split("|")]
            rows, index = [], index + 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append([inline_markdown(cell.strip()) for cell in lines[index].strip().strip("|").split("|")]); index += 1
            html.append("<table><thead><tr>" + "".join(f"<th>{cell}</th>" for cell in headers) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows) + "</tbody></table>"); continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1)); html.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>"); index += 1; continue
        unordered, ordered = re.match(r"^\s*[-*+]\s+(.+)$", line), re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            tag, items = ("ul", []) if unordered else ("ol", [])
            pattern = r"^\s*[-*+]\s+(.+)$" if unordered else r"^\s*\d+[.)]\s+(.+)$"
            while index < len(lines):
                item = re.match(pattern, lines[index])
                if not item: break
                items.append(f"<li>{inline_markdown(item.group(1))}</li>"); index += 1
            html.append(f"<{tag}>" + "".join(items) + f"</{tag}>"); continue
        if line.startswith("> "):
            html.append(f"<blockquote>{inline_markdown(line[2:])}</blockquote>"); index += 1; continue
        html.append(f"<p>{inline_markdown(line)}</p>"); index += 1
    return "".join(html)


def pdf_bytes(chat):
    """Create a paginated, Unicode-safe PDF with Chrome's production print engine."""
    title, exported = escape(chat.get("title", "Conversation")), datetime.now().strftime("%d %B %Y, %I:%M %p")
    documents = escape(", ".join(chat.get("document_names", [])) or t("No document selected"))
    conversation_id = escape(chat.get("id", "Unavailable"))
    messages = []
    for message in chat.get("messages", []):
        role = t("You") if message.get("role") == "user" else "IP-SAKTI Sahayak"
        stamp = escape(display_time(message.get("timestamp") or message.get("time")))
        messages.append(f'<section class="message {"user" if message.get("role") == "user" else "assistant"}"><div class="message-meta">{role} <span>{stamp}</span></div><div class="message-body">{markdown_html(rendered_message(message))}</div></section>')
    html = f'''<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><style>
    @page {{ size:A4; margin:20mm 16mm 18mm; @bottom-center {{content:"Page " counter(page) " of " counter(pages); color:#64748b; font:9px Arial,sans-serif;}} }}
    *{{box-sizing:border-box}} body{{font:10.5pt "Segoe UI","Nirmala UI",Arial,sans-serif;color:#172033;line-height:1.58}} h1{{font-size:22pt;margin:0 0 5px}} h2{{font-size:16pt;margin:24px 0 9px}} h3{{font-size:13pt;margin:18px 0 7px}} p{{margin:0 0 10px}} .top{{border-bottom:1px solid #dce2ee;padding-bottom:15px;margin-bottom:20px}} .sub{{color:#667085;font-size:9.5pt;margin-top:3px}} .message{{break-inside:avoid;margin:0 0 18px;padding:14px 16px;border:1px solid #e3e8f2;border-radius:10px}} .message.user{{background:#f5f3ff;border-color:#e5e0ff}} .message-meta{{font-weight:700;color:#4f46e5;margin-bottom:10px}} .message-meta span{{float:right;font-weight:400;color:#667085;font-size:9pt}} pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#101827;color:#f1f5f9;padding:12px;border-radius:7px;font:8.7pt Consolas,"Courier New",monospace}} code{{background:#eef1f7;padding:1px 3px;border-radius:3px}} pre code{{background:none;padding:0}} table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:9pt}} th{{background:#eef1f7}} th,td{{border:1px solid #d9e0eb;padding:7px;text-align:left;vertical-align:top}} ul,ol{{margin:5px 0 10px;padding-left:23px}} blockquote{{border-left:3px solid #8b7cff;margin:10px 0;padding:4px 12px;color:#475467}} a{{color:#4f46e5}} </style></head><body><div class="top"><h1>{title}</h1><div class="sub">{t("Exported")}: {exported}</div><div class="sub">{t("Uploaded documents")}: {documents}</div><div class="sub">{t("Conversation ID")}: {conversation_id}</div></div>{''.join(messages) or '<p>No messages in this conversation.</p>'}</body></html>'''
    chrome = os.getenv("CHROME_PATH") or shutil.which("chrome") or shutil.which("chromium")
    if not chrome:
        for folder in (os.getenv("PROGRAMFILES", ""), os.getenv("PROGRAMFILES(X86)", "")):
            candidate = Path(folder) / "Google/Chrome/Application/chrome.exe"
            if candidate.is_file(): chrome = str(candidate); break
    if not chrome:
        from weasyprint import HTML
        def deny_external(url, *args, **kwargs):
            raise ValueError("External resources are not allowed in private PDF exports.")
        return HTML(string=html, url_fetcher=deny_external).write_pdf()
    with tempfile.TemporaryDirectory(prefix="nexusdocs_pdf_") as directory:
        html_path, pdf_path = os.path.join(directory, "conversation.html"), os.path.join(directory, "conversation.pdf")
        with open(html_path, "w", encoding="utf-8") as file: file.write(html)
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header", "file:///" + html_path.replace("\\", "/")], check=True, capture_output=True, timeout=60)
        with open(pdf_path, "rb") as file: return file.read()


for key, value in {"theme": "light", "uploader_key": 0, "last_sources": [], "feedback": {}, "delete_target": None, "smart_cache": {}}.items():
    st.session_state.setdefault(key, value)
if "conversations" not in st.session_state:
    st.session_state.conversations = load_conversations()
if not st.session_state.conversations:
    new_chat()
if "current_chat_id" not in st.session_state or not current_conversation():
    st.session_state.current_chat_id = st.session_state.conversations[0]["id"]
if "messages" not in st.session_state:
    st.session_state.messages = current_conversation().get("messages", [])


def apply_theme():
    dark = st.session_state.theme == "dark"
    bg, card, text, muted = ("#101b18", "#17251f", "#e6efe9", "#a2b8aa") if dark else ("#f6f8f5", "#ffffff", "#20382e", "#64776d")
    dark_control_css = """\
    [data-testid="stPopover"] button,
    [data-testid="stExpander"] details > summary,
    [data-testid="stFileUploaderDropzone"] button {
        background-color:var(--card)!important;
        color:var(--text)!important;
        border-color:var(--line)!important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] [data-baseweb="textarea"],
    [data-testid="stChatInput"] textarea {
        background-color:var(--card)!important;
        color:var(--text)!important;
        border-color:var(--line)!important;
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stMultiSelect"] [data-baseweb="select"] *,
    [data-testid="stFileUploaderDropzone"] * { color:var(--text); }
    [data-testid="stSelectbox"] [role="listbox"],
    [data-testid="stMultiSelect"] [role="listbox"],
    [data-baseweb="popover"] [role="listbox"] { background-color:var(--card); color:var(--text); }
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stChatInput"] textarea::placeholder { color:var(--muted)!important; opacity:1; }
    """ if dark else ""
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root {{ --bg:{bg}; --card:{card}; --text:{text}; --muted:{muted}; --line:rgba(137,151,194,.18); --accent:#8170ff; }}
    .stApp {{ background:radial-gradient(circle at 84% -8%,rgba(116,91,255,.13),transparent 32%),var(--bg); color:var(--text); font-family:Inter,sans-serif; }}
    #MainMenu, footer {{visibility:hidden}} header[data-testid="stHeader"] {{visibility:visible;background:transparent}} .block-container {{max-width:1500px;padding:1.15rem 2.5rem 6rem}} [data-testid=stSidebar]{{background:var(--card);border-right:1px solid var(--line)}} [data-testid=stSidebar]>div:first-child{{padding:1.35rem .9rem 2rem}} [data-testid=stSidebar] *{{color:var(--text)}}
    .brand{{display:flex;gap:11px;align-items:center;margin:2px 0 14px;padding:8px 0}} .mark{{display:grid;place-items:center;width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#8271ff,#44c7d9);color:#fff;font-weight:800;box-shadow:0 7px 20px rgba(110,91,245,.25)}} .brand h1{{font-size:17px;margin:0;letter-spacing:-.35px}} .brand p,.muted{{color:var(--muted);font-size:12px;margin:3px 0}} .cap{{color:var(--muted);font-size:10px;font-weight:800;letter-spacing:1.15px;margin:25px 3px 9px}}
    .upload-card{{padding:13px 13px 3px;border:1px solid var(--line);border-radius:14px;background:rgba(129,112,255,.055)}} .upload-card p{{font-size:12px;color:var(--muted);margin:4px 0 11px}} [data-testid=stFileUploader]{{padding:5px;border:1px dashed rgba(130,113,255,.55);border-radius:11px;background:transparent}}
    .stButton>button{{border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--text);font-weight:600;transition:transform .16s,border-color .16s,box-shadow .16s}} .stButton>button:hover{{border-color:var(--accent);color:var(--text);transform:translateY(-1px);box-shadow:0 7px 16px rgba(28,24,80,.14)}} .new .stButton>button{{background:linear-gradient(135deg,#7865ff,#9858e7);border:0;color:#fff;width:100%;height:2.65rem}}
    /* Keep the existing conversation delete control visible beside long titles. */ [data-testid="stSidebar"] [class*="st-key-del_"]{{display:block!important;min-width:2.1rem!important;flex:0 0 2.1rem!important;overflow:visible!important;position:relative!important;z-index:2!important;margin-left:.3rem!important}} [data-testid="stSidebar"] [class*="st-key-del_"] button{{display:flex!important;visibility:visible!important;opacity:1!important;pointer-events:auto!important;min-width:2.1rem!important;width:2.1rem!important;padding:.35rem!important;align-items:center!important;justify-content:center!important;white-space:nowrap!important}}
    [data-testid=stChatMessage]{{padding:17px 8px;scroll-margin-top:1rem;animation:message-in .25s ease both}} [data-testid=stChatMessage] [data-testid=stMarkdownContainer]{{color:var(--text);line-height:1.78;font-size:15px}} [data-testid=stChatMessage]:has([data-testid=chatAvatarIcon-user]){{margin:4px 0 4px 14%;padding:15px 18px;background:rgba(122,102,255,.085);border:1px solid rgba(130,112,255,.13);border-radius:18px}} .meta{{font-size:11px;color:var(--muted);margin-bottom:7px}} .assistant{{color:#9d90ff;font-weight:800}}
    [data-testid=stChatInput]{{max-width:880px;margin:auto auto 1rem;border:1px solid var(--line);border-radius:19px;background:var(--card);box-shadow:0 14px 38px rgba(11,16,32,.22)}} [data-testid=stChatInput] textarea,.stTextInput input{{color:var(--text)!important;background:var(--card)!important}} pre{{border-radius:12px!important;border:1px solid var(--line)}}
    .outline{{position:sticky;top:1.1rem;background:linear-gradient(145deg,rgba(27,38,66,.93),rgba(18,27,48,.82));border:1px solid var(--line);border-radius:18px;padding:17px;max-height:76vh;overflow:auto;box-shadow:0 14px 36px rgba(7,12,29,.14)}} .outline a{{display:block;text-decoration:none;color:var(--text);padding:10px;border:1px solid transparent;border-radius:10px;font-size:12px;line-height:1.4;transition:all .16s ease}} .outline a:hover{{background:rgba(129,112,255,.13);border-color:rgba(135,117,255,.2);transform:translateX(2px)}} .outline small{{color:var(--muted)}} .welcome{{text-align:center;margin:8vh auto 5vh;max-width:590px}} .welcome h2{{font-size:clamp(30px,3.4vw,40px);line-height:1.15;letter-spacing:-1.45px;margin:10px 0}} [data-testid="stDownloadButton"] button{{width:100%;min-height:2.35rem;margin:2px 0;border-radius:10px;transition:transform .16s,box-shadow .16s}} [data-testid="stDownloadButton"] button:hover{{transform:translateY(-1px);box-shadow:0 8px 18px rgba(28,24,80,.15)}} html{{scroll-behavior:smooth}} @keyframes message-in{{from{{opacity:0;transform:translateY(5px)}}to{{opacity:1;transform:none}}}} @media(max-width:900px){{.block-container{{padding:1rem 1rem 6rem}} .outline{{display:none}} [data-testid=stChatMessage]:has([data-testid=chatAvatarIcon-user]){{margin-left:0}}}} 
    {dark_control_css}
    </style>""", unsafe_allow_html=True)


apply_theme()
st.markdown("<style>" + (Path(__file__).parent / "ui" / "workspace.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)
# Localize Streamlit's built-in uploader text while retaining its native upload behavior.
st.markdown(f"""<style>
[data-testid="stAppDeployButton"] {{display:none}}
[data-testid="stFileUploaderDropzone"] button {{font-size:0}}
[data-testid="stFileUploaderDropzone"] button::after {{content:{json.dumps(t("Browse files"))};font-size:14px}}
[data-testid="stFileUploaderDropzoneInstructions"] span {{font-size:0}}
[data-testid="stFileUploaderDropzoneInstructions"] span::after {{content:{json.dumps(t("Drop files here or browse to add knowledge."))};font-size:14px}}
[data-testid="stFileUploaderDropzoneInstructions"] small {{font-size:0}}
[data-testid="stFileUploaderDropzoneInstructions"] small::after {{content:{json.dumps(t("Up to 25 MB per file"))};font-size:12px}}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    account_controls(workspace)
    st.markdown(localize_markup('<div class="brand"><div class="mark">IP</div><div><h1>IP-SAKTI</h1><p>Knowledge workspace</p></div></div>'), unsafe_allow_html=True)
    answer_language = st.selectbox("Language", ["Auto"] + LANGUAGES, format_func=lambda name: NAMES.get(name, name), key="app_language", on_change=save_language)
    jurisdiction = st.radio(t("Jurisdiction"), ["India", "International"], horizontal=True, format_func=t, key="jurisdiction").lower()
    available_uploads = sorted(p.name for p in Path(UPLOAD_FOLDER).iterdir() if p.is_file())
    # Source selection is automatic; keep the sidebar focused on user controls.
    source_mode = "Knowledge base + uploads" if available_uploads else "Knowledge base"
    st.session_state.source_mode = source_mode
    use_bhashini = bhashini_configured()
    selected_files = st.multiselect(t("Limit uploads to"), sorted(p.name for p in Path(UPLOAD_FOLDER).iterdir() if p.is_file())) if source_mode != "Knowledge base" else []
    st.markdown('<div class="new">', unsafe_allow_html=True)
    if st.button(t("+ New chat"), width="stretch", type="primary"):
        new_chat(); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    documents_section = st.expander(t("Uploaded Documents"), expanded=False)
    documents_section.markdown(localize_markup('<div class="upload-card"><b>Document library</b><p>Drop files here or browse to add knowledge.</p></div>'), unsafe_allow_html=True)
    uploads = documents_section.file_uploader(t("Upload documents"), type=["pdf","docx","pptx","xlsx","xls","csv","txt","md","html","json","xml"], accept_multiple_files=True, key=f"upload_{st.session_state.uploader_key}", label_visibility="collapsed")
    if uploads:
        progress = documents_section.progress(0)
        uploaded_names = []
        for index, upload in enumerate(uploads):
            safe_name = Path(upload.name.replace("\\", "/")).name
            if not safe_name or safe_name != upload.name or upload.size > 25 * 1024 * 1024:
                st.error(t("Upload a filename without directories, at most 25 MB.")); continue
            try:
                count = save_upload(workspace, safe_name, upload.getvalue())
                uploaded_names.append(safe_name)
                st.session_state.smart_cache = {}
                st.toast(f"{upload.name}: " + t("Indexed {count} chunks", count=count))
            except Exception:
                st.error(t("The document could not be processed. Check the file and retry."))
            progress.progress((index + 1) / len(uploads))
        st.session_state.uploader_key += 1
        current_conversation()["document_names"] = uploaded_names; persist_current()
    documents_on_disk = [name for name in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, name))]
    if documents_on_disk:
        documents_section.caption(t("{count} documents ready", count=len(documents_on_disk)))
        for index, name in enumerate(documents_on_disk):
            row = documents_section.columns([8, 1]); row[0].caption(f"📄 {name}")
            if row[1].button("×", key=f"file_{index}_{name}", help=t("Remove document")):
                delete_upload(workspace, name)
                st.session_state.smart_cache = {}
                st.session_state.last_sources = []
                st.rerun()
    conversations_section = st.expander(t("Recent Conversations"), expanded=True)
    query = conversations_section.text_input(t("Search conversations"), placeholder=t("Search chats…"), label_visibility="collapsed")
    chats = sorted(st.session_state.conversations, key=lambda item: item.get("updated_at", ""), reverse=True)
    for chat in chats:
        searchable = (chat.get("title", "") + " " + " ".join(m.get("content", "") for m in chat.get("messages", [])[:3])).lower()
        if query.lower() not in searchable:
            continue
        cols = conversations_section.columns([8, 1])
        title = t(chat["title"]) if chat["title"] == "New conversation" else chat["title"]
        shortened_title = title if len(title) <= 30 else title[:27] + "..."
        label = shortened_title
        if cols[0].button(label, key=f"open_{chat['id']}", help=title + " | " + display_time(chat.get("updated_at")), width="stretch"):
            open_chat(chat["id"]); st.rerun()
        if cols[1].button("×", key=f"del_{chat['id']}", help=t("Delete conversation")):
            st.session_state.delete_target = chat["id"]
    if conversations_section.button(t("Delete All Chats"), width="stretch"):
        st.session_state.delete_target = "all"
    if st.session_state.delete_target and st.session_state.delete_target != "all":
        conversations_section.warning(t("Permanently delete this conversation?"))
        yes, no = conversations_section.columns(2)
        if yes.button(t("Delete"), type="primary"):
            target = st.session_state.delete_target
            workspace.delete_chat(target)
            st.session_state.conversations = [c for c in st.session_state.conversations if c["id"] != target]
            if target == st.session_state.current_chat_id or not st.session_state.conversations:
                replacement = make_conversation()
                st.session_state.conversations.insert(0, replacement)
                st.session_state.current_chat_id = replacement["id"]
                st.session_state.messages = []
                st.session_state.last_sources = []
                st.session_state.smart_cache = {}
            save_conversations(st.session_state.conversations); st.session_state.delete_target = None
            st.rerun()
        if no.button(t("Cancel")):
            st.session_state.delete_target = None; st.rerun()
    if st.session_state.delete_target == "all":
        conversations_section.warning(t("Permanently delete all conversations? This cannot be undone."))
        all_yes, all_no = conversations_section.columns(2)
        if all_yes.button(t("Delete All"), type="primary"):
            workspace.delete_all_chats()
            st.session_state.conversations = [make_conversation()]; save_conversations(st.session_state.conversations)
            open_chat(st.session_state.conversations[0]["id"]); st.session_state.delete_target = None; st.rerun()
        if all_no.button(t("Cancel"), key="cancel_delete_all"):
            st.session_state.delete_target = None; st.rerun()
    bookmarks_section = st.expander(t("Bookmarks"), expanded=False)
    bookmark_query = bookmarks_section.text_input(t("Search bookmarks"), placeholder=t("Search bookmarks…"), label_visibility="collapsed")
    saved_bookmarks = []
    for saved_chat in st.session_state.conversations:
        for bookmark in saved_chat.get("bookmarks", []):
            # Supports bookmarks created by earlier versions, which stored an index only.
            if isinstance(bookmark, dict):
                saved_bookmarks.append((saved_chat, bookmark))
    if not saved_bookmarks:
        bookmarks_section.caption(t("No bookmarked conversations yet."))
    for saved_chat, bookmark in saved_bookmarks:
        question = bookmark.get("question", "Bookmarked question")
        if bookmark_query.lower() not in question.lower():
            continue
        item, remove = bookmarks_section.columns([8, 1])
        if item.button(f"🔖 {question[:38]}", key=f"open_bookmark_{bookmark.get('id')}", width="stretch"):
            open_chat(saved_chat["id"])
            st.session_state.bookmark_anchor = bookmark.get("message_index")
            st.rerun()
        if remove.button("×", key=f"remove_bookmark_{bookmark.get('id')}", help=t("Remove bookmark")):
            saved_chat["bookmarks"] = [entry for entry in saved_chat.get("bookmarks", []) if not isinstance(entry, dict) or entry.get("id") != bookmark.get("id")]
            workspace.save_chat(saved_chat); st.rerun()
    if st.button(t("☀ Light mode") if st.session_state.theme == "dark" else t("◐ Dark mode"), width="stretch"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"; st.rerun()
chat = current_conversation()
if st.session_state.pop("audit_write_failed", False):
    st.warning(t("The answer was saved, but the audit event could not be recorded."))
st.markdown('<span id="top"></span>', unsafe_allow_html=True)
header, export = st.columns([5, 1])
current_document = ", ".join(chat.get("document_names", [])) or t(source_mode)
header.markdown(f'<div class="brand"><div class="mark">IP</div><div><h1>{escape(t(chat["title"]) if chat["title"] == "New conversation" else chat["title"])}</h1><p>IP-SAKTI Sahayak · {escape(current_document)}</p></div></div>', unsafe_allow_html=True)
with export, st.popover(t("Workspace exports"), width="stretch"):
    private_download("TXT", conversation_text(chat), f"{chat['title']}.txt", width="stretch")
    private_download("MD", conversation_text(chat, "md"), f"{chat['title']}.md", width="stretch")
    if st.button(t("Prepare PDF")):
        try:
            private_download(t("Download PDF"), pdf_bytes(chat), f"{chat['title']}.pdf", mime="application/pdf")
        except Exception: st.error(t("PDF export failed. Check the browser configuration."))

st.markdown(f'<div class="scope-bar"><span class="scope-tag">{escape(t(jurisdiction.title()))}</span><span class="scope-tag">{escape(t(source_mode))}</span><span class="scope-tag">{escape(NAMES.get(ui_language, ui_language))}</span></div>', unsafe_allow_html=True)
workflow_panel(chat, jurisdiction, BASE_DIR, t, persist_current, private_root=workspace.root)
chat_col, outline_col = st.columns([4, 1.15], gap="large")
with chat_col:
    if not st.session_state.messages:
        st.markdown(localize_markup('<div class="welcome"><p class="assistant">YOUR AI KNOWLEDGE ASSISTANT</p><h2>Ayurveda innovation. Informed decisions.</h2><p class="muted">Ask about Ayurveda IP, product classification, ABS and regulatory requirements. Sources are cited; missing evidence is reported.</p></div>'), unsafe_allow_html=True)
        with st.container(key="starters"):
            starter_questions = ["What is TKDL?", "Can I patent a traditional Ayurvedic formulation?", "What labelling requirements apply to Ayurveda Aahara products?", "What does the official GI registry say about Navara Rice?"]
            for start in range(0, len(starter_questions), 2):
                tiles = st.columns(2)
                for offset, prompt in enumerate(starter_questions[start:start + 2]):
                    if tiles[offset].button(t(prompt), key=f"starter_{start + offset}", width="stretch"):
                        st.session_state.regenerate_question = prompt
    if st.session_state.get("message_translation_error"):
        st.error(st.session_state.message_translation_error)
    for index, message in enumerate(st.session_state.messages):
        anchor = f"q-{index}" if message["role"] == "user" else f"a-{index}"
        st.markdown(f'<span id="{anchor}"></span>', unsafe_allow_html=True)
        with st.chat_message(message["role"]):
            label = t("YOU") if message["role"] == "user" else '<span class="assistant">IP-SAKTI</span>'
            st.markdown(f'<div class="meta">{label} · {display_time(message.get("timestamp") or message.get("time"))}</div>', unsafe_allow_html=True)
            st.markdown(message_markdown(rendered_message(message)))
        if message["role"] == "assistant":
            passport_panel(message, t)
            actions = st.columns([1.3, 0.7, 1.8, 4.2])
            message_key = f"{chat['id']}_{message['message_id']}_message_language"
            current_language = message.get("display_language") or ui_language
            if message_key not in st.session_state or not message.get("display_language"):
                st.session_state[message_key] = current_language
            actions[3].selectbox(t("Message language"), LANGUAGES,
                index=None, format_func=lambda name: NAMES[name],
                key=message_key, on_change=change_message_language,
                args=(message["message_id"], message_key), help=t("Select a language for this answer only."),
                label_visibility="collapsed")
            if actions[0].button(t("Copy"), key=f"copy_{index}"):
                st.code(rendered_message(message), language=None); st.toast(t("Select the text above to copy."))
            if actions[1].button("🔖", key=f"bookmark_{index}", help=t("Bookmark this answer")):
                question_index = next((i for i in range(index - 1, -1, -1) if st.session_state.messages[i]["role"] == "user"), None)
                if question_index is not None:
                    bookmarks = chat.setdefault("bookmarks", [])
                    already_saved = any((entry.get("answer_index") == index) for entry in bookmarks if isinstance(entry, dict))
                    if not already_saved:
                        question_message = st.session_state.messages[question_index]
                        bookmarks.append({
                            "id": str(uuid.uuid4()), "message_index": question_index, "answer_index": index,
                            "question": question_message["content"], "answer": message["content"],
                            "timestamp": message.get("timestamp") or message.get("time"),
                            "conversation_id": chat["id"], "conversation_title": chat["title"],
                            "document_names": chat.get("document_names", []),
                        })
                        persist_current(); st.toast(t("Bookmark saved"))
            if actions[2].button(t("Regenerate"), key=f"regen_{index}"):
                question = next((item["content"] for item in reversed(st.session_state.messages[:index]) if item["role"] == "user"), None)
                if question: st.session_state.regenerate_question = question; st.rerun()

with outline_col, st.container(key="outline_panel"):
    st.markdown("**" + t("Conversation outline") + "**")
    outline_search = st.text_input(t("Find question"), placeholder=t("Search outline…"), label_visibility="collapsed")
    questions = [(i, item) for i, item in enumerate(st.session_state.messages) if item["role"] == "user"]
    bookmarked = {entry.get("message_index") if isinstance(entry, dict) else entry for entry in chat.get("bookmarks", [])}
    if not questions:
        st.caption(t("Your questions will appear here as the conversation grows."))
    if bookmarked: st.markdown(localize_markup('<p class="cap">Bookmarks</p>'), unsafe_allow_html=True)
    for number, (index, item) in enumerate(questions, 1):
        if outline_search.lower() not in item["content"].lower(): continue
        star = "★ " if index in bookmarked else ""
        title = escape(re.sub(r"\s+", " ", item["content"])[:62])
        st.markdown(f'<a href="#q-{index}">{star}<b>{number}. {title}</b><br><small>{display_time(item.get("timestamp") or item.get("time"))}</small></a>', unsafe_allow_html=True)
    st.markdown(localize_markup('<hr><a href="#top">↑ Jump to top</a><a href="#bottom">↓ Jump to bottom</a>'), unsafe_allow_html=True)

st.markdown('<span id="bottom"></span>', unsafe_allow_html=True)
question = st.session_state.pop("regenerate_question", None) or st.chat_input(t("Ask about Ayurveda IP, classification, ABS or export requirements..."))
if question:
    if len(question)>12000:
        st.error("Please keep the question under 12,000 characters.");st.stop()
    try:workspace.limit_request()
    except PermissionError as exc:st.error(str(exc));st.stop()
    stamp = now_iso()
    st.session_state.messages.append(migrate_message({"role": "user", "content": question, "timestamp": stamp}, chat["id"]))
    if chat["title"] == "New conversation": chat["title"] = question[:52]
    persist_current()
    try:
        with st.spinner(t("IP-SAKTI is checking the evidence...")):
            result = respond(question, st.session_state.messages[:-1], jurisdiction,
                             source_mode, selected_files, answer_language, use_bhashini,
                             st.session_state.smart_cache, workspace=workspace)
            answer, documents, language = result["answer"], result["documents"], result["language"]
    except BhashiniError as error:
        st.error(t("Translation is temporarily unavailable. Please retry."))
        st.stop()
    except Exception:
        st.error(t("The request could not be completed. Please retry shortly."))
        st.stop()
    assistant_message = {"role": "assistant", "content": answer, "timestamp": now_iso(),
        "response_kind": "clarification" if result["cache"].get("pending_question") else "answer",
        "jurisdiction": jurisdiction, "language": language, "answer_language": language,
        "original_question": result["cache"].get("last_question", question),
        "original_answer": answer,
        "retrieved_context": [{"page_content": d.page_content, "metadata": d.metadata} for d in documents],
        "sources": [citation(d, i) for i, d in enumerate(documents, 1)]}
    migrate_message(assistant_message, chat["id"], question)
    st.session_state.messages.append(assistant_message)
    try:
        record_event(workspace.root / "knowledge_base/audit.jsonl", "answer_created", assistant_message)
    except OSError:
        st.session_state.audit_write_failed = True
    if answer_language == "Auto": st.session_state.auto_language = language
    st.session_state.last_sources = documents
    st.session_state.smart_cache = result["cache"]
    persist_current()
    st.rerun()

if st.session_state.pop("versions_changed", False):
    persist_current()
