import unittest
from unittest.mock import patch
from langchain_core.documents import Document
from utils.language import response_language, is_response_transformation, TANGLISH, messages, is_abstention
from rag.conversation import respond
from rag.chatbot import ask_llm, prepare_query

class LanguageTests(unittest.TestCase):
    def test_explicit_language_overrides_script(self):
        self.assertEqual(response_language("தமிழில் உள்ள பதிலை English la sollu"), "English")
        self.assertEqual(response_language("Hindi answer tamil la sollu"), "Tamil")
        self.assertEqual(response_language("தமிழில் உள்ள பதிலை tanglish la sollu"), "Tamil")
        self.assertEqual(response_language("हिंदी में बताओ"), "Hindi")

    def test_english_topic_mentions_do_not_change_language(self):
        self.assertEqual(response_language("Which rules apply in Tamil Nadu?"), "English")
        self.assertEqual(response_language("Explain English translations of patent documents"), "English")
        self.assertEqual(response_language("Tell me about soda formulations"), "English")

    def test_tanglish_and_native_script(self):
        self.assertEqual(response_language("Traditional knowledge patent panna mudiyuma?"), "Tamil")
        self.assertEqual(response_language("காப்புரிமை என்றால் என்ன?"), "Tamil")
        self.assertEqual(response_language("पेटेंट क्या है?"), "Hindi")

    def test_rewrite_commands_only(self):
        for text in ("Tamil la sollu", "translate it into Hindi", "make it shorter", "தமிழில் சொல்லுங்கள்"):
            self.assertTrue(is_response_transformation(text, True), text)
        for text in ("patent na enna sollu", "GI registration explain pannu", "give an example of ABS exemptions", "Explain Tamil Nadu licensing"):
            self.assertFalse(is_response_transformation(text, True), text)
        self.assertFalse(is_response_transformation("Tamil la sollu", False))

    def test_localized_refusals_need_no_api(self):
        for language in ("Tamil", "Hindi"):
            with patch("rag.chatbot.call_json") as llm, patch("utils.bhashini.translate_many") as translate:
                answer=ask_llm("unavailable information", [], language=language, use_bhashini=True)
                self.assertTrue(is_abstention(answer))
                self.assertIn(messages(language)["disclaimer"],answer)
                self.assertNotIn("Evidence status:",answer)
                llm.assert_not_called()
                translate.assert_not_called()

    def test_localized_classification_uses_normalized_question(self):
        with patch("rag.chatbot.call_json") as llm:
            answer=ask_llm("என் தயாரிப்பை வகைப்படுத்துங்கள்", [], language="Tamil",
                classification_query="Classify my Ayurveda formulation",use_bhashini=True)
            self.assertIn(messages("Tamil")["use"], answer)
            self.assertIn(messages("Tamil")["unassigned"], answer)
            llm.assert_not_called()

    def test_tanglish_query_is_not_skipped(self):
        with patch("rag.chatbot.call_json", return_value={"english":"Can traditional knowledge be patented?"}) as llm:
            query=prepare_query("Traditional knowledge patent panna mudiyuma?",use_bhashini=True)
            self.assertEqual(query,"Can traditional knowledge be patented?")
            llm.assert_called_once()

    def test_malformed_query_translation_stops_retrieval(self):
        with patch("rag.chatbot.call_json", return_value={"english":None}):
            with self.assertRaises(ValueError):
                prepare_query("patent mudiyuma?",use_bhashini=True)

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.doc=Document(page_content="Original source",metadata={"jurisdiction":"india"})
        self.cache={"last_answer":"previous answer","last_question":"Can traditional knowledge be patented?",
                    "retrieval_query":"traditional knowledge patent","language":"Tamil",
                    "documents":[self.doc],"scope":("india","Knowledge base",(),True)}

    def test_language_switch_reuses_same_evidence(self):
        with patch("rag.conversation.retrieve_documents") as retrieve, patch("rag.conversation.ask_llm",return_value="answer") as ask:
            result=respond("English la sollu",use_bhashini=True,cache=self.cache)
            self.assertEqual(result["language"],"English")
            self.assertTrue(result["followup"])
            self.assertEqual(result["cache"]["last_question"],self.cache["last_question"])
            retrieve.assert_not_called()
            self.assertEqual(ask.call_args.args[1],[self.doc])

    def test_new_tanglish_topic_retrieves_fresh_sources(self):
        with patch("rag.conversation.prepare_query",return_value="Who can register a GI?"), patch("rag.conversation.retrieve_documents",return_value=[]) as retrieve, patch("rag.conversation.ask_llm",return_value="answer"):
            result=respond("GI registration pathi sollu",use_bhashini=True,cache=self.cache)
            self.assertFalse(result["followup"])
            retrieve.assert_called_once()
            self.assertEqual(result["cache"]["last_question"],"GI registration pathi sollu")

    def test_sidebar_selection_wins(self):
        with patch("rag.conversation.ask_llm",return_value="answer"):
            result=respond("English la sollu",answer_language="Hindi",use_bhashini=True,cache=self.cache)
            self.assertEqual(result["language"],"Hindi")

    def test_shorter_preserves_previous_language(self):
        with patch("rag.conversation.ask_llm",return_value="answer"):
            result=respond("shorter please",use_bhashini=True,cache=self.cache)
            self.assertEqual(result["language"],"Tamil")
            self.assertTrue(result["followup"])

    def test_reopened_chat_recovers_question_and_retrieves_again(self):
        history=[{"role":"user","content":"Can traditional knowledge be patented?"},
                 {"role":"assistant","content":"prior answer","language":"Tamil"}]
        with patch("rag.conversation.prepare_query",return_value="traditional knowledge patent"), patch("rag.conversation.retrieve_documents",return_value=[self.doc]) as retrieve, patch("rag.conversation.ask_llm",return_value="answer"):
            result=respond("English la sollu",history=history,use_bhashini=True,cache={})
            self.assertTrue(result["followup"])
            self.assertEqual(result["language"],"English")
            self.assertEqual(result["cache"]["last_question"],history[0]["content"])
            retrieve.assert_called_once()

    def test_jurisdiction_change_does_not_reuse_cache(self):
        with patch("rag.conversation.prepare_query",return_value="patent"), patch("rag.conversation.retrieve_documents",return_value=[]) as retrieve, patch("rag.conversation.ask_llm",return_value="answer"):
            result=respond("Tamil la sollu",jurisdiction="international",use_bhashini=True,cache=self.cache)
            self.assertFalse(result["followup"])
            retrieve.assert_called_once()

if __name__ == "__main__":
    unittest.main()
