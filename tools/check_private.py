"""Privacy check for this repository: fails if personal or book-specific material slipped in.

Built-in checks: API keys and private keys, absolute home-directory paths, e-mail addresses, book/image/database files
outside docs/ and examples/. Your own forbidden terms (names, book titles, character names ...) go into a text file
that is NOT part of the repository:

    python tools/check_private.py --terms ../private-terms.txt
"""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', 'build', 'dist'}
SECRET = [r'sk-[A-Za-z0-9_-]{20,}', r'sk-ant-[A-Za-z0-9_-]{20,}', r'AIza[0-9A-Za-z_-]{30,}', r'ghp_[A-Za-z0-9]{30,}',
          r'-----BEGIN [A-Z ]*PRIVATE KEY-----']
PATHS = [r'[A-Za-z]:\\Users\\', r'/Users/[A-Za-z0-9_.-]+/', r'/home/[A-Za-z0-9_.-]+/']
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
EMAIL_OK = {'you@example.com', 'name@example.com', 'noreply@anthropic.com'}
BINARY = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.epub', '.pdf', '.sqlite', '.sqlite3', '.db', '.zip', '.exe'}
BINARY_ALLOWED = ('docs/', 'examples/')
DATA_DIRS = {'atlas-history', 'atlas-images', 'atlas-maps', 'atlas-geo', 'book-cache', 'snapshots', 'recap-cache', 'before-audit', 'before-profile'}


def files(root=ROOT):
    for path in sorted(root.rglob('*')):
        if path.is_file() and not (set(path.relative_to(root).parts) & SKIP_DIRS):
            yield path


def scan(root=ROOT, terms=()):
    problems = []
    for path in files(root):
        rel = path.relative_to(root).as_posix()
        if set(path.relative_to(root).parts[:-1]) & DATA_DIRS:
            problems.append((rel, 'personal data folder'))
            continue
        if path.suffix.lower() in BINARY:
            if not rel.startswith(BINARY_ALLOWED):
                problems.append((rel, 'binary or book/image file outside docs/ and examples/'))
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            problems.append((rel, 'unreadable as text'))
            continue
        if rel == 'tools/check_private.py':
            continue  # contains the patterns themselves
        for pattern in SECRET + PATHS:
            if re.search(pattern, text):
                problems.append((rel, f'matches {pattern}'))
        for mail in EMAIL.findall(text):
            if mail.lower() not in EMAIL_OK:
                problems.append((rel, f'e-mail address {mail}'))
        lowered = text.lower()
        for term in terms:
            if term and term.lower() in lowered:
                problems.append((rel, f'forbidden term "{term}"'))
    return problems


def load_terms(path):
    return [line.strip() for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip() and not line.startswith('#')]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--terms', help='text file with one forbidden term per line (keep it outside the repository)')
    args = parser.parse_args(argv)
    problems = scan(ROOT, load_terms(args.terms) if args.terms else ())
    for rel, why in problems:
        print(f'{rel}: {why}')
    print('Privacy check:', 'FAILED' if problems else 'clean')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
