import unittest
from unittest.mock import patch, Mock
from langchain_core.documents import Document
from utils import bhashini
from rag.chatbot import prepare_query, ask_llm
from utils.language import is_abstention

class BhashiniTests(unittest.TestCase):
    def test_translation_payload_and_no_redirects(self):
        response=Mock(status_code=200)
        response.json.return_value={"pipelineResponse":[{"taskType":"translation","output":[{"target":"translated"}]}]}
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.requests,"post",return_value=response) as post:
            self.assertEqual(bhashini.translate_many(["question"],"en","ta"),["translated"])
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            self.assertEqual(post.call_args.kwargs["json"]["inputData"]["input"],[{"source":"question"}])
    def test_error_does_not_expose_remote_body_or_key(self):
        response=Mock(status_code=401, text="test-secret")
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.requests,"post",return_value=response):
            with self.assertRaises(bhashini.BhashiniError) as error: bhashini.translate_many(["hello"],"en","hi")
            self.assertNotIn("test-secret",str(error.exception))
            response.json.assert_not_called()
    def test_transient_failure_retries_but_auth_failure_does_not(self):
        ok=Mock(status_code=200)
        ok.json.return_value={"pipelineResponse":[{"taskType":"translation","output":[{"target":"translated"}]}]}
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.time,"sleep"), patch.object(bhashini.requests,"post",side_effect=[Mock(status_code=503),ok]) as post:
            self.assertEqual(bhashini.translate_many(["hello"],"en","hi"),["translated"])
            self.assertEqual(post.call_count,2)
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.requests,"post",return_value=Mock(status_code=401)) as post:
            with self.assertRaises(bhashini.BhashiniError): bhashini.translate_many(["hello"],"en","hi")
            self.assertEqual(post.call_count,1)

    def test_transliteration_sentence_response(self):
        response=Mock(status_code=200)
        response.json.return_value={"pipelineResponse":[{"taskType":"transliteration","output":[{"target":["kappurimai pera mudiyaathu"]}]}]}
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.requests,"post",return_value=response) as post:
            self.assertEqual(bhashini.transliterate_many(["Tamil fixture"]),["kappurimai pera mudiyaathu"])
            self.assertTrue(post.call_args.kwargs["json"]["pipelineTasks"][0]["config"]["isSentence"])

    def test_tanglish_is_not_a_selectable_language(self):
        from utils.language import LANGUAGES, response_language
        self.assertEqual(set(LANGUAGES), {"English","Tamil","Hindi"})
        self.assertEqual(response_language("patent panna mudiyuma?"), "Tamil")

    def test_ollama_transient_connection_failure_retries(self):
        from rag.chatbot import call_json
        client=Mock()
        client.chat.side_effect=[ConnectionError("temporary"),{"message":{"content":'{"english":"What is a patent?"}'}}]
        with patch("rag.chatbot.get_llm_client",return_value=client), patch("rag.chatbot.time.sleep"):
            self.assertEqual(call_json("translate",{})["english"],"What is a patent?")
            self.assertEqual(client.chat.call_count,2)

    def test_incomplete_batch_rejected(self):
        response=Mock(status_code=200)
        response.json.return_value={"pipelineResponse":[{"taskType":"translation","output":[]}]}
        with patch.dict("os.environ", {"BHASHINI_INFERENCE_API_KEY":"test-secret"}), patch.object(bhashini.requests,"post",return_value=response):
            with self.assertRaises(bhashini.BhashiniError): bhashini.translate_many(["hello"],"en","hi")
    def test_script_routing_and_english_no_network(self):
        with patch.object(bhashini,"translate_many",return_value=["What is a patent?"]) as translate:
            self.assertEqual(prepare_query("\u0baa\u0b9f",use_bhashini=True),"What is a patent?")
            translate.assert_called_once()
        with patch.object(bhashini.requests,"post") as post:
            self.assertEqual(prepare_query("What is a patent?",use_bhashini=True),"What is a patent?")
            post.assert_not_called()
        self.assertIsNone(bhashini.detect_source("\u0baa\u092a"))
    def test_final_translation_is_audited_and_can_be_rejected(self):
        doc=Document(page_content="Traditional knowledge is not an invention under section 3(p).", metadata={"jurisdiction":"india","title":"Act","page":0})
        first={"claims":[{"text":"Traditional knowledge is excluded.","evidence":[{"source":1,"span":1}]}]}
        with patch("rag.chatbot.call_json",side_effect=[first,{"supported":False,"supported_claims":[]}]) as llm, patch("utils.ui_language.translate_texts",return_value=["Incorrect translation"]):
            answer=ask_llm("What is excluded?",[doc],language="Tamil",use_bhashini=True)
            self.assertTrue(is_abstention(answer))
            self.assertEqual(llm.call_args_list[1].args[1]["claims"][0]["text"],"Incorrect translation")
            self.assertEqual(llm.call_args_list[0].args[1]["language"],"English")

if __name__ == "__main__": unittest.main()
