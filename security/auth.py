"""Local account/session store. Public UI never supplies an owner ID."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

class AuthenticationError(PermissionError): pass
class RateLimitError(AuthenticationError): pass
class ConflictError(RuntimeError): pass

_KDF_SLOTS = threading.BoundedSemaphore(2)

IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 12 * 60 * 60


def password_hash(password, salt):
    if not isinstance(password, str) or not 15 <= len(password) <= 128:
        raise ValueError('Use a password or passphrase containing 15 to 128 characters.')
    if not _KDF_SLOTS.acquire(timeout=3):raise RateLimitError('Sign-in is busy. Please retry shortly.')
    try:return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=2**17, r=8, p=1, maxmem=256*1024*1024, dklen=32)
    finally:_KDF_SLOTS.release()


def username_key(value):
    name=value.strip().lower() if isinstance(value,str) else ''
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{2,31}',name):
        raise ValueError('Username must be 3 to 32 letters, numbers, dots, dashes or underscores.')
    return name


class AuthStore:
    def __init__(self, root):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path=self.root/'accounts.sqlite3'
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, digest BLOB NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, created REAL NOT NULL, touched REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS throttle(bucket TEXT PRIMARY KEY, started REAL NOT NULL, count INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, revision INTEGER NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS conversations_owner ON conversations(owner);
            CREATE INDEX IF NOT EXISTS sessions_owner ON sessions(owner);
            ''')
        try:self.path.chmod(0o600)
        except OSError:pass

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=15)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback();raise
        finally:db.close()

    def limit(self, bucket, maximum, window=900):
        # Atomic reservation also counts attempts that fail after this point.
        key=hashlib.sha256(bucket.encode()).hexdigest();now=time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM throttle WHERE started < ?', (now-86400,))
            row=db.execute('SELECT * FROM throttle WHERE bucket=?',(key,)).fetchone()
            if row and now-row['started']<window:
                if row['count']>=maximum:raise RateLimitError('Too many attempts. Please try again later.')
                db.execute('UPDATE throttle SET count=count+1 WHERE bucket=?',(key,))
            else:db.execute('INSERT OR REPLACE INTO throttle VALUES(?,?,1)',(key,now))

    def register(self, username, password, client='unknown'):
        self.limit('register:'+client,5,3600)
        name=username_key(username);salt=secrets.token_bytes(16)
        digest=password_hash(password,salt);owner=uuid.uuid4().hex
        try:
            with self.db() as db:db.execute('INSERT INTO accounts VALUES(?,?,?,?,?)',(owner,name,salt,digest,time.time()))
        except sqlite3.IntegrityError:
            raise ValueError('Registration could not be completed. Choose another username.') from None
        return owner

    def login(self, username, password, client='unknown'):
        name=username_key(username)
        self.limit('login-client:'+client,30)
        self.limit('login-account:'+name,10)
        with self.db() as db:row=db.execute('SELECT * FROM accounts WHERE username=?',(name,)).fetchone()
        # Unknown accounts take the same KDF path; no fast existence oracle.
        salt=row['salt'] if row else b'\x00'*16
        try:actual=password_hash(password,salt)
        except ValueError:
            password_hash('invalid-length-password-placeholder',salt)
            raise AuthenticationError('Invalid username or password.') from None
        expected=row['digest'] if row else b'\x00'*32
        if not hmac.compare_digest(actual,expected) or row is None:
            raise AuthenticationError('Invalid username or password.')
        token=secrets.token_urlsafe(32);now=time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=db.execute('SELECT digest FROM accounts WHERE id=?',(row['id'],)).fetchone()
            if not latest or not hmac.compare_digest(latest['digest'],expected):raise AuthenticationError('Credentials changed. Sign in again.')
            db.execute('DELETE FROM sessions WHERE created<? OR touched<?',(now-ABSOLUTE_SECONDS,now-IDLE_SECONDS))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(self.token_digest(token),row['id'],now,now))
        return token

    @staticmethod
    def token_digest(token):
        if not isinstance(token,str) or not 32<=len(token)<=128:raise AuthenticationError('Please sign in.')
        return hashlib.sha256(token.encode()).hexdigest()

    def session(self, token):
        key=self.token_digest(token);now=time.time()
        with self.db() as db:
            row=db.execute('SELECT s.*,a.username FROM sessions s JOIN accounts a ON a.id=s.owner WHERE s.digest=?',(key,)).fetchone()
            if not row or now-row['created']>=ABSOLUTE_SECONDS or now-row['touched']>=IDLE_SECONDS:
                raise AuthenticationError('Your session expired. Please sign in again.')
            db.execute('UPDATE sessions SET touched=? WHERE digest=?',(now,key))
        return {'id':row['owner'],'username':row['username']}

    def logout(self, token, all_sessions=False):
        if all_sessions:
            owner=self.session(token)['id']
            with self.db() as db:db.execute('DELETE FROM sessions WHERE owner=?',(owner,))
        else:
            with self.db() as db:db.execute('DELETE FROM sessions WHERE digest=?',(self.token_digest(token),))

    def change_password(self, token, current, new):
        owner=self.session(token)['id']
        self.limit('change-password:'+owner,5)
        with self.db() as db:row=db.execute('SELECT * FROM accounts WHERE id=?',(owner,)).fetchone()
        try:valid=hmac.compare_digest(password_hash(current,row['salt']),row['digest'])
        except ValueError:valid=False
        if not valid:raise AuthenticationError('Current password is incorrect.')
        salt=secrets.token_bytes(16);digest=password_hash(new,salt)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=db.execute('SELECT digest FROM accounts WHERE id=?',(owner,)).fetchone()
            if not latest or not hmac.compare_digest(latest['digest'],row['digest']):raise AuthenticationError('Credentials changed. Sign in again.')
            db.execute('UPDATE accounts SET salt=?,digest=? WHERE id=?',(salt,digest,owner))
            db.execute('DELETE FROM sessions WHERE owner=?',(owner,))
