import json
from pathlib import Path
from rag.conversation import respond
questions=[('What labelling requirements apply to Ayurveda Aahara products?','india'),('Can I patent a traditional Ayurvedic formulation?','india'),('What does the official GI registry say about Navara Rice?','india'),('How does the Budapest Treaty help with microorganism deposits for patents?','international')]
rows=[]
for question,jurisdiction in questions:
    try:
        result=respond(question,jurisdiction=jurisdiction,answer_language='English')
        rows.append({'question':question,'jurisdiction':jurisdiction,'answer':result['answer']})
    except Exception as exc:
        rows.append({'question':question,'error':type(exc).__name__})
    Path('evaluation/accuracy_verified_answers.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(question,flush=True)
