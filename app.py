import streamlit as st
import os
from utils import DatabaseManager, parse_filename
from utils.ui import (
    render_discovery, render_library, render_analytics,
    render_practice_room, render_sidebar, apply_global_styles
)

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Guitar Shed",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_database():
    """Get singleton database instance (cached across reruns)."""
    return DatabaseManager()


db = get_database()

# Apply global styles from centralized module
apply_global_styles()

def _init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'folder_path': '',
        'selected_lesson_id': None,
        'db_synced': False,
        'metronome_bpm': 120,
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


_init_session_state()


def sync_db():
    """Sync database with folder and invalidate caches."""
    if st.session_state.folder_path and os.path.isdir(st.session_state.folder_path):
        stats = db.sync_folder(st.session_state.folder_path, parse_filename)
        db.invalidate_cache()
        st.session_state.db_synced = True
        return stats
    return None


def main():
    """Main application entry point."""
    render_sidebar(db, sync_db)

    # If a lesson is selected, render the practice room exclusively
    if st.session_state.get('selected_lesson_id'):
        render_practice_room(db)
        return

    # Main dashboard with tabs
    tab_discovery, tab_library, tab_analytics = st.tabs(["DISCOVERY", "LIBRARY", "ANALYTICS"])

    with tab_discovery:
        render_discovery(db)

    with tab_library:
        render_library(db)

    with tab_analytics:
        render_analytics(db)


if __name__ == "__main__":
    main()