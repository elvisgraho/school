import streamlit as st
import os
import tkinter as tk
from tkinter import filedialog
from utils import DatabaseManager, parse_filename
# Added render_practice_room to imports
from utils.ui import render_discovery, render_library, render_analytics, render_practice_room

# Initialize
db = DatabaseManager()

st.set_page_config(
    page_title="Guitar Shed",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Minimal CSS (Theme Adjusted - Conservative/Precise)
st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .block-container {padding-top: 2rem; max-width: 98%;}
    [data-testid="stSidebar"] {background-color: #1a1a1a; border-right: 1px solid #333;}
    /* Tab Styling - Clean & Spaced */
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
    [data-testid="stDataFrame"] {border: 1px solid #333;}
    [data-testid="stMetricValue"] {font-size: 1.25rem !important; color: #fff;}
    [data-testid="stMetricLabel"] {font-size: 0.75rem !important; text-transform: uppercase; color: #888; letter-spacing: 1px;}
    h1, h2, h3 {font-weight: 600; color: #eee; font-family: 'Helvetica', sans-serif;}
    /* Button Styling */
    .stButton > button {background-color: #222; border: 1px solid #444; color: #ccc; border-radius: 2px; transition: all 0.2s;}
    .stButton > button:hover {background-color: #333; border-color: #666; color: #fff;}
</style>
""", unsafe_allow_html=True)

# Session state
if 'folder_path' not in st.session_state:
    st.session_state.folder_path = ''
if 'selected_lesson_id' not in st.session_state:
    st.session_state.selected_lesson_id = None
if 'db_synced' not in st.session_state:
    st.session_state.db_synced = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'metronome_bpm' not in st.session_state:
    st.session_state.metronome_bpm = 120
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = 'discovery'

def sync_db():
    if st.session_state.folder_path and os.path.isdir(st.session_state.folder_path):
        stats = db.sync_folder(st.session_state.folder_path, parse_filename)
        st.session_state.db_synced = True
        return stats
    return None

def render_sidebar():
    """Render sidebar with settings and metronome."""
    with st.sidebar:
        st.markdown("<h3 style='color:#ccc; margin-top:0;'>GUITAR SHED</h3>", unsafe_allow_html=True)
        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)
        
        # Stats first
        stats = db.get_stats()
        c1, c2 = st.columns(2)
        c1.metric("Total", stats.get('total', 0))
        c2.metric("Done", stats.get('completed', 0))
        c3, c4 = st.columns(2)
        c3.metric("In Progress", stats.get('in_progress', 0))
        c4.metric("To Do", stats.get('total', 0) - stats.get('completed', 0))
        
        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)
        
        # Folder (Tkinter)
        st.markdown("**Library Location**")
        
        col_text, col_btn = st.columns([4, 1])
        with col_text:
            path = st.text_input("Folder", value=st.session_state.folder_path, 
                               placeholder="Select folder...", label_visibility="collapsed", disabled=True)
        with col_btn:
            if st.button("...", help="Select Folder"):
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', 1)
                selected_folder = filedialog.askdirectory(master=root)
                root.destroy()
                if selected_folder:
                    st.session_state.folder_path = selected_folder
                    st.rerun()

        if path != st.session_state.folder_path:
            st.session_state.folder_path = path
            st.session_state.db_synced = False
        
        if st.button("Sync Library", type="secondary", use_container_width=True):
            if st.session_state.folder_path and os.path.isdir(st.session_state.folder_path):
                with st.spinner("Scanning..."):
                    s = sync_db()
                    if s:
                        st.success(f"+{s.get('added', 0)} / Updated: {s.get('updated', 0)}")
            else:
                st.error("Invalid path")
        
        st.markdown("<hr style='margin: 10px 0; opacity: 0.2'>", unsafe_allow_html=True)
        
        # Metronome
        st.subheader("Metronome")
        
        bpm_val = st.session_state.metronome_bpm
        
        # HTML Metronome
        st.components.v1.html(f"""
        <style>
        body {{ background: #1a1a1a; color: #ccc; font-family: sans-serif; margin: 0; padding: 5px; }}
        .met-container {{ border: 1px solid #333; padding: 10px; border-radius: 4px; background: #222; }}
        .top-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
        .bpm-display {{ font-size: 1.8rem; font-weight: bold; color: #fff; }}
        .time-sig-select {{ background: #333; color: #fff; border: 1px solid #444; padding: 2px 5px; }}
        input[type=range] {{ width: 100%; accent-color: #555; background: transparent; }}
        .btn-row {{ display: flex; gap: 5px; margin-top: 10px; }}
        button {{ flex: 1; background: #333; border: 1px solid #444; color: #ddd; padding: 8px; cursor: pointer; }}
        button:hover {{ background: #444; color: #fff; }}
        .active {{ background: #4a4a4a !important; color: #fff; }}
        </style>

        <div class="met-container">
            <div class="top-row">
                <span class="bpm-display" id="bpm">{bpm_val}</span>
                <select class="time-sig-select" id="ts">
                    <option value="4">4/4</option>
                    <option value="3">3/4</option>
                    <option value="2">2/4</option>
                    <option value="6">6/8</option>
                </select>
            </div>
            <input type="range" id="slider" min="40" max="220" value="{bpm_val}">
            <div class="btn-row">
                <button id="tap">TAP</button>
                <button id="start">START</button>
            </div>
        </div>

        <script>
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            let bpm = {bpm_val}, isPlaying = false, timer, nextNote = 0, beat = 0;
            const slider = document.getElementById('slider');
            const disp = document.getElementById('bpm');
            const startBtn = document.getElementById('start');
            const tapBtn = document.getElementById('tap');
            const ts = document.getElementById('ts');
            let taps = [];

            function playSound(time, strong) {{
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain); gain.connect(ctx.destination);
                osc.frequency.value = strong ? 800 : 500;
                gain.gain.setValueAtTime(0.3, time);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.1);
                osc.start(time); osc.stop(time + 0.1);
            }}

            function scheduler() {{
                while (nextNote < ctx.currentTime + 0.1) {{
                    let measure = parseInt(ts.value);
                    playSound(nextNote, beat % measure === 0);
                    nextNote += 60.0 / bpm;
                    beat++;
                }}
                timer = requestAnimationFrame(scheduler);
            }}

            slider.oninput = function() {{ bpm = this.value; disp.innerText = bpm; }};

            startBtn.onclick = function() {{
                isPlaying = !isPlaying;
                if (isPlaying) {{
                    if (ctx.state === 'suspended') ctx.resume();
                    nextNote = ctx.currentTime;
                    beat = 0;
                    scheduler();
                    this.innerText = "STOP";
                    this.classList.add('active');
                }} else {{
                    cancelAnimationFrame(timer);
                    this.innerText = "START";
                    this.classList.remove('active');
                }}
            }};

            tapBtn.onclick = function() {{
                let now = Date.now();
                if (taps.length && now - taps[taps.length-1] > 2000) taps = [];
                taps.push(now);
                if (taps.length > 4) taps.shift();
                if (taps.length > 1) {{
                    let avg = taps.slice(1).map((t,i) => t - taps[i]).reduce((a,b)=>a+b)/ (taps.length-1);
                    bpm = Math.round(60000/avg);
                    if(bpm > 220) bpm = 220; if(bpm < 40) bpm = 40;
                    slider.value = bpm; disp.innerText = bpm;
                }}
            }};
        </script>
        """, height=140)


def main():
    render_sidebar()
    
    # === MAIN LOGIC FIX ===
    # If a lesson is selected, ONLY render the practice room.
    # This prevents the tabs from rendering and resetting the state.
    if st.session_state.get('selected_lesson_id'):
        render_practice_room(db)
        
    else:
        # No video selected -> Show Dashboard
        # Icons removed for conservative design
        t1, t2, t3 = st.tabs(["DISCOVERY", "LIBRARY", "ANALYTICS"])
        
        with t1:
            st.session_state.active_tab = 'discovery'
            render_discovery(db)
        with t2:
            st.session_state.active_tab = 'library'
            render_library(db)
        with t3:
            st.session_state.active_tab = 'analytics'
            render_analytics(db)


if __name__ == "__main__":
    main()