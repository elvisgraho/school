"""
CSS styling modules for Video School.
Conservative, precise, text-first aesthetic.
"""

import streamlit as st

# Global app styles - applied once in app.py
GLOBAL_STYLES = """
<style>
    /* Hide Streamlit branding */
    #MainMenu, footer, header {visibility: hidden !important;}

    /* Main container */
    .block-container {padding-top: 2rem; max-width: 98%;}

    /* Sidebar */
    [data-testid="stSidebar"] {background-color: #1a1a1a; border-right: 1px solid #333;}
    [data-testid="stSidebarCollapseButton"] {display: none !important;}

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {gap: 0.5rem; border-bottom: 1px solid #333; padding: 0 1rem;}
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        padding: 0 1.5rem;
        background-color: transparent;
        border: none;
        border-radius: 0;
        font-size: 0.9rem;
        font-weight: 500;
        color: #888;
        transition: all 0.2s;
    }
    .stTabs [data-baseweb="tab"]:hover {color: #ccc; background-color: #2a2a2a;}
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #fff !important;
        border-bottom: 2px solid #3A4A5C !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="false"] {opacity: 0.6;}

    /* Metrics */
    [data-testid="stMetricValue"] {font-size: 1.25rem !important; color: #fff;}
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        text-transform: uppercase;
        color: #888;
        letter-spacing: 1px;
    }

    /* Typography */
    h1, h2, h3 {font-weight: 600; color: #eee; font-family: 'Helvetica', sans-serif;}

    /* Button base styling */
    .stButton > button {
        background-color: #222;
        border: 1px solid #444;
        color: #ccc;
        border-radius: 4px;
        transition: all 0.2s;
        font-weight: 500;
    }
    .stButton > button:hover {
        background-color: #333;
        border-color: #666;
        color: #fff;
    }

    /* DataFrames */
    [data-testid="stDataFrame"] {border: 1px solid #333;}
</style>
"""


def apply_global_styles():
    """Apply global app styles - call once in app.py."""
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


def apply_conservative_style():
    """Applies minimal, clean styling adjustments for content areas."""
    st.markdown("""
        <style>
            /* Tighten spacing */
            .block-container { padding-bottom: 3rem; }
            hr { margin-top: 1rem; margin-bottom: 1rem; border-color: #333; }

            /* Section labels */
            .section-label {
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #888;
                margin-bottom: 0.5rem;
                font-weight: 600;
            }

            /* Lesson cards (used in discovery) */
            .lesson-card {
                background: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 12px 16px;
                margin-bottom: 8px;
                cursor: pointer;
                transition: all 0.15s ease;
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

            /* Remove internal scrollbar from dataframe */
            [data-testid="stDataFrame"] {
                max-height: none !important;
                height: auto !important;
            }
            [data-testid="stDataFrame"] .stDataFrameResizable {
                max-height: none !important;
                overflow: visible !important;
            }
                
            details[title="Click to view actions"] {
                display: none;
            }

            /* Fix Altair chart clipping in columns */
            [data-testid="stColumn"],
            [data-testid="stHorizontalBlock"],
            [data-testid="stVerticalBlock"],
            [data-testid="stElementContainer"],
            [data-testid="stVegaLiteChart"],
            .stColumn,
            .stHorizontalBlock,
            .stVerticalBlock {
                overflow: visible !important;
            }
            [data-testid="stFullScreenFrame"] {
                overflow: visible !important;
                align-items: center;
                display: flex;
            }
            
            [data-testid="stFullScreenFrame"] svg {
                overflow: visible !important;
            }

            /* Progress ring and streak display */
            .streak-container {
                background: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 16px;
            }

            .milestone-badge {
                background: #3D4A3D;
                border-radius: 4px;
                padding: 8px 12px;
                color: #48BB78;
                font-size: 0.85rem;
                margin-top: 12px;
            }

            .recovery-badge {
                background: #4A3D3D;
                border-radius: 4px;
                padding: 8px 12px;
                color: #F6AD55;
                font-size: 0.85rem;
                margin-top: 12px;
            }

            /* Personal records cards */
            .record-card {
                background: #2D2D2D;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
                padding: 16px;
                text-align: center;
            }

            .record-value {
                font-size: 1.5rem;
                font-weight: 700;
                color: #fff;
            }

            .record-label {
                font-size: 0.8rem;
                color: #888;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-top: 4px;
            }

            /* Trend indicators */
            .trend-up {
                color: #48BB78;
            }

            .trend-down {
                color: #F56565;
            }

            /* Heatmap color legend */
            .heatmap-legend {
                display: flex;
                gap: 16px;
                justify-content: center;
                margin-top: 8px;
                font-size: 0.75rem;
                color: #888;
            }

            .heatmap-legend-item {
                display: inline-block;
                width: 12px;
                height: 12px;
                margin-right: 4px;
                vertical-align: middle;
            }
        </style>
    """, unsafe_allow_html=True)
