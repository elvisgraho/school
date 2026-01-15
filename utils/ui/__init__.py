"""
UI rendering modules for Guitar Shed.
Redesigned for a conservative, precise, text-first aesthetic.

Submodules:
- styles: CSS styling
- callbacks: Helper callbacks
- practice: Practice room (video player)
- discovery: Discovery tab
- library: Library tab
- analytics: Analytics tab
"""

from .styles import apply_conservative_style
from .callbacks import set_lesson, clear_lesson, update_status_callback
from .practice import render_practice_room
from .discovery import render_discovery
from .library import render_library
from .analytics import render_analytics

__all__ = [
    'apply_conservative_style',
    'set_lesson',
    'clear_lesson',
    'update_status_callback',
    'render_practice_room',
    'render_discovery',
    'render_library',
    'render_analytics',
]
