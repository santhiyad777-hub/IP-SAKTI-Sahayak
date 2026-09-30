"""Exercise the exact conversation workflow used by Streamlit with real providers."""
import json
import argparse
import sys
import time
from config import BASE_DIR
from rag.conversation import respond
from utils.language import language_matches, is_abstention, messages, TANGLISH
sys.stdout.reconfigure(encoding="utf-8")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--only",type=int,nargs="+",help="Rerun selected one-based cases, preserving recorded results for others.")
    args=parser.parse_args()
    original=json.loads((BASE_DIR/"evaluation/questions.json").read_text(encoding="utf-8"))
    cases=[
        {"question":original[14]["question"],"language":"Tamil","sources":["patents_3"]},
        {"question":"English la sollu","language":"English","sources":["patents_3"],"followup":True},
        {"question":"Hindi mein batao","language":"Hindi","sources":["patents_3"],"followup":True},
        {"question":"Tanglish la sollu","language":TANGLISH,"sources":["patents_3"],"followup":True},
        {"question":"GI registration pathi sollu","language":TANGLISH,"sources":["ip_india_gi_act"]},
        {"question":"Traditional knowledge patent panna mudiyuma?","language":TANGLISH,"sources":["patents_3"]},
        {"question":original[15]["question"],"language":"Hindi","sources":["patents_3"]},
        {"question":"What does Section 3(p) say about traditional knowledge?","answer_language":"Tamil","language":"Tamil","sources":["patents_3"]},
        {"question":"எனது ரகசிய TKDL பதிவைத் தரவும்","language":"Tamil","abstain":True},
        {"question":"எனது ஆயுர்வேத தயாரிப்பை வகைப்படுத்துங்கள்","language":"Tamil","classification":True},
    ]
    cache={}
    history=[]
    rows=[]
    result_path=BASE_DIR/"evaluation/language_flow_results.json"
    previous=json.loads(result_path.read_text(encoding="utf-8")) if args.only and result_path.exists() else []
    for index,case in enumerate(cases,1):
        if args.only and index not in args.only:
            if len(previous)<index: raise ValueError("Run all cases once before selecting reruns.")
            row=previous[index-1]
            rows.append(row)
            if row.get("answer"):
                history += [{"role":"user","content":row["question"]},{"role":"assistant","content":row["answer"],"language":row.get("actual_language","English")}]
            cache={}
            continue
        start=time.monotonic()
        row=dict(case)
        try:
            result=respond(case["question"],history=history,answer_language=case.get("answer_language","Auto"),use_bhashini=True,cache=cache)
            cache=result["cache"]
            history += [{"role":"user","content":case["question"]},{"role":"assistant","content":result["answer"],"language":result["language"]}]
            answer=result["answer"]
            found=[d.metadata.get("source_id") for d in result["documents"]]
            wording=messages(case["language"])
            # Check the generated body, excluding original source titles and URLs.
            body=answer.split("**"+wording["sources"]+"**")[0]
            language_pass=result["language"]==case["language"] and language_matches(body,case["language"])
            outcome_pass=is_abstention(answer) if case.get("abstain") else (
                wording["unassigned"] in answer if case.get("classification") else
                not is_abstention(answer) and "**"+wording["sources"]+"**" in answer
                and all(s in found for s in case.get("sources",[])))
            followup_pass=result["followup"]==case.get("followup",False)
            row.update(answer=answer,retrieval_query=result["retrieval_query"],found_sources=found,
                actual_language=result["language"],language_pass=language_pass,outcome_pass=outcome_pass,
                followup_pass=followup_pass,passed=language_pass and outcome_pass and followup_pass)
        except Exception as error:
            row.update(passed=False,error_type=type(error).__name__)
            from utils.bhashini import BhashiniError
            if isinstance(error, BhashiniError): row["error"] = str(error)
        row["seconds"]=round(time.monotonic()-start,2)
        rows.append(row)
        (BASE_DIR/"evaluation/language_flow_results.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in row.items() if k not in ("answer","found_sources","retrieval_query")},ensure_ascii=False),flush=True)
    result_path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Passed",sum(r["passed"] for r in rows),"/",len(rows),flush=True)
    raise SystemExit(0 if all(r["passed"] for r in rows) else 1)

if __name__=="__main__":
    main()
