"""Isolated Streamlit UI checks; no real chats, uploads or external API calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import config
from streamlit.testing.v1 import AppTest
from utils.ui_language import tr
from utils.language import messages
from security.auth import AuthStore
from security.workspace import Workspace

APP = config.BASE_DIR / "app.py"

class MultilingualUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="ip_sakti_ui_")
        self.root=Path(self.temp.name)
        (self.root/"knowledge_base").mkdir()
        (self.root/"uploads").mkdir()
        original=tr("Hello! Ask me about Ayurveda intellectual property, product classification, ABS or export requirements.","English")
        chat={"id":"ui-test-chat","title":"New conversation","created_at":"2026-09-19T10:00:00",
              "updated_at":"2026-09-19T10:00:00","document_names":[],"bookmarks":[],
              "messages":[{"role":"assistant","content":original,"language":"English"} for _ in range(3)]}
        store=AuthStore(self.root/"private_data")
        store.register("ui_user","a-long-ui-test-passphrase",client="test")
        self.token=store.login("ui_user","a-long-ui-test-passphrase",client="test")
        self.workspace=Workspace(store,self.token)
        self.workspace.save_chat(chat)
        self.patches=[patch("config.BASE_DIR",self.root),patch("config.UPLOAD_FOLDER",str(self.root/"uploads")),
                      patch("rag.chatbot.call_json",side_effect=AssertionError("Unexpected API call during isolated UI check"))]
        for item in self.patches: item.start()
        self.app=AppTest.from_file(str(APP),default_timeout=30)
        self.app.session_state["auth_token"]=self.token
        self.app.run()
        self.assertEqual(len(self.app.exception),0)

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_empty_upload_library_uses_builtin_sources(self):
        self.assertEqual(self.app.session_state["source_mode"], "Knowledge base")
        self.assertFalse(any(widget.key == "source_mode" for widget in self.app.selectbox))
        self.app = AppTest.from_file(str(APP), default_timeout=30)
        self.app.session_state["auth_token"]=self.token
        self.app.session_state["source_mode"] = "Uploaded documents"
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.session_state["source_mode"], "Knowledge base")
        self.assertFalse(any("Using the built-in" in message.value for message in self.app.caption))

    def test_global_language_changes_controls_and_english_greeting(self):
        self.assertEqual(self.app.selectbox(key="app_language").options,["Auto","English","தமிழ்","हिन्दी"])
        for language in ("Tamil","Hindi","English"):
            self.app.selectbox(key="app_language").set_value(language).run()
            self.assertEqual(len(self.app.exception),0)
            self.assertEqual(self.app.radio(key="jurisdiction").label,tr("Jurisdiction",language))
            self.assertEqual(self.app.chat_input[0].placeholder,tr("Ask about Ayurveda IP, classification, ABS or export requirements...",language))
            self.app.chat_input[0].set_value("hi").run()
            self.assertEqual(len(self.app.exception),0)
            self.assertEqual(self.app.session_state["messages"][-1]["answer_language"],language)
            self.assertIn(tr("Hello! Ask me about Ayurveda intellectual property, product classification, ABS or export requirements.",language),
                          self.app.session_state["messages"][-1]["content"])

    def test_one_message_switches_repeatedly_without_changing_neighbors(self):
        items=self.app.session_state["messages"]
        key=f"ui-test-chat_{items[1]['message_id']}_message_language"
        original=items[1]["original_answer"]
        for language in ("Tamil","Hindi","English"):
            self.app.selectbox(key=key).set_value(language).run()
            self.assertEqual(len(self.app.exception),0)
            items=self.app.session_state["messages"]
            self.assertEqual(items[1]["display_language"],language)
            self.assertEqual(items[1]["original_answer"],original)
            self.assertIsNone(items[0]["display_language"])
            self.assertIsNone(items[2]["display_language"])
        saved=self.workspace.list_chats()
        self.assertEqual(set(saved[0]["messages"][1]["translated_versions"]),{"English","Tamil","Hindi"})
        self.assertEqual(saved[0]["messages"][1]["original_answer"],original)

    def test_auto_follows_native_greeting(self):
        self.app.selectbox(key="app_language").set_value("Auto").run()
        for question,language in [("வணக்கம்","Tamil"),("नमस्ते","Hindi"),("hi","English")]:
            self.app.chat_input[0].set_value(question).run()
            self.assertEqual(len(self.app.exception),0)
            self.assertEqual(self.app.session_state["messages"][-1]["answer_language"],language)

    def test_product_brief_saves_without_model_or_chat_submission(self):
        self.app.text_input(key="profile_ui-test-chat_formula").set_value("Private aloe preparation")
        next(b for b in self.app.button if b.label == "Save brief").click().run()
        self.assertEqual(len(self.app.exception),0)
        saved=self.workspace.list_chats()
        self.assertEqual(saved[0]["product_profile"]["formula"],"Private aloe preparation")
        audit=(self.workspace.root/"knowledge_base/audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("Private aloe",audit)
        self.assertEqual(len(saved[0]["messages"]),3)

    def test_empty_profile_classification_asks_for_details_without_model(self):
        next(b for b in self.app.button if b.label == "Check classification").click().run()
        self.assertEqual(len(self.app.exception),0)
        self.assertIn("intended use",self.app.session_state["messages"][-1]["content"])
        self.assertEqual(self.app.session_state["messages"][-1]["response_kind"],"clarification")

if __name__=="__main__": unittest.main()
