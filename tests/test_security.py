"""Adversarial account and ownership tests using a temporary real SQLite store."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from security.auth import AuthStore,AuthenticationError,RateLimitError,ConflictError,IDLE_SECONDS,ABSOLUTE_SECONDS
from security.workspace import Workspace
from security.uploads import validate_upload

PASSWORD='a correct long passphrase 123'

class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.store=AuthStore(cls.tmp.name)
        cls.a=cls.store.register('alice',PASSWORD,'a')
        cls.b=cls.store.register('bob',PASSWORD,'b')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        with self.store.db() as db:db.execute('DELETE FROM throttle')
        self.ta=self.store.login('alice',PASSWORD,'a');self.tb=self.store.login('bob',PASSWORD,'b')
        self.wa=Workspace(self.store,self.ta);self.wb=Workspace(self.store,self.tb)
    def tearDown(self):
        with self.store.db() as db:
            db.execute('DELETE FROM conversations');db.execute('DELETE FROM sessions')
    def test_passwords_and_tokens_are_not_stored_in_plaintext(self):
        with self.store.db() as db:
            rows=db.execute('SELECT salt,digest FROM accounts ORDER BY username').fetchall()
            tokens=[r[0] for r in db.execute('SELECT digest FROM sessions')]
        self.assertNotEqual(rows[0]['salt'],rows[1]['salt']);self.assertNotEqual(rows[0]['digest'],rows[1]['digest'])
        self.assertNotIn(self.ta,tokens);self.assertNotIn(PASSWORD.encode(),self.store.path.read_bytes())
    def test_generic_login_failure(self):
        errors=[]
        for user in ('alice','unknown'):
            with self.assertRaises(AuthenticationError) as error:self.store.login(user,'wrong long password','failure')
            errors.append(str(error.exception))
        self.assertEqual(*errors)
    def test_registration_validation(self):
        for username,password in [("a'; DROP TABLE accounts;--",PASSWORD),('valid','short')]:
            with self.assertRaises(ValueError):self.store.register(username,password,'invalid')
    def test_case_normalized_username(self):self.assertEqual(self.store.session(self.store.login(' ALICE ',PASSWORD,'caps'))['id'],self.a)
    def test_rate_limit_is_persistent(self):
        self.store.limit('test',1)
        with self.assertRaises(RateLimitError):AuthStore(self.tmp.name).limit('test',1)
    def test_idle_and_absolute_expiration(self):
        import time
        for column,age in [('touched',IDLE_SECONDS+1),('created',ABSOLUTE_SECONDS+1)]:
            token=self.store.login('alice',PASSWORD,'expiry')
            with self.store.db() as db:db.execute(f'UPDATE sessions SET {column}=? WHERE digest=?',(time.time()-age,self.store.token_digest(token)))
            with self.assertRaises(AuthenticationError):self.store.session(token)
    def test_logout_and_logout_all(self):
        second=self.store.login('alice',PASSWORD,'second')
        self.store.logout(self.ta)
        with self.assertRaises(AuthenticationError):self.wa.list_chats()
        self.assertEqual(self.store.session(second)['id'],self.a)
        self.store.logout(second,all_sessions=True)
        with self.assertRaises(AuthenticationError):self.store.session(second)
        self.assertEqual(self.store.session(self.tb)['id'],self.b)
    def test_password_change_revokes_sessions(self):
        owner=self.store.register('changeuser',PASSWORD,'change')
        first=self.store.login('changeuser',PASSWORD,'change');second=self.store.login('changeuser',PASSWORD,'change')
        new='a different strong passphrase 456'
        self.store.change_password(first,PASSWORD,new)
        for token in (first,second):
            with self.assertRaises(AuthenticationError):self.store.session(token)
        with self.assertRaises(AuthenticationError):self.store.login('changeuser',PASSWORD,'change')
        self.assertEqual(self.store.session(self.store.login('changeuser',new,'change'))['id'],owner)
    def test_other_user_cannot_read_modify_delete_or_claim_chat(self):
        chat={'id':'private-alice-chat','messages':[{'content':'ALICE ONLY'}],'bookmarks':['PRIVATE BOOKMARK'],'product_profile':{'claim':'secret'}}
        self.wa.save_chat(chat)
        self.assertEqual(self.wb.list_chats(),[])
        for operation in (lambda:self.wb.get_chat(chat['id']),lambda:self.wb.save_chat(chat),lambda:self.wb.delete_chat(chat['id'])):
            with self.assertRaises(PermissionError):operation()
        self.wb.delete_all_chats();self.assertEqual(self.wa.get_chat(chat['id'])['messages'],chat['messages'])
    def test_stale_edit_cannot_overwrite_or_resurrect(self):
        chat={'id':'concurrent','messages':[]};self.wa.save_chat(chat)
        stale=self.wa.get_chat('concurrent');chat['messages']=['new'];self.wa.save_chat(chat)
        stale['messages']=['old'];
        with self.assertRaises(ConflictError):self.wa.save_chat(stale)
        self.wa.delete_chat('concurrent')
        with self.assertRaises(ConflictError):self.wa.save_chat(chat)
    def test_upload_paths_and_preferences_are_private(self):
        self.assertNotEqual(self.wa.upload_path('same.txt'),self.wb.upload_path('same.txt'))
        self.wa.save_preferences({'language':'Tamil'});self.wb.save_preferences({'language':'English'})
        self.assertEqual(self.wa.read_preferences()['language'],'Tamil')
        self.assertEqual(self.wb.read_preferences()['language'],'English')
    def test_path_traversal_and_windows_special_names(self):
        for name in ('../bob/file.txt','..\\bob.txt','C:\\secret.txt','/etc/passwd','CON.txt','CONIN$','COM'+chr(185)+'.txt','CON .txt','bad?.txt','.env','x:ads.txt','x.','x\x00.txt'):
            with self.subTest(name=name),self.assertRaises((ValueError,PermissionError)):self.wa.upload_path(name)
    def test_revoked_session_cannot_access_private_files(self):
        self.store.logout(self.ta)
        for operation in (lambda:self.wa.upload_path('a.txt'),lambda:self.wa.save_chat({'id':'test'}),lambda:self.wa.read_preferences()):
            with self.assertRaises(AuthenticationError):operation()
    def test_upload_screening(self):
        for name,content in [('file.exe',b'exe'),('file.pdf',b'fake'),('file.xml',b'<!DOCTYPE x><x/>'),('file.docx',b'fake'),('empty.txt',b'')]:
            with self.subTest(name=name),self.assertRaises(ValueError):validate_upload(self.wa,name,content)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml','x');z.writestr('huge','x'*1000000)
        with self.assertRaises(ValueError):validate_upload(self.wa,'bomb.docx',stream.getvalue())
        self.assertEqual(validate_upload(self.wa,'valid.txt',b'hello').name,'valid.txt')
    def test_legacy_history_is_not_assigned_to_new_accounts(self):
        (self.store.root/'conversations.json').write_text('[{"id":"legacy","secret":"old"}]')
        self.assertEqual(self.wa.list_chats(),[]);self.assertEqual(self.wb.list_chats(),[])

if __name__=='__main__':unittest.main()
