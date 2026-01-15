"""
CSS styling modules for Guitar Shed.
Conservative, precise, text-first aesthetic.
"""

import streamlit as st


def apply_conservative_style():
    """Applies minimal, clean styling adjustments."""
    st.markdown("""
        <style>
            /* Tighten spacing for a precise look */
            .block-container { padding-top: 2rem; padding-bottom: 3rem; }
            h1, h2, h3 { font-family: 'Helvetica', 'Arial', sans-serif; font-weight: 600; letter-spacing: -0.5px; }
            .stButton button { border-radius: 4px; font-weight: 500; }
            hr { margin-top: 1rem; margin-bottom: 1rem; border-color: #eee; }
            .section-label { 
                font-size: 0.9rem; 
                text-transform: uppercase; 
                letter-spacing: 1px; 
                color: #888; 
                margin-bottom: 0.5rem; 
                font-weight: 600;
            }
            /* Tight spacing for lesson author */
            .lesson-author {
                font-size: 0.85rem;
                color: #888;
                margin-top: -8px;
                display: block;
            }
        </style>
    """, unsafe_allow_html=True)
