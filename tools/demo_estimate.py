"""Estimate the AI work for building an atlas from an EPUB without sending anything.

    python tools/demo_estimate.py book.epub --chapters 5

Counts the story chapters up to chapter N, the characters of text, and the number of requests: one main request and one
audit request per 30,000 characters (configurable with --chunk), plus one optional profile request per state when you
use `reading-atlas enrich`. Token numbers are a rough guide (about 3.5 characters per token for English prose).
"""
import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reading_atlas import epub_chapters  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('epub')
    parser.add_argument('--chapters', type=int, required=True, help='read up to the end of this story chapter')
    parser.add_argument('--chunk', type=int, default=30000)
    args = parser.parse_args(argv)
    book = epub_chapters.load(args.epub)
    chapters = [c for c in book.chapters if c.number <= args.chapters]
    sizes = [sum(map(len, c.paragraphs)) for c in chapters]
    requests = sum(2 * max(1, math.ceil(size / args.chunk)) for size in sizes)
    chars = sum(sizes)
    print(f'{len(book.chapters)} story chapters found; reading up to chapter {len(chapters)}')
    for chapter, size in zip(chapters, sizes):
        print(f'  {chapter.number:>3}  {size // 1000:>4}k characters  {chapter.title[:60]}')
    print(f'Total {chars // 1000}k characters -> about {requests} requests (main + audit pass)')
    print(f'Rough input volume: {int(chars * 2 / 3.5) // 1000}k tokens plus the growing list of known characters; '
          f'output: a few thousand tokens per request.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
