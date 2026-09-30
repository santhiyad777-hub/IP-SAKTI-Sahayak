"""Server-side BHASHINI translation; never log credentials or remote error bodies."""
import os
import time
import requests
import config  # Load the project's local .env before reading settings.

ENDPOINT = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
LANGUAGES = {"English": "en", "Hindi": "hi", "Tamil": "ta"}

class BhashiniError(RuntimeError):
    pass

def configured():
    return bool(os.getenv("BHASHINI_INFERENCE_KEY", os.getenv("BHASHINI_INFERENCE_API_KEY", "")).strip())

def detect_source(text):
    # Only unambiguous scripts supported by the current UI. Latin/Tanglish
    # and mixed Indic scripts continue through the existing Ollama translator.
    scripts = set()
    for char in text:
        if "\u0900" <= char <= "\u097f": scripts.add("hi")
        elif "\u0b80" <= char <= "\u0bff": scripts.add("ta")
        elif char.isalpha() and ord(char) > 127: scripts.add("other")
    return next(iter(scripts)) if len(scripts) == 1 and "other" not in scripts else None

def translate_many(texts, source, target):
    return _compute(texts, source, target, "translation")

def transliterate_many(texts, source="ta", target="en"):
    return _compute(texts, source, target, "transliteration")

def _compute(texts, source, target, task_type):
    if source not in LANGUAGES.values() or target not in LANGUAGES.values():
        raise BhashiniError("Unsupported BHASHINI language selection.")
    if not texts or source == target: return list(texts)
    if any(not isinstance(t, str) or not t.strip() for t in texts):
        raise BhashiniError("Translation requires nonempty text.")
    if sum(len(t) for t in texts) > 20000:
        raise BhashiniError("Translation text is too long; shorten the question.")
    key = os.getenv("BHASHINI_INFERENCE_KEY", os.getenv("BHASHINI_INFERENCE_API_KEY", "")).strip()
    if not key: raise BhashiniError("Configure BHASHINI_INFERENCE_KEY in .env.")
    model = (os.getenv("BHASHINI_TRANSLITERATION_SERVICE_ID", "ai4bharat/indicxlit--cpu-fsv2")
             if task_type == "transliteration" else
             os.getenv("BHASHINI_TRANSLATION_SERVICE_ID", "ai4bharat/indictrans-v2-all-gpu--t4"))
    settings = {"language": {"sourceLanguage": source, "targetLanguage": target}, "serviceId": model}
    if task_type == "transliteration": settings.update(isSentence=True, numSuggestions=1)
    payload = {"pipelineTasks": [{"taskType": task_type, "config": settings}],
               "inputData": {"input": [{"source": t} for t in texts]}}
    # Translation is idempotent. Retry only transient transport/server failures;
    # invalid credentials and invalid payloads must surface immediately.
    for attempt in range(3):
        try:
            response = requests.post(ENDPOINT, headers={"Authorization": key, "Accept": "application/json"},
                json=payload, timeout=(10, 30), allow_redirects=False)
        except (requests.ConnectionError, requests.Timeout):
            if attempt < 2:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise BhashiniError("BHASHINI could not be reached after retries. Please retry shortly.") from None
        except requests.RequestException:
            raise BhashiniError("BHASHINI could not be reached. Check connectivity and retry.") from None
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
            time.sleep(0.5 * (2 ** attempt))
            continue
        break
    if response.status_code != 200:
        raise BhashiniError(f"BHASHINI returned HTTP {response.status_code}. Check inference-key access or retry later.")
    try:
        tasks = response.json()["pipelineResponse"]
        task = next(t for t in tasks if t.get("taskType") == task_type)
        values = [item["target"] for item in task["output"]]
        if task_type == "transliteration":
            values = [v[0] if isinstance(v, list) and v else v for v in values]
        if len(values) != len(texts) or any(not isinstance(t, str) or not t.strip() for t in values):
            raise ValueError()
        return values
    except (ValueError, KeyError, TypeError, StopIteration, AttributeError):
        raise BhashiniError("BHASHINI returned an incomplete translation. Retry the request.") from None
