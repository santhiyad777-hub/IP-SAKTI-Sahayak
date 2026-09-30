"""Deterministic product intake, evidence provenance and local review exports.

These helpers do not classify products or generate legal conclusions.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from utils.language import MESSAGES, is_abstention

PROFILE_FIELDS = {
    "use": "Intended use", "route": "Route of use", "claim": "Exact label claim",
    "formula": "Ingredients / authoritative text / preparation method",
    "novelty": "Changes from the traditional formula",
    "origin": "Biological resource and source location",
    "resource_status": "Cultivated or wild resource / origin evidence",
    "applicant": "Applicant nationality / ownership or control",
    "activity": "Intended activity", "destination": "Destination country or region",
}


def profile_prompt(profile, task="classification"):
    if task not in {"classification", "abs"}:
        raise ValueError("Unknown product task")
    fields = {k: str(profile.get(k, "")).strip()[:2000] or "unknown" for k in PROFILE_FIELDS}
    if task == "classification":
        request = "Help classify this Ayurveda formulation."
    else:
        request = "Assess the ABS questions for my product using the supplied facts and cited sources."
    # The existing classifier uses these headings to request only missing facts.
    return (request + "\nUse/claims: " + ("unknown" if not all(fields[k] != "unknown" for k in ("use", "route", "claim")) else
            f"Intended use: {fields['use']}; route: {fields['route']}; claim: {fields['claim']}") +
            "\nText/composition/process: " + fields["formula"] +
            "\nOrigin/applicant/activity: " + ("unknown" if all(fields[k] == "unknown" for k in ("origin", "applicant", "activity")) else
            f"Origin: {fields['origin']}; applicant: {fields['applicant']}; activity: {fields['activity']}") +
            "\nDestination: " + fields["destination"] +
            "\nUser-supplied facts (not independently verified):\n" + json.dumps(fields, ensure_ascii=False) +
            "\nAsk only for a missing fact that materially changes the answer. Do not assume approval or patentability.")


def evidence_passport(message):
    """Expose only references actually present in the answer, not all search hits."""
    answer = message.get("original_answer", message.get("content", ""))
    contexts = message.get("retrieved_context", [])
    references = sorted({int(i) for i in re.findall(r"\[(\d+)\]", answer)})
    sources = []
    unresolved = []
    for number in references:
        if not 1 <= number <= len(contexts):
            unresolved.append(number)
            continue
        context = contexts[number - 1]
        meta = context.get("metadata", {})
        sources.append({"reference": number, "source_id": meta.get("source_id", ""),
            "title": meta.get("title") or Path(meta.get("source", "Document")).name,
            "url": meta.get("source_url", ""), "jurisdiction": meta.get("jurisdiction", "unspecified"),
            "regime": meta.get("regime", "unspecified"), "pdf_page": meta["page"] + 1 if type(meta.get("page")) is int else None,
            "retrieved_at": meta.get("retrieved_at", "Unknown"), "version": meta.get("version", "Not recorded"),
            "content_hash": meta.get("content_hash", ""), "source_type": meta.get("source_type", "unknown"),
            "excerpt": context.get("page_content", "")})
    if is_abstention(answer):
        status = "Insufficient evidence"
    elif message.get("response_kind") == "clarification" or any(m["unassigned"] in answer for m in MESSAGES.values()):
        status = "Awaiting product details"
    elif unresolved:
        status = "Citation needs review"
    elif sources:
        partial = any(m["partial"] in answer for m in MESSAGES.values())
        status = "Partial source-linked answer" if partial else "Source-linked answer"
    else:
        status = "No cited legal conclusion"
    return {"schema_version": 1, "message_id": message.get("message_id", ""),
        "jurisdiction": message.get("jurisdiction", "Not recorded"), "status": status,
        "confidence_note": "Evidence availability only; not a probability of legal correctness.",
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "sources": sources, "unresolved_references": unresolved}


def review_pack(chat):
    """Downloadable user-controlled handoff; no emails or external transmission."""
    profile = chat.get("product_profile", {})
    lines = ["# IP-SAKTI — Expert review pack", "", "Information only, not legal advice. Human review requested.",
             "This file can contain confidential product information. Review before sharing.", "", "## Product facts (user supplied)"]
    lines += [f"- {label}: {profile.get(key) or 'Not supplied'}" for key, label in PROFILE_FIELDS.items()]
    lines += ["", "## Questions, answers and evidence"]
    for message in chat.get("messages", []):
        if message.get("role") == "user":
            lines += ["", "### Question", message.get("content", "")]
        elif message.get("role") == "assistant":
            passport = evidence_passport(message)
            lines += ["", f"### Answer — {passport['jurisdiction']} / {passport['status']}",
                      message.get("original_answer", message.get("content", ""))]
            for source in passport["sources"]:
                lines.append(f"- Evidence [{source['reference']}]: {source['title']} | {source['url']} | PDF page: {source['pdf_page']} | Retrieved: {source['retrieved_at']} | SHA-256: {source['content_hash'] or 'Not recorded'}")
    lines += ["", "## Items for the facilitator to verify",
              "- Applicable product category and any missing facts.",
              "- Current provisions, amendments, exceptions and jurisdiction.",
              "- Patent/TK/prior-art and ABS implications for the actual product.",
              "- Whether additional permissions, evidence or professional review are needed.",
              "", "Find a facilitator: https://www.wipo.int/en/web/tisc",
              "No appointment, legal review or submission has been made by this app."]
    return "\n".join(lines)


def source_inventory(root, jurisdiction, today=None):
    """Local manifest health; a download date is never called legal currency."""
    path = Path(root) / "dataset/source_registry/curated.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    today = today or datetime.now(timezone.utc).date()
    result = []
    for row in rows:
        if row.get("jurisdiction") != jurisdiction:
            continue
        age = None
        try:
            age = (today - datetime.fromisoformat(row.get("retrieved_at", "")[:10]).date()).days
        except (ValueError, TypeError):
            pass
        local = (Path(root) / row.get("local_file_path", "")).resolve()
        exists = local.is_relative_to(Path(root).resolve()) and local.is_file()
        result.append({"Title": row.get("title", row.get("source_id", "")), "Regime": row.get("regime", ""),
            "Acquisition": row.get("status", "unknown"), "Local file": "Present" if exists else "Missing",
            "Retrieved": row.get("retrieved_at", "Unknown"), "Age (days)": age,
            "Version": row.get("version", "Not recorded"), "Official URL": row.get("source_url", ""),
            "Review": "Check snapshot" if age is None or age < 0 or age > 30 or not exists else "Downloaded within 30 days; legal currency unverified"})
    return result


def record_event(path, event, message=None):
    """Allowlisted metadata only. Never log questions, answers, keys or product facts."""
    if event not in {"answer_created", "profile_saved"}:
        raise ValueError("Unknown audit event")
    message = message or {}
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event}
    if event == "answer_created":
        passport = evidence_passport(message)
        entry.update(jurisdiction=passport["jurisdiction"], status=passport["status"],
                     cited_sources=len(passport["sources"]), unresolved_references=len(passport["unresolved_references"]))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

def structured_profile(question):
    marker = 'User-supplied facts (not independently verified):\n'
    if marker not in question or not question.startswith(('Help classify this Ayurveda formulation.', 'Assess the ABS questions for my product')):
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(question.split(marker, 1)[1])
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or any(not isinstance(data.get(k, ''), str) for k in PROFILE_FIELDS):
        return None
    return ('abs' if question.startswith('Assess the ABS') else 'classification', data)


def profile_retrieval_query(question):
    parsed = structured_profile(question)
    if not parsed:
        return question
    task, fields = parsed
    if task == 'abs':
        query = 'Access and benefit sharing Biological Diversity Act NBA rules. Resource source: ' + fields.get('origin', '') + '; applicant: ' + fields.get('applicant', '') + '; activity: ' + fields.get('activity', '') + '; resource status: ' + fields.get('resource_status', '')
    else:
        query = 'Ayurveda product classification Drugs and Cosmetics Act definition. Intended use: ' + fields.get('use', '') + '; route: ' + fields.get('route', '') + '; label claim: ' + fields.get('claim', '') + '; composition: ' + fields.get('formula', '')
    if '\nUser clarification:' in question:
        query += '\nUser clarification:' + question.split('\nUser clarification:',1)[1]
    return query
