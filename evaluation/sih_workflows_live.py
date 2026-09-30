"""Live profile flow smoke check. Sends fictional product facts to the provider."""
import json
from pathlib import Path
from rag.conversation import respond
from utils.workspace_tools import profile_prompt,evidence_passport
from utils.language import is_abstention

def main():
 profile={'use':'skin moisturising','route':'topical application','claim':'moisturises dry skin; no disease treatment claim','formula':'aloe gel and water; no authoritative Ayurvedic text claimed','novelty':'none claimed','origin':'aloe sourced in India','applicant':'Indian-owned company','activity':'commercial manufacture','destination':'India'}
 rows=[]
 for task in ('classification','abs'):
  question=profile_prompt(profile,task)
  try:
   result=respond(question,jurisdiction='india',answer_language='English')
   msg={'original_answer':result['answer'],'jurisdiction':'india','response_kind':'clarification' if result['cache'].get('pending_question') else 'answer','retrieved_context':[{'page_content':d.page_content,'metadata':d.metadata} for d in result['documents']]}
   passport=evidence_passport(msg)
   row={'task':task,'answer':result['answer'],'response_kind':msg['response_kind'],'abstained':is_abstention(result['answer']),'citation_references_resolve':not passport['unresolved_references'],'evidence_status':passport['status']}
  except Exception as exc:row={'task':task,'error':type(exc).__name__}
  rows.append(row)
  Path('evaluation/sih_workflows_live_results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({k:v for k,v in row.items() if k!='answer'}),flush=True)
if __name__=='__main__':main()
