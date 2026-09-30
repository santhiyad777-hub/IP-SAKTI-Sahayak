"""The same conversation/language path is used by Streamlit and live checks."""
import re
from rag.chatbot import prepare_query, ask_llm, classification_questions
from rag.retriever import retrieve_documents
from utils.language import response_language, is_response_transformation
from utils.ui_language import greeting
from utils.workspace_tools import structured_profile, profile_retrieval_query

def respond(question, history=None, jurisdiction="india", source_mode="Knowledge base",
            selected_files=None, answer_language="Auto", use_bhashini=False, cache=None, workspace=None):
    cache = cache or {}
    private_args = {"workspace":workspace} if workspace is not None else {}
    selected_files = selected_files or []
    scope = (jurisdiction, source_mode, tuple(selected_files), use_bhashini)
    if workspace is not None: scope += (workspace.owner,)
    pending = cache.get("pending_question") if cache.get("scope") == scope else None
    # A new standalone question must not be treated as an answer to a prior prompt.
    if pending and re.match(r"^\s*(?:what|how|why|when|where|who|can|could|does|do|explain|tell me|an I)\b", question, re.I):
        pending = None
    if pending:
        question = f"{pending}\nUser clarification: {question}"

    # Reopened chats have persisted messages but no in-memory document cache.
    # Re-retrieve the original question under the CURRENT jurisdiction/source filters.
    if cache.get("scope") != scope and history and is_response_transformation(question, True):
        has_answer = any(m.get("role") == "assistant" for m in history)
        original = next((m.get("content", "") for m in reversed(history)
                         if m.get("role") == "user" and not is_response_transformation(m.get("content", ""), True)), None)
        if has_answer and original:
            previous = next(m for m in reversed(history) if m.get("role") == "assistant")
            query = prepare_query(original, history, use_bhashini=use_bhashini)
            documents = retrieve_documents(query, jurisdiction, source_mode, selected_files, **private_args)
            cache = {"last_answer": previous.get("content", ""), "last_question": original,
                     "language": previous.get("language") or response_language(original),
                     "retrieval_query": query, "documents": documents, "scope": scope}
    followup = cache.get("scope") == scope and is_response_transformation(
        question, bool(cache.get("last_answer")))
    default = cache.get("language", "English") if followup else "English"
    language = response_language(question, default) if answer_language == "Auto" else answer_language
    salutation = greeting(question, language)
    if salutation:
        return {"answer":salutation,"documents":[],"language":language,
                "retrieval_query":"","followup":False,"cache":{}}
    if not pending and not followup and classification_questions(question, jurisdiction):
        answer = ask_llm(question, [], history, jurisdiction, language,
                         use_bhashini=use_bhashini, classification_query=question)
        return {"answer": answer, "documents": [], "language": language,
                "retrieval_query": "", "followup": False,
                "cache": {"pending_question": question, "scope": scope}}
    if followup:
        documents = cache.get("documents", [])
        original_question = cache.get("last_question", "")
        retrieval_query = cache.get("retrieval_query", "")
        grounded_question = (
            f"Original question: {original_question}. Restate the answer using "
            f"the evidence with this instruction: {question}")
    else:
        original_question = question
        retrieval_query = prepare_query(profile_retrieval_query(question), history, use_bhashini=use_bhashini)
        needed = necessary_followup(question if structured_profile(question) else retrieval_query) if not pending else ""
        if needed:
            from utils.ui_language import translate_texts
            prompt = "To give a relevant answer, I need one detail. " + needed
            if language in ("Tamil", "Hindi"):
                prompt = translate_texts([prompt], "English", language, use_bhashini=use_bhashini)[0]
            return {"answer": prompt, "documents": [], "language": language,
                    "retrieval_query": retrieval_query, "followup": False,
                    "cache": {"pending_question": question, "scope": scope}}
        documents = retrieve_documents(retrieval_query, jurisdiction, source_mode, selected_files, **private_args)
        grounded_question = question
    if not documents and source_mode == "Uploaded documents":
        from utils.ui_language import tr
        answer = tr("No readable uploaded evidence is available. Choose Knowledge base to use the built-in sources, or upload and select a document.", language)
        return {"answer": answer, "documents": [], "language": language,
                "retrieval_query": retrieval_query, "followup": False, "cache": {}}
    answer = ask_llm(grounded_question, documents, history, jurisdiction, language,
                     use_bhashini=use_bhashini,
                     classification_query=retrieval_query if not followup else None)
    new_cache = {"last_answer": answer, "last_question": original_question,
                 "retrieval_query": retrieval_query, "language": language,
                 "documents": documents, "scope": scope}
    return {"answer": answer, "documents": documents, "language": language,
            "retrieval_query": retrieval_query, "followup": followup, "cache": new_cache}

def necessary_followup(question):
    """Ask for a decision-changing fact only for a personal/scenario request."""
    parsed = structured_profile(question)
    if parsed:
        task, fields = parsed
        if task == "abs" and any(not fields.get(k) or fields[k].lower() == "unknown" for k in ("origin", "applicant", "activity")):
            return "Which biological resource are you using, where is it sourced, who is the applicant, and what is the intended activity?"
        if task == "abs" and (not fields.get("resource_status") or fields["resource_status"].lower() == "unknown"):
            return "Are the biological resources cultivated or collected from the wild, and what evidence of their origin is available?"
        return ""
    q = question.lower()
    if re.search(r"\b(generally|overview|definition|define|what is|what are|explain|in general)\b", q):
        return ""
    personal = bool(re.search(r"\b(i|my|our|we|this product|this formulation|en|ennoda|naan|enga)\b", q))
    if not personal:
        return ""
    # An explicit answer is retained in the combined query. Do not repeat intake.
    if "user clarification:" in q:
        return ""
    if re.search(r"\bexport\w*\b", q):
        # Accept a named destination without maintaining a short country whitelist.
        destination = re.search(r"\b(?:to|into|in)\s+(?:the\s+)?([a-z][a-z -]{1,40})", re.split(r"\bexport\w*\b", q, maxsplit=1)[-1])
        missing_destination = not destination or re.match(r"abroad|another country|other countries|foreign|international|overseas", destination[1])
        if missing_destination:
            return "Which country or region do you plan to export to?"
    if "patent" in q and re.search(r"\b(formulation|product|invention|developed|ayurvedic)\b", q):
        if not re.search(r"(?:new|novel|different|changed)\s+(?:extraction|process|method|ingredient|combination)|novelty\s*:|new feature\s*:", q):
            # A general traditional-knowledge eligibility question needs a rule, not intake.
            if not ("traditional" in q and not re.search(r"\b(my|our|developed)\b",q)):
                return "What is new about your product: the ingredients, combination, preparation or extraction method, or something else?"
    if re.search(r"3\s*\([de]\)", q) and re.search(r"apply|applicable", q):
        if not re.search(r"claimed invention:|new feature:|novelty:", q):
            return "What exactly is claimed as new about your invention or combination?"
    if re.search(r"\babs\b|form iii|access and benefit", q):
        if not all(re.search(pattern,q) for pattern in (r"resource\s*:|neem|turmeric|plant|microorganism", r"research|commercial|commercialisation|commercialization|patent filing", r"sourc|origin|collected|purchased")):
            return "Which biological resource are you using, where is it sourced, and is it for research, commercial use or an IP filing?"
    if "regulations apply" in q and "product" in q and not re.search(r"medicine|food|cosmetic|nutraceutical",q):
        return "What is the product's intended use and the exact claim you plan to make on its label?"
    return ""
