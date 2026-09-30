"""Private exports stay in the authenticated page, never in public media URLs."""
import base64
from html import escape
from pathlib import PurePath
import streamlit as st

def private_download(label, data, file_name='download.txt', mime='text/plain', **kwargs):
    allowed={'text/plain','text/markdown','application/json','application/x-ndjson','application/pdf'}
    if mime not in allowed:raise ValueError('Unsupported download type.')
    if isinstance(data,str):data=data.encode('utf-8')
    if not isinstance(data,bytes):raise TypeError('Expected export bytes or text.')
    name=PurePath(file_name.replace('\\','/')).name.replace('\n','').replace('\r','')[:180]
    encoded=base64.b64encode(data).decode('ascii')
    st.markdown(f'<a class="private-download" download="{escape(name,quote=True)}" href="data:{mime};base64,{encoded}">{escape(label)}</a>',unsafe_allow_html=True)
