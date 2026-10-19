"""Metadata handling at the filename import boundary."""

import unittest

from utils import parse_filename
from utils.metadata import clean_title


class FilenameTest(unittest.TestCase):
    def test_email_prefix_is_removed_without_changing_title_case(self):
        parsed = parse_filename('McTeacher - remem@gmx.de - My First Riff 10-10-2026.mp4')
        self.assertEqual(parsed['author'], 'McTeacher')
        self.assertEqual(parsed['title'], 'My First Riff')

    def test_empty_or_email_only_titles_receive_a_name(self):
        for title in ('', ' ', '-', 'remem@gmx.de - ', 'remem@gmx.de'):
            with self.subTest(title=title):
                parsed = parse_filename(f'McTeacher - {title} 10-10-2026.mp4')
                self.assertEqual(parsed['title'], 'Lesson by McTeacher (2026-10-10)')

    def test_missing_author_and_multiword_author_have_names(self):
        parsed = parse_filename(' - Riff 10-10-2026.mp4')
        self.assertEqual(parsed['author'], 'Unknown author')
        self.assertEqual(parsed['title'], 'Riff')
        parsed = parse_filename('Anthony Muzio 10-10-2026.mp4')
        self.assertEqual(parsed['author'], 'Anthony Muzio')
        self.assertEqual(parsed['title'], 'Anthony Muzio')

    def test_non_prefix_emails_and_title_punctuation_are_preserved(self):
        self.assertEqual(clean_title('Contact me at person@example.com', 'Teacher', '2026-10-10'),
                         'Contact me at person@example.com')
        self.assertEqual(clean_title('E-mail Rhythm - Part 2', 'Teacher', '2026-10-10'),
                         'E-mail Rhythm - Part 2')

    def test_invalid_dates_and_unparseable_files_still_fail(self):
        self.assertIsNone(parse_filename('Teacher - Riff 31-02-2026.mp4'))
        self.assertIsNone(parse_filename('unparseable.mp4'))


if __name__ == '__main__':
    unittest.main()
