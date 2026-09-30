"""Trusted-operator account recovery; requires separate ownership verification."""
import argparse
import getpass
import os
import secrets
from pathlib import Path
from security.auth import AuthStore,password_hash,username_key

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('revoke-all')
    reset=sub.add_parser('reset-password');reset.add_argument('username')
    args=parser.parse_args()
    root=Path(os.getenv('APP_DATA_DIR',str(Path(__file__).resolve().parents[1]/'private_data')))
    store=AuthStore(root)
    if args.action=='revoke-all':
        with store.db() as db:db.execute('DELETE FROM sessions')
        print('All sessions revoked.');return
    name=username_key(args.username)
    with store.db() as db:row=db.execute('SELECT id FROM accounts WHERE username=?',(name,)).fetchone()
    if not row:raise SystemExit('Account not found.')
    print('Proceed only after independently verifying ownership of this account.')
    password=getpass.getpass('New passphrase: ')
    if password!=getpass.getpass('Confirm passphrase: '):raise SystemExit('Passwords do not match.')
    salt=secrets.token_bytes(16);digest=password_hash(password,salt)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE accounts SET salt=?,digest=? WHERE id=?',(salt,digest,row['id']))
        db.execute('DELETE FROM sessions WHERE owner=?',(row['id'],))
    print('Password replaced; all sessions for this account revoked.')
if __name__=='__main__':main()
