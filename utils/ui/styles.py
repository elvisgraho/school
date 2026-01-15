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
            /* Clickable lesson card */
            .lesson-card {
                background: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 12px 16px;
                margin-bottom: 8px;
                cursor: pointer;
                transition: all 0.15s ease;
                text-decoration: none !important;
            }
            .lesson-card:hover {
                background: #3D3D3D;
                border-color: #4D4D4D;
            }
            .lesson-title {
                font-size: 1rem;
                font-weight: 600;
                color: #E0E0E0;
                margin: 0;
            }
            .lesson-author {
                font-size: 0.85rem;
                color: #A0A0A0;
                margin: 4px 0 0 0;
            }
            /* Tight spacing for lesson author */
            .lesson-author-inline {
                font-size: 0.85rem;
                color: #888;
                margin-top: -8px;
                display: block;
            }
            /* Remove internal scrollbar from dataframe and expand to full height */
            [data-testid="stDataFrame"] {
                max-height: none !important;
                height: auto !important;
            }
            [data-testid="stDataFrame"] .stDataFrameResizable {
                max-height: none !important;
                overflow: visible !important;
            }
        </style>
    """, unsafe_allow_html=True)
