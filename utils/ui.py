"""
UI rendering modules for Guitar Shed.
Redesigned for a conservative, precise, text-first aesthetic.

This module re-exports all UI components for backward compatibility.
For new code, import directly from submodules:
    from utils.ui.styles import apply_conservative_style, apply_global_styles
    from utils.ui.callbacks import set_lesson
    from utils.ui.practice import render_practice_room
    etc.
"""

# Re-export all components for backward compatibility
from utils.ui.styles import apply_conservative_style, apply_global_styles
from utils.ui.callbacks import set_lesson, clear_lesson, update_status_callback
from utils.ui.practice import render_practice_room
from utils.ui.discovery import render_discovery
from utils.ui.library import render_library
from utils.ui.analytics import render_analytics

__all__ = [
    'apply_conservative_style',
    'apply_global_styles',
    'set_lesson',
    'clear_lesson',
    'update_status_callback',
    'render_practice_room',
    'render_discovery',
    'render_library',
    'render_analytics',
]
