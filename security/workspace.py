"""All private operations derive their owner from a live server-side session."""
import json
import os
import re
import tempfile
from pathlib import Path, PureWindowsPath
from security.auth import AuthenticationError, ConflictError

class Workspace:
    def __init__(self, store, token):
        self.store=store;self.token=token
        self._owner=store.session(token)['id']

    @property
    def owner(self):
        current=self.store.session(self.token)['id']
        if current!=self._owner:raise AuthenticationError('Account changed. Sign in again.')
        return current

    @property
    def root(self):
        owner=self.owner
        if not re.fullmatch('[a-f0-9]{32}',owner):raise AuthenticationError('Invalid account.')
        root=(self.store.root/'users'/owner).resolve()
        if not root.is_relative_to(self.store.root):raise PermissionError('Invalid account directory')
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        return root

    @property
    def uploads(self):
        path=self.root/'uploads';path.mkdir(exist_ok=True,mode=0o700);return path

    @property
    def vectors(self):return self.root/'vectors'

    def upload_path(self, filename):
        if not isinstance(filename,str) or not filename or len(filename)>180 or any(c in filename for c in '/\\:\x00') or filename.startswith('.') or any(ord(c)<32 for c in filename):
            raise ValueError('Invalid filename.')
        if PureWindowsPath(filename).is_reserved() or filename.endswith((' ','.')) or any(c in filename for c in '<>"|?*'):
            raise ValueError('Invalid filename.')
        folder=self.uploads.resolve();path=folder/filename
        if path.is_symlink() or path.resolve().parent!=folder:raise PermissionError('Invalid upload path.')
        return path

    def list_chats(self):
        owner=self.owner
        with self.store.db() as db:rows=db.execute('SELECT payload,revision FROM conversations WHERE owner=? ORDER BY rowid DESC',(owner,)).fetchall()
        result=[]
        for row in rows:
            chat=json.loads(row['payload']);chat['_revision']=row['revision'];result.append(chat)
        return result

    def get_chat(self, chat_id):
        owner=self.owner
        with self.store.db() as db:row=db.execute('SELECT payload,revision FROM conversations WHERE id=? AND owner=?',(chat_id,owner)).fetchone()
        if row is None:raise PermissionError('Conversation unavailable.')
        chat=json.loads(row['payload']);chat['_revision']=row['revision'];return chat

    def save_chat(self, chat):
        owner=self.owner;chat_id=chat.get('id')
        if not isinstance(chat_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',chat_id):raise ValueError('Invalid conversation ID.')
        clean={k:v for k,v in chat.items() if k!='_revision'}
        payload=json.dumps(clean,ensure_ascii=False)
        if len(payload.encode('utf-8'))>20*1024*1024:raise ValueError('Conversation is too large. Start a new chat.')
        with self.store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT owner,revision,payload FROM conversations WHERE id=?',(chat_id,)).fetchone()
            total=db.execute('SELECT COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM conversations WHERE owner=? AND id<>?',(owner,chat_id)).fetchone()[0]
            if total+len(payload.encode('utf-8'))>50*1024*1024:raise ValueError('Account history quota reached. Export and delete old chats.')
            if row:
                if row['owner']!=owner:raise PermissionError('Conversation unavailable.')
                if row['revision']!=chat.get('_revision'):raise ConflictError('Conversation changed in another session. Reload before editing.')
                if row['payload']==payload:return
                revision=row['revision']+1
                db.execute('UPDATE conversations SET payload=?,revision=? WHERE id=? AND owner=?',(payload,revision,chat_id,owner))
            else:
                if chat.get('_revision') is not None:raise ConflictError('Conversation was deleted. Reload the workspace.')
                count=db.execute('SELECT COUNT(*) FROM conversations WHERE owner=?',(owner,)).fetchone()[0]
                if count>=500:raise ValueError('Conversation limit reached. Delete an old chat first.')
                revision=1
                db.execute('INSERT INTO conversations VALUES(?,?,?,?)',(chat_id,owner,revision,payload))
        chat['_revision']=revision

    def delete_chat(self, chat_id):
        owner=self.owner
        with self.store.db() as db:
            result=db.execute('DELETE FROM conversations WHERE id=? AND owner=?',(chat_id,owner))
            if result.rowcount!=1:raise PermissionError('Conversation unavailable.')

    def delete_all_chats(self):
        owner=self.owner
        with self.store.db() as db:db.execute('DELETE FROM conversations WHERE owner=?',(owner,))

    def read_preferences(self):
        root=self.root  # Authentication failures must never be swallowed as an OSError.
        try:return json.loads((root/'preferences.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}

    def save_preferences(self, values):
        root=self.root
        fd,name=tempfile.mkstemp(dir=root,prefix='preferences-',suffix='.tmp')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(values,f)
            os.replace(name,root/'preferences.json')
        finally:
            Path(name).unlink(missing_ok=True)

    def limit_request(self):self.store.limit('chat:'+self.owner,20,60)
