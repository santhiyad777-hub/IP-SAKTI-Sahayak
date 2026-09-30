"""Retrieval evaluation; --live also invokes the configured Ollama service.
Metrics are source hit@8 and source recall, not legal-answer accuracy.
"""
import argparse,json,time,sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
from config import BASE_DIR
from rag.chatbot import ask_llm,prepare_query
from utils.language import is_abstention
from rag.retriever import retrieve_documents
from ingestion.pipeline import write_json

def main():
    p=argparse.ArgumentParser(); p.add_argument('--live',action='store_true'); p.add_argument('--trace',action='store_true'); p.add_argument('--limit',type=int,default=100); args=p.parse_args()
    cases=json.loads((BASE_DIR/'evaluation/questions.json').read_text(encoding='utf-8'))[:args.limit]
    rows=[]
    trace=[]
    if args.trace:
        import rag.chatbot as chatbot
        original=chatbot.call_json
        def traced(system,payload):
            result=original(system,payload)
            trace.append({"kind":"audit" if "auditor" in system else "generation", "result":result})
            write_json(BASE_DIR/"evaluation/diagnostic_trace.json",trace)
            return result
        chatbot.call_json=traced
    for case in cases:
        start=time.perf_counter(); row=dict(case)
        try:
            query=prepare_query(case['question']) if args.live else case['question']
            if not args.live and case.get('language'):
                row['status']='requires query translation (live)'; rows.append(row); continue
            docs=retrieve_documents(query,case['jurisdiction'])
            found={d.metadata.get('source_id') for d in docs}; expected=set(case.get('expected_sources',[]))
            row.update(retrieval_query=query,sources=sorted(found),hit_at_8=bool(found & expected) if expected else None,
                expected_source_recall=len(found & expected)/len(expected) if expected else None,
                jurisdiction_pass=all(d.metadata.get('jurisdiction')==case['jurisdiction'] for d in docs))
            if args.live:
                row['answer']=ask_llm(case['question'],docs,jurisdiction=case['jurisdiction'],language=case.get('language','English'))
                row['abstained']=is_abstention(row['answer'])
            row['status']='completed'
        except Exception as exc: row.update(status='error',error=type(exc).__name__+': '+str(exc)[:150])
        row['seconds']=round(time.perf_counter()-start,2); rows.append(row)
        print({k:v for k,v in row.items() if k not in {'answer','retrieval_query'}},flush=True)
        write_json(BASE_DIR/'evaluation'/('live_results.json' if args.live else 'retrieval_results.json'),rows)
if __name__=='__main__': main()
