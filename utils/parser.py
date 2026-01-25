"""
Filename parsing utilities for Video School.
Handles extraction of Author, Title, and Date from video filenames.
"""

import re
import hashlib
from typing import Optional, Dict, Any


# Primary pattern: Author - Title DD-MM-YYYY.mp4
FILENAME_PATTERN = re.compile(
    r'^(.+?)\s*-\s*(.+?)\s*(\d{2}-\d{2}-\d{4})\.mp4$',
    re.IGNORECASE
)

# Fallback for files without separator: Author DD-MM-YYYY.mp4
FILENAME_NO_SEPARATOR_PATTERN = re.compile(
    r'^(\S+)\s+(\d{2}-\d{2}-\d{4})\.mp4$',
    re.IGNORECASE
)


def parse_filename(filename: str) -> Optional[Dict[str, Any]]:
    """
    Parse a video lesson filename into its components.
    
    Handles multiple formats:
    - "Author - Title DD-MM-YYYY.mp4" (standard)
    - "Author DD-MM-YYYY.mp4" (no title/separator)
    - Titles with parentheses, dashes, etc.
    
    Args:
        filename: The filename to parse
    
    Returns:
        Dictionary with keys: author, title, lesson_date, unique_hash, or None if parsing fails.
    """
    clean_filename = filename.strip()
    
    # Try primary pattern first: Author - Title DD-MM-YYYY.mp4
    match = FILENAME_PATTERN.match(clean_filename)
    if match:
        author = match.group(1).strip()
        title = match.group(2).strip()
        date_str = match.group(3)
        
        from datetime import datetime
        try:
            lesson_date = datetime.strptime(date_str, '%d-%m-%Y').date()
        except ValueError:
            return None
        
        unique_hash = generate_unique_hash(author, title)
        
        return {
            'author': author,
            'title': title,
            'lesson_date': lesson_date,
            'unique_hash': unique_hash,
            'filename': filename
        }
    
    # Try fallback: Author DD-MM-YYYY.mp4 (no title)
    match = FILENAME_NO_SEPARATOR_PATTERN.match(clean_filename)
    if match:
        author = match.group(1).strip()
        date_str = match.group(2)
        
        from datetime import datetime
        try:
            lesson_date = datetime.strptime(date_str, '%d-%m-%Y').date()
        except ValueError:
            return None
        
        # Use just author as title for these cases
        title = author
        unique_hash = generate_unique_hash(author, title)
        
        return {
            'author': author,
            'title': title,
            'lesson_date': lesson_date,
            'unique_hash': unique_hash,
            'filename': filename
        }
    
    return None


def generate_unique_hash(author: str, title: str) -> str:
    """Generate a unique hash for an author-title combination."""
    hash_input = f"{author.lower()}|{title.lower()}"
    return hashlib.md5(hash_input.encode()).hexdigest()
