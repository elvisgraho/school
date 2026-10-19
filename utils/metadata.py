"""Shared lesson metadata rules for existing libraries and new imports."""

from collections import Counter
import re


EMAIL_PREFIX = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+?(?:\s+[-–—]\s*|\s*$)')
LI_SA_X_PREFIX = re.compile(r'^Sa(?:\s+|\s*-\s*)X\s*[-–—]\s*', re.IGNORECASE)


def clean_author(author, title=None):
    author = (author or '').strip() or 'Unknown author'
    if author.casefold() in ('lisax', 'li-sa-x') or (
            author.casefold() == 'li' and LI_SA_X_PREFIX.match((title or '').strip())):
        return 'Li-Sa-X'
    return author


def canonical_authors(authors):
    """Keep the most common spelling, using the first spelling to break ties."""
    groups = {}
    for author in authors:
        name = clean_author(author)
        groups.setdefault(name.casefold(), Counter())[name] += 1
    return {key: counts.most_common(1)[0][0] for key, counts in groups.items()}


def clean_title(title, author, lesson_date):
    """Remove email prefixes and give unnamed lessons a useful display title."""
    title = (title or '').strip()
    while EMAIL_PREFIX.match(title):
        title = EMAIL_PREFIX.sub('', title, count=1).strip()
    if clean_author(author, title) == 'Li-Sa-X':
        title = LI_SA_X_PREFIX.sub('', title, count=1).strip()
    if not title.strip(' \t\r\n-–—\u200b\ufeff'):
        return f'Lesson by {clean_author(author)} ({lesson_date})'
    return title
