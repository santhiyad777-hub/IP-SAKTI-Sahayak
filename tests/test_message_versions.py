import copy
import unittest
from unittest.mock import patch
from utils.message_versions import migrate_conversation, version_for, select_message_language, reference_signature
from utils.ui_language import translate_answer, translate_texts
from utils.bhashini import BhashiniError
from utils.language import messages

class MessageVersionTests(unittest.TestCase):
    def setUp(self):
        self.answer="**India**\n\n- Section 3(p) excludes traditional knowledge. [1]\n\n**Sources**\n\n[1] [Patents Act](https://example.test/act.pdf#page=12) | PDF page: 12"
        self.chat={"id":"c1","messages":[{"role":"user","content":"What is excluded?"}]+[
            {"role":"assistant","content":self.answer,"language":"English",
             "retrieved_context":[{"page_content":"Original context","metadata":{"page":11}}],
             "sources":["source one"]} for _ in range(3)]}
        migrate_conversation(self.chat)

    def test_existing_message_metadata_is_migrated_once(self):
        before=copy.deepcopy(self.chat)
        migrate_conversation(self.chat)
        self.assertEqual(before,self.chat)
        self.assertEqual(self.chat["messages"][1]["original_question"],"What is excluded?")

    def test_repeated_switch_uses_original_and_same_context(self):
        selected=self.chat["messages"][2]
        others=copy.deepcopy([self.chat["messages"][1],self.chat["messages"][3]])
        versions={"Tamil":self.answer.replace("excludes traditional knowledge","பாரம்பரிய அறிவை விலக்குகிறது"),
                  "Hindi":self.answer.replace("excludes traditional knowledge","पारंपरिक ज्ञान को बाहर रखती है")}
        with patch("utils.message_versions.translate_answer",side_effect=lambda original,target,*args: versions[target]) as translate, patch("rag.chatbot.call_json",return_value={"equivalent":True}) as audit, patch("rag.retriever.retrieve_documents",side_effect=AssertionError("Must not retrieve")):
            for language in ("Tamil","Hindi","English"):
                select_message_language(self.chat,selected["message_id"],language)
            self.assertEqual(translate.call_count,2)
            self.assertTrue(all(call.args[0]==self.answer for call in translate.call_args_list))
            self.assertEqual(audit.call_args.args[1]["retrieved_context"],selected["retrieved_context"])
        self.assertEqual(selected["original_answer"],self.answer)
        self.assertEqual(others,[self.chat["messages"][1],self.chat["messages"][3]])

    def test_changed_reference_rejected_and_original_retained(self):
        selected=self.chat["messages"][1]
        with patch("utils.message_versions.translate_answer",return_value=self.answer.replace("page=12","page=13")):
            with self.assertRaises(BhashiniError): version_for(selected,"Tamil")
        self.assertNotIn("Tamil",selected["translated_versions"])
        self.assertEqual(selected["original_answer"],self.answer)

    def test_meaning_change_is_rejected(self):
        with patch("utils.message_versions.translate_answer",return_value=self.answer), patch("rag.chatbot.call_json",return_value={"equivalent":False}):
            with self.assertRaises(BhashiniError): version_for(self.chat["messages"][1],"Tamil")

    def test_fixed_refusal_translation_is_offline(self):
        text="**India**\n\n"+messages("English")["abstain"]+"\n\n"+messages("English")["disclaimer"]
        with patch("utils.ui_language.translate_texts",side_effect=AssertionError("No API needed")):
            translated=translate_answer(text,"Tamil")
        self.assertIn(messages("Tamil")["abstain"],translated)

    def test_bhashini_failure_falls_back_with_protected_terms(self):
        def fallback(system,payload):
            return {"translations":[text.replace("excludes","விலக்குகிறது") for text in payload["texts"]]}
        with patch("utils.bhashini.translate_many",side_effect=BhashiniError("offline")), patch("rag.chatbot.call_json",side_effect=fallback):
            result=translate_texts(["Section 3(p) excludes TKDL material."],"English","Tamil")
        self.assertIn("Section 3(p)",result[0])
        self.assertIn("TKDL",result[0])

if __name__=="__main__": unittest.main()
