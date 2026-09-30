import json,time
from pathlib import Path
from unittest.mock import patch
import rag.chatbot as chatbot
from rag.conversation import respond

original=chatbot.call_json
calls=[]
def trace(system,payload):
    result=original(system,payload)
    calls.append({'stage':'audit' if 'evidence auditor' in system else 'generation','result':result})
    print(json.dumps(calls[-1],ensure_ascii=True),flush=True)
    return result
results=[]
for question in ['En herbal product medicine-aa, food-aa, cosmetic-aa?','What labelling requirements apply to Ayurveda Aahara products?','an I patent a traditional Ayurvedic formulation?']:
    start=time.monotonic();calls=[]
    try:
        with patch('rag.chatbot.call_json',side_effect=trace):
            result=respond(question,answer_language='English',source_mode='Knowledge base')
        row={'question':question,'answer':result['answer'],'source_ids':sorted({d.metadata.get('source_id','') for d in result['documents']}),'abstained':chatbot.ABSTAIN in result['answer'],'calls':calls}
    except Exception as exc: row={'question':question,'error':str(exc),'calls':calls}
    row['seconds']=round(time.monotonic()-start,1)
    results.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    Path('evaluation/user_question_live_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
