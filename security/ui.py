"""Authentication gate runs before any private content is loaded or rendered."""
import os
from pathlib import Path
import streamlit as st
from security.auth import AuthStore, AuthenticationError
from security.workspace import Workspace


def clear_session():
    for key in list(st.session_state.keys()):del st.session_state[key]


def require_login(project_root):
    if os.getenv('APP_ENV','development')=='production' and not os.getenv('PUBLIC_BASE_URL','').startswith('https://'):
        st.error('Deployment requires PUBLIC_BASE_URL with HTTPS. Contact the operator.');st.stop()
    root=Path(os.getenv('APP_DATA_DIR',str(Path(project_root)/'private_data')))
    store=AuthStore(root)
    token=st.session_state.get('auth_token')
    if token:
        try:
            user=store.session(token)
            if st.session_state.get('auth_owner') not in (None,user['id']):
                clear_session();st.rerun()
            st.session_state.auth_owner=user['id']
            return Workspace(store,token)
        except AuthenticationError:
            clear_session()
            st.info('Session expired. Please sign in again.')
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"] {max-width:760px;padding-top:3rem;}
    [data-testid="stForm"] {border-radius:16px;border-color:#c9dace;padding:1.4rem;}
    [data-testid="stHeader"] {background:transparent;}
    </style>""",unsafe_allow_html=True)
    st.title('IP-SAKTI Sahayak')
    st.write('Your private Ayurveda IP knowledge workspace')
    st.caption('Sign in to access your own conversations, documents and product briefs.')
    try:client=st.context.ip_address or 'unknown'
    except Exception:client='unknown'
    if not isinstance(client,str):client='unknown'
    login,register=st.tabs(['Sign in','Create account'])
    with login:
        with st.form('login_form',clear_on_submit=True):
            name=st.text_input('Username',max_chars=32,key='login_username')
            password=st.text_input('Password',type='password',max_chars=128,key='login_password')
            submitted=st.form_submit_button('Sign in',type='primary',width='stretch')
        if submitted:
            try:
                token=store.login(name,password,client)
                clear_session();st.session_state.auth_token=token;st.rerun()
            except (AuthenticationError,ValueError) as exc:st.error(str(exc))
    with register:
        with st.form('register_form',clear_on_submit=True):
            name=st.text_input('Choose a username',max_chars=32,key='register_username')
            password=st.text_input('Choose a password',type='password',max_chars=128,key='register_password')
            confirm=st.text_input('Confirm password',type='password',max_chars=128,key='register_confirm')
            st.caption('Use a unique passphrase of 15 to 128 characters. No email address is required.')
            agreed=st.checkbox('I understand that questions and relevant document excerpts are sent to the configured AI/translation providers. My workspace is stored on this service.')
            submitted=st.form_submit_button('Create account',width='stretch')
        if submitted:
            try:
                if not agreed:raise ValueError('Please acknowledge the data-processing notice.')
                if password!=confirm:raise ValueError('Passwords do not match.')
                store.register(name,password,client)
                st.success('Account created. Use the Sign in tab to continue.')
            except (AuthenticationError,ValueError) as exc:st.error(str(exc))
    st.caption('Refreshing the browser may require signing in again. Forgotten-password recovery is not available through this interface; contact the deployment operator.')
    st.stop()


def account_controls(workspace):
    user=workspace.store.session(workspace.token)
    st.caption('Signed in as '+user['username'])
    if st.button('Sign out',key='account_logout',width='stretch'):
        workspace.store.logout(workspace.token)
        clear_session();st.rerun()
    with st.expander('Account security'):
        if st.button('Sign out all sessions',key='logout_all'):
            workspace.store.logout(workspace.token,all_sessions=True)
            clear_session();st.rerun()
        with st.form('change_password',clear_on_submit=True):
            current=st.text_input('Current password',type='password',max_chars=128)
            new=st.text_input('New password',type='password',max_chars=128)
            confirm=st.text_input('Confirm new password',type='password',max_chars=128)
            change=st.form_submit_button('Change password')
        if change:
            try:
                if new!=confirm:raise ValueError('Passwords do not match.')
                workspace.store.change_password(workspace.token,current,new)
                clear_session();st.rerun()
            except (AuthenticationError,ValueError) as exc:st.error(str(exc))
