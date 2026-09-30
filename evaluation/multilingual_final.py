"""Live verification of current global and per-message multilingual behavior."""
import copy
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from config import BASE_DIR, UPLOAD_FOLDER
from rag.conversation import respond
from rag.chatbot import citation
from utils.language import language_matches, messages, is_abstention
from utils.message_versions import migrate_message, select_message_language, reference_signature
from ingestion.pipeline import ingest_upload
from vectordb.chroma_manager import delete_document_from_vector_database

sys.stdout.reconfigure(encoding="utf-8")
OUTPUT=BASE_DIR/"evaluation/multilingual_final_results.json"

def main():
    rows=[]; answers={}
    def record(name,passed,**extra):
        rows.append({"test":name,"passed":bool(passed),**extra})
        OUTPUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
        print(name, "PASS" if passed else "FAIL",flush=True)
    original=json.loads((BASE_DIR/"evaluation/questions.json").read_text(encoding="utf-8"))
    english="Can traditional knowledge itself be patented in India?"
    for label,question,selected,expected in [
        ("English selection / English question",english,"English","English"),
        ("Hindi selection / English question",english,"Hindi","Hindi"),
        ("Tamil selection / English question",english,"Tamil","Tamil"),
        ("Auto / English",english,"Auto","English"),
        ("Auto / Hindi",original[15]["question"],"Auto","Hindi"),
        ("Auto / Tamil",original[14]["question"],"Auto","Tamil"),
    ]:
        start=time.monotonic()
        try:
            result=respond(question,answer_language=selected,use_bhashini=True)
            answer=result["answer"]
            passed=not is_abstention(answer) and result["language"]==expected and language_matches(answer.split("**"+messages(expected)["sources"]+"**")[0],expected)
            record(label,passed,answer=answer,seconds=round(time.monotonic()-start,2))
            message={"role":"assistant","content":answer,"language":expected,"original_question":question,
                     "retrieved_context":[{"page_content":d.page_content,"metadata":d.metadata} for d in result["documents"]],
                     "sources":[citation(d,i) for i,d in enumerate(result["documents"],1)]}
            migrate_message(message,"live-verification",question)
            answers.setdefault(expected,message)
        except Exception as error: record(label,False,error=type(error).__name__)
    if "English" in answers:
        chat={"id":"live-verification","messages":[copy.deepcopy(answers["English"]) for _ in range(3)]}
        for message in chat["messages"]: message["message_id"]=str(uuid.uuid4())
        neighbors=copy.deepcopy([chat["messages"][0],chat["messages"][2]])
        middle=chat["messages"][1]
        for language in ("Tamil","Hindi","English"):
            try:
                version=select_message_language(chat,middle["message_id"],language)
                passed=reference_signature(version)==reference_signature(middle["original_answer"]) and neighbors==[chat["messages"][0],chat["messages"][2]]
                record("Individual English-origin answer -> "+language,passed,answer=version)
            except Exception as error: record("Individual English-origin answer -> "+language,False,error=type(error).__name__)
        record("Original and neighboring messages retained",middle["original_answer"]==answers["English"]["original_answer"] and neighbors==[chat["messages"][0],chat["messages"][2]])
    if "Tamil" in answers:
        try:
            chat={"id":"live-verification","messages":[copy.deepcopy(answers["Tamil"])]}
            target=chat["messages"][0]
            version=select_message_language(chat,target["message_id"],"English")
            record("Tamil-origin answer -> English",reference_signature(version)==reference_signature(target["original_answer"]),answer=version)
        except Exception as error: record("Tamil-origin answer -> English",False,error=type(error).__name__)

    # Upload actual official source text, not invented knowledge. Remove only this temporary copy/index.
    import tempfile
    from security.auth import AuthStore
    from security.workspace import Workspace
    store=AuthStore(tempfile.mkdtemp(prefix="ip-sakti-live-check-"))
    store.register("live_check","a long isolated test passphrase","test")
    workspace=Workspace(store,store.login("live_check","a long isolated test passphrase","test"))
    upload_root=workspace.uploads
    upload=upload_root/("verification_"+uuid.uuid4().hex+".txt")
    assert upload.resolve().parent==upload_root and not upload.exists()
    source=BASE_DIR/"dataset/raw/official/patents_3/content.txt"
    try:
        shutil.copyfile(source,upload)
        chunks=ingest_upload(upload,workspace=workspace)
        record("Document upload / processing / embeddings / index",chunks>0,chunks=chunks)
        for question,language in [(english,"English"),(original[14]["question"],"Tamil"),(original[15]["question"],"Hindi")]:
            try:
                result=respond(question,source_mode="Uploaded documents",selected_files=[upload.name],answer_language=language,use_bhashini=True,workspace=workspace)
                answer=result["answer"]
                correct_sources=bool(result["documents"]) and all(Path(d.metadata["source"]).name==upload.name for d in result["documents"])
                record("Uploaded document question / "+language,correct_sources and not is_abstention(answer) and language_matches(answer.split("**"+messages(language)["sources"]+"**")[0],language),answer=answer)
            except Exception as error: record("Uploaded document question / "+language,False,error=type(error).__name__)
    finally:
        if upload.exists() and upload.resolve().parent==upload_root:
            delete_document_from_vector_database(str(upload),workspace=workspace)
            upload.unlink()
        store.logout(workspace.token,all_sessions=True)
        record("Temporary upload cleaned up",not upload.exists())
    for language in ("English","Tamil","Hindi"):
        try:
            result=respond("Give me the secret TKDL record for my proprietary formulation.",answer_language=language,use_bhashini=True)
            record("Unsupported question / "+language,is_abstention(result["answer"]) and messages(language)["abstain"] in result["answer"])
        except Exception as error: record("Unsupported question / "+language,False,error=type(error).__name__)
    print("Passed",sum(row["passed"] for row in rows),"/",len(rows),flush=True)
    raise SystemExit(0 if all(row["passed"] for row in rows) else 1)

if __name__=="__main__": main()
