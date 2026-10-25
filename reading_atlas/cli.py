"""Command line: reading-atlas <command>  (or: python -m reading_atlas <command>)."""
import argparse
import json
from pathlib import Path
import sys

from . import books, config as cfg, enrich_profiles, epub_chapters, llm, portraits, progress, states, sync


def cmd_init(args):
    home = cfg.data_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / 'config.json'
    if not path.exists():
        path.write_text(json.dumps(cfg.DEFAULTS, indent=2), encoding='utf-8')
    print(f'Data home: {home}\nSettings:  {path}\nNext: set "language" and "nominatim_contact" there, choose an AI provider '
          '(see README), connect the device and run "reading-atlas add-book --device <drive>".')


def cmd_doctor(args):
    settings = cfg.load()
    print('Data home:', cfg.data_home())
    print('Language :', settings['language'])
    try:
        provider = llm.load_provider()
        print('Provider :', provider['provider'], provider.get('model', ''))
    except Exception as error:
        print('Provider : not ready:', error)
    print('Codex CLI:', llm.find_codex() or 'not found')
    print('Nominatim contact:', 'set' if settings['nominatim_contact'].strip() else 'NOT SET (needed for place lookups)')
    try:
        import PIL  # noqa: F401
        print('Pillow   : installed (portraits possible)')
    except ImportError:
        print('Pillow   : not installed (only needed for portraits)')
    print('Books    :', len(books.load()))


def cmd_add_book(args):
    settings = cfg.load()
    sync.configure(settings)
    config = books.load()
    progress.update_from_device(args.device)
    found = books.scan_device(args.device)
    client = llm.LazyClient(settings)
    for book_id, path in found.items():
        position = progress.get(book_id)
        if book_id in config:
            if not config[book_id].get('device_file'):
                config[book_id]['device_file'] = str(path.relative_to(Path(args.device) / 'documents'))
                books.save(config)
            continue
        if not position:
            continue  # no reading position exported by the plugin yet
        book = epub_chapters.load(path)
        count, chars = books.estimate(book, position['cutoff'])
        print(f'{position["title"]}: {count} states, about {chars // 1000}k characters sent to the AI ({path.name})')
        if not count:
            print('  The reading position is not inside a story chapter; skipped.')
            continue
        if args.yes:
            config[book_id] = {'title': position['title'].split(':')[0].split('(')[0].strip(),
                               'device_file': str(path.relative_to(Path(args.device) / 'documents'))}
            books.save(config)
            epub = books.resolve_epub(book_id, config[book_id], args.device)
            made = states.advance(book_id, epub_chapters.load(epub), position['cutoff'], config[book_id]['title'], client, llm.ask)
            print('  created:', made)
    if not args.yes:
        print('Nothing changed. Run again with --yes to add these books and build their chapter states.')


def cmd_build(args):
    built, copied, failures = sync.build(device=args.device, only=args.book)
    return 1 if failures else 0


def cmd_position(args):
    known = progress.load()
    cutoff = args.cutoff
    if args.chapter:
        entry = books.load()[args.book_id]
        book = epub_chapters.load(books.resolve_epub(args.book_id, entry, None))
        cutoff = epub_chapters.cutoff_for(book, args.chapter)
    if not cutoff:
        raise SystemExit('Give a cutoff (KOReader XPointer) or --chapter N')
    known[args.book_id] = {'title': args.title or known.get(args.book_id, {}).get('title') or books.load().get(args.book_id, {}).get('title', args.book_id),
                           'cutoff': cutoff, 'updated': 'manual'}
    from .util import atomic_json
    atomic_json(progress.file(), known)
    print('Saved.')


def cmd_audit(args):
    settings = cfg.load()
    sync.configure(settings)
    entry = books.load()[args.book_id]
    book = epub_chapters.load(books.resolve_epub(args.book_id, entry, None))
    for name, added, rejected in states.audit_states(args.book_id, book, entry['title'], llm.LazyClient(settings), llm.ask):
        print(name, 'new characters:', added, '| still unverified:', rejected)


def cmd_enrich(args):
    settings = cfg.load()
    sync.configure(settings)
    entry = books.load()[args.book_id]
    book = epub_chapters.load(books.resolve_epub(args.book_id, entry, None))
    for name, kept, rejected in enrich_profiles.enrich(args.book_id, book, entry['title'], llm.LazyClient(settings), llm.ask):
        print(f'{name}: {kept} entries verified, {rejected} rejected')


def cmd_portraits(args):
    settings = cfg.load()
    sync.configure(settings)
    chain = states.load_clean(args.book_id)
    if args.action == 'plan':
        for job in portraits.plan(args.book_id, chain):
            print(f"{job['name']}: new version from chapter {job['from_chapter']} "
                  f"({sum(len(portraits.features(t)) for t in job['looks'])} features, age: {job['age'] or '-'})")
    elif args.action == 'generate':
        if not settings['portraits']:
            print('Portraits are off. Set "portraits": true in config.json to allow image generation (it costs money).')
            return 1
        print('created:', portraits.generate(args.book_id, chain, llm.LazyClient(settings), limit=args.max))
    elif args.action == 'sheet':
        print(portraits.sheet(args.book_id))
    elif args.action == 'approve':
        print(portraits.set_approval(args.book_id, args.target.split(','), True), 'approved')
    elif args.action == 'reject':
        portraits.reject(args.book_id, args.target)
    elif args.action == 'rekey':
        print(portraits.rekey(args.book_id, chain))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='reading-atlas', description='A spoiler-free, growing atlas of the books you read.')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='create the data home and settings').set_defaults(run=cmd_init)
    sub.add_parser('doctor', help='check settings, provider and tools').set_defaults(run=cmd_doctor)
    p = sub.add_parser('add-book', help='list or add books from the connected device')
    p.add_argument('--device', required=True, help='drive or folder of the reader (contains koreader/ and documents/)')
    p.add_argument('--yes', action='store_true', help='add the listed books and build their chapter states')
    p.set_defaults(run=cmd_add_book)
    p = sub.add_parser('build', help='update chapter states and write the HTML pages')
    p.add_argument('--device', help='reader to read positions and EPUB files from')
    p.add_argument('--book', help='only this book id')
    p.set_defaults(run=cmd_build)
    p = sub.add_parser('position', help='set a reading position by hand')
    p.add_argument('book_id')
    p.add_argument('cutoff', nargs='?', help='KOReader XPointer such as /body/DocFragment[10]/body/section/p[57]/text().0')
    p.add_argument('--chapter', type=int, help='instead of a cutoff: the end of story chapter N (for books read without a reader)')
    p.add_argument('--title')
    p.set_defaults(run=cmd_position)
    for name, func, helptext in (('audit', cmd_audit, 'look for forgotten characters in existing states'),
                                 ('enrich', cmd_enrich, 'add character-sheet entries to older states')):
        p = sub.add_parser(name, help=helptext)
        p.add_argument('book_id')
        p.set_defaults(run=func)
    p = sub.add_parser('portraits', help='plan, generate and approve portraits')
    p.add_argument('action', choices=['plan', 'generate', 'sheet', 'approve', 'reject', 'rekey'])
    p.add_argument('book_id')
    p.add_argument('target', nargs='?', help='figure ids for approve/reject')
    p.add_argument('--max', type=int, help='at most this many new images')
    p.set_defaults(run=cmd_portraits)
    args = parser.parse_args(argv)
    return args.run(args) or 0


if __name__ == '__main__':
    sys.exit(main())
