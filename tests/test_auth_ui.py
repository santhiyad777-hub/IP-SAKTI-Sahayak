"""Authentication UI checks; no model calls and no production account data."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
import config
from security.auth import AuthStore
from security.workspace import Workspace

class AuthUITests(unittest.TestCase):
    def test_gate_logout_and_second_account(self):
        app_path=config.BASE_DIR/'app.py'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=AuthStore(root/'private_data')
            tokens=[]
            for user in ('alice','bob'):
                store.register(user,'a long test password here',user)
                token=store.login(user,'a long test password here',user);tokens.append(token)
                Workspace(store,token).save_chat({'id':user+'-chat','title':user+' private title','messages':[],'bookmarks':[]})
            with patch('config.BASE_DIR',root):
                app=AppTest.from_file(str(app_path),default_timeout=30).run()
                self.assertFalse(app.exception);self.assertEqual(len(app.chat_input),0)
                app.text_input(key='login_username').set_value('alice')
                app.text_input(key='login_password').set_value('a long test password here')
                next(b for b in app.button if b.label=='Sign in').click().run()
                self.assertFalse(app.exception);self.assertEqual(len(app.chat_input),1)
                self.assertIn('alice private title',[b.label for b in app.button]);self.assertNotIn('bob private title',[b.label for b in app.button])
                app.session_state['smart_cache']={'private':'ALICE ONLY'}
                app.button(key='account_logout').click().run()
                self.assertFalse(app.exception);self.assertEqual(len(app.chat_input),0)
                self.assertNotIn('smart_cache',app.session_state)
                app.text_input(key='login_username').set_value('bob')
                app.text_input(key='login_password').set_value('a long test password here')
                next(b for b in app.button if b.label=='Sign in').click().run()
                self.assertFalse(app.exception)
                self.assertIn('bob private title',[b.label for b in app.button]);self.assertNotIn('alice private title',[b.label for b in app.button])
                self.assertEqual(app.session_state['smart_cache'],{})
    def test_production_without_https_fails_closed(self):
        with patch.dict('os.environ',{'APP_ENV':'production','PUBLIC_BASE_URL':'http://insecure.example'}):
            app=AppTest.from_file(str(config.BASE_DIR/'app.py'),default_timeout=30).run()
            self.assertEqual(len(app.chat_input),0);self.assertTrue(app.error)

if __name__=='__main__':unittest.main()
