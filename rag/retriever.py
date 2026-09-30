"""Jurisdiction-filtered semantic + BM25 retrieval; scores are not confidence."""
import math
import re
from functools import lru_cache
from collections import Counter
from pathlib import Path
from langchain_core.documents import Document
from config import BASE_DIR, CORPUS_COLLECTION, RETRIEVAL_K, MIN_SEMANTIC_SCORE, UPLOAD_FOLDER
from vectordb.chroma_manager import load_vector_database, load_private_database
STOP = set("a an the is are was were what which how why can could should do does i my me we our to of in on for and or with from it this that about please explain tell reply english tamil hindi".split())

def tokens(text):
    normalized = re.sub(r"\bsection\s*(\d+[a-z]?)\s*\(([a-z0-9]+)\)", r"section \1\2 \1\2", text.lower())
    normalized = re.sub(r"\b(\d+[a-z]?)\s*\(([a-z0-9]+)\)", r"\1\2 \1", normalized)
    return ["patent" if t.startswith("patent") else t for t in re.findall(r"[a-z0-9]+", normalized) if t not in STOP and (len(t) > 1 or t.isdigit() or t in {'a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p'})]

def bm25(query, texts):
    terms = set(tokens(query)); counts = [Counter(tokens(t)) for t in texts]
    lengths = [sum(c.values()) for c in counts]; avg = sum(lengths) / max(1, len(lengths)) or 1
    df = Counter(t for c in counts for t in c if t in terms)
    return [sum(math.log(1+(len(texts)-df[t]+.5)/(df[t]+.5)) * c[t]*2.5 /
            (c[t]+1.5*(.25+.75*length/avg)) for t in terms if c[t])
            for c,length in zip(counts,lengths)]

def resolve_source_path(raw_path_str):
    if not raw_path_str:
        return None
    p = Path(raw_path_str)
    if p.is_file():
        return p
    # Try relative to BASE_DIR
    rel = BASE_DIR / raw_path_str
    if rel.is_file():
        return rel
    return None

@lru_cache(maxsize=64)
def full_page(path_str, modified, page):
    p = resolve_source_path(path_str)
    if not p or not p.is_file():
        return ""
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(p))
        if 0 <= page < len(reader.pages):
            return reader.pages[page].extract_text() or ""
    except Exception:
        pass
    return ""

def route_regimes(question):
    routes = {
        "patents": r"\b(patent\w*|pct|budapest|microorganism|24b|form\s*(?:1|2|3|18|18a|27)|rfe|fer|section\s*3|3\s*\([a-p]\)|synerg\w*|prior.art)\b",
        "traditional_knowledge": r"\b(tkdl|gratk|traditional knowledge|prior.art|biopiracy|tulasi|ocimum|ashwagandha|neem|turmeric|haldi|ayurved\w*|herbal)\b",
        "biodiversity_abs": r"\b(abs|biodiversity|nagoya|biological resources?|benefit.sharing|nba|sbb|form\s*(?:i|ii|iii|iv))\b",
        "gi": r"\b(geographical indication|gi registration|gi registry|navara|appellation)\b",
        "trademarks": r"\b(trade.?marks?|madrid|brand name|section\s*9)\b",
        "designs": r"\b(designs?|hague)\b",
        "copyright": r"\bcopyright\b",
        "plant_variety": r"\b(plant variet|farmers. rights|cultivator)\w*",
        "food_regulation": r"\b(aahar\w*|food|nutraceutical|fssai|dietary)\b",
        "drug_regulation": r"\b(drugs?|formulation|classical|proprietary|phytopharmaceutical|cosmetic|cdsco|158b|schedule e-1|schedule t|gmp|magic remedies|advertisement)\b",
        "trade_secrets": r"\b(trade secret|confidential)\b",
        "export_eu": r"\b(eu|europe|european|ema)\b",
        "export_us": r"\b(usa|united states|fda|cder|nda|ind)\b",
        "export_uk": r"\b(uk|united kingdom|britain|mhra|thr)\b",
        "privacy": r"\b(dpdp|privacy|personal data|data fiduciary|data principal)\b",
        "ai_governance": r"\b(nist|ai rmf|ai risk|ai governance)\b",
    }
    matched = [name for name,pattern in routes.items() if re.search(pattern,question,re.I)]
    if any(name in matched for name in ("food_regulation", "drug_regulation")) and not re.search(
            r"tkdl|traditional knowledge|prior.art|biopiracy|gratk|patent", question, re.I):
        matched = [name for name in matched if name != "traditional_knowledge"]
    # A formulation mentioned in a patent question is not itself a drug-regulation request.
    if "patents" in matched and not re.search(r"licen[sc]|drug|safety|approval|classif|cdsco|gmp", question, re.I):
        matched = [name for name in matched if name != "drug_regulation"]
    return matched

def retrieve_documents(question, jurisdiction="india", mode="Knowledge base", selected_files=None, k=RETRIEVAL_K, workspace=None):
    if mode not in {"Knowledge base", "Uploaded documents", "Knowledge base + uploads"}:
        raise ValueError("Unknown knowledge-source mode.")
    if jurisdiction not in {"india", "international"}:
        raise ValueError("Choose India or international; jurisdictions cannot be mixed.")
    if mode != "Knowledge base" and workspace is None:
        raise PermissionError("Authentication required for private retrieval.")
    owner = workspace.owner if workspace is not None else None
    upload_folder = workspace.uploads if workspace is not None else Path(UPLOAD_FOLDER)
    candidates = []
    collections = ([CORPUS_COLLECTION] if mode == "Knowledge base" else
                   ["langchain"] if mode == "Uploaded documents" else [CORPUS_COLLECTION, "langchain"])
    for name in collections:
        db = load_vector_database(name) if name == CORPUS_COLLECTION else load_private_database(workspace)
        where = {"jurisdiction": jurisdiction} if name == CORPUS_COLLECTION else {"owner_id":owner}
        regimes = route_regimes(question)
        if name == CORPUS_COLLECTION and regimes:
            # TRIPS remains relevant to international IP routes.
            if jurisdiction == "international": regimes = regimes + ["trade_treaty"]
            where = {"$and": [where, {"regime": {"$in": regimes}}]}
        if name == "langchain" and selected_files:
            source_paths=[]
            for filename in selected_files:
                if Path(filename).name != filename: raise ValueError("Invalid upload selection")
                source_paths.append(str(workspace.upload_path(filename)))
            where={"$and":[where,{"source":{"$in":source_paths}}]}
        rows = db.get(where=where, include=["documents", "metadatas"])
        docs = [Document(page_content=t, metadata=m or {}) for t,m in zip(rows["documents"],rows["metadatas"])]
        if name == "langchain":
            docs = [d for d in docs if d.metadata.get("owner_id")==owner and (upload_folder/Path(d.metadata.get("source", "")).name).is_file()
                    and (not selected_files or Path(d.metadata.get("source", "")).name in selected_files)]
        if not docs:
            continue
        text = [d.metadata.get("title", "") + " " + d.metadata.get("section", "") + " " + d.page_content for d in docs]
        lexical = bm25(question, text)
        # Chroma's legacy collection uses L2 on normalized embeddings: cosine = 1 - squared L2/2.
        semantic = db.similarity_search_with_score(question, k=min(32, len(rows["ids"])), filter=where)
        sims = {d.page_content: max(-1., 1.-float(distance)/2.) for d,distance in semantic}
        lex_rank = {i:rank for rank,i in enumerate(sorted(range(len(docs)),key=lambda i:lexical[i],reverse=True)) if lexical[i]>0}
        sem_rank = {d.page_content:rank for rank,(d,_) in enumerate(semantic)}
        q = set(tokens(question))
        for i,d in enumerate(docs):
            sim = sims.get(d.page_content, -1.)
            overlap = len(q & set(tokens(text[i]))) / max(1,len(q))
            category_definition = bool(re.search(r"\b(classif\w*|definition|define)\b", question, re.I) and
                re.search(r"\b(?:cosmetic|drug|medicine)\W{0,8}(?:means|includes)\b", d.page_content, re.I))
            if not category_definition and sim < MIN_SEMANTIC_SCORE and not (lexical[i]>=3 and overlap >= .25):
                continue
            score = (1/(60+lex_rank[i]) if i in lex_rank else 0) + (1/(60+sem_rank[d.page_content]) if d.page_content in sem_rank else 0)
            if category_definition: score += .04
            d.metadata.update(retrieval_score=round(score,6), semantic_score=round(sim,4))
            candidates.append((score,d))
    selected=[]; seen=set(); seen_pages=set(); per_source=Counter()
    ranked=sorted(candidates,key=lambda x:x[0],reverse=True)
    routes=route_regimes(question)
    if len(routes)>1:
        first=[]
        for regime in routes:
            match=next((pair for pair in ranked if pair[1].metadata.get("regime")==regime),None)
            if match: first.append(match)
        ranked=first+ranked
    for score,d in ranked:
        key=re.sub(r"\s+"," ",d.page_content).strip()
        source=d.metadata.get("source_id",d.metadata.get("source",""))
        page_key=(source,d.metadata.get("page")) if "page" in d.metadata else None
        if key in seen or (page_key is not None and page_key in seen_pages) or per_source[source]>=4:
            continue
        seen.add(key)
        if page_key is not None: seen_pages.add(page_key)
        per_source[source]+=1; selected.append(d)
        if len(selected)>=k: break
    # Give generation the full cited PDF page, avoiding mid-sentence chunk boundaries.
    for d in selected:
        m=d.metadata; path_str=m.get("source","")
        p=resolve_source_path(path_str)
        if m.get("source_type") == "official_pdf" and "page" in m and p and p.suffix.lower()==".pdf":
            content=full_page(str(p),p.stat().st_mtime_ns,int(m["page"]))
            if content.strip() and len(content)<=12000: d.page_content=content
        elif m.get("source_type")=="official_web" and p and p.suffix==".txt":
            try:
                content=p.read_text(encoding="utf-8")
                if len(content)<=10000: d.page_content=content
            except Exception:
                pass
    unique=[]; keys=set()
    for d in selected:
        key=(d.metadata.get("source_id"),d.metadata.get("page"),d.page_content)
        if key not in keys: unique.append(d); keys.add(key)
    return unique

def get_retriever():
    # Compatibility entry point for existing callers.
    from langchain_core.runnables import RunnableLambda
    return RunnableLambda(retrieve_documents)
