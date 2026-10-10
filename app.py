"""Streamlit entry point with a same-origin, disk-backed video route.

Run with: streamlit run app.py
"""
from pathlib import Path
import streamlit as st
from utils.video_server import video_routes

app = st.App(Path(__file__).with_name('ui_app.py'), routes=video_routes())
