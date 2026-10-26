"""Read an EPUB as story chapters with numbered paragraphs and resolve KOReader reading positions.

Front/back matter (cover, contents, blurb, cast list, map, ...) is never a knowledge source:
it would reveal the whole plot. Chapter titles are only exposed up to the reading position.
"""
import hashlib
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

SKIP_TITLE = re.compile(
    r'^(cover|inhalt|inhaltsverzeichnis|über dieses buch|titel|titelseite|dramatis personae|personen|'
    r'karte|karten|zitat|widmung|impressum|danksagung|nachwort|anmerkung|glossar|leseprobe|'
    r'contents|table of contents|about this book|about the author|title page|title|map|maps|epigraph|dedication|'
    r'copyright|imprint|acknowledg(e)?ments?|afterword|author.s note|glossary|sample|cast of characters|characters|'
    r'\d+\.\s*teil\b.*|part\s+(\d+|[ivxl]+|one|two|three|four|five)\b.*|\d+\.\s*part\b.*)$', re.I)
TITLE_PLACE_TIME = re.compile(r'^(?P<place>[^,]+),\s*(?P<when>[A-Za-zÄÖÜäöüéèê]+\s+\d{3,4}|\d{3,4})\s*$')
MIN_STORY_CHARS = 2000


def partial_md5(path):
    """KOReader's partial MD5 (sampled 1 KiB blocks), the book_id used in recap requests."""
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for i in range(-1, 11):
            f.seek(1024 << (2 * i) if i >= 0 else 256)
            block = f.read(1024)
            if not block:
                break
            md5.update(block)
    return md5.hexdigest()


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _text(element):
    return re.sub(r'\s+', ' ', ''.join(element.itertext())).strip()


class Chapter:
    def __init__(self, number, spine, title, paragraphs, tree):
        self.number, self.spine, self.title, self.paragraphs, self.tree = number, spine, title, paragraphs, tree
        match = TITLE_PLACE_TIME.match(title)
        self.place = match['place'].strip() if match else ''
        self.when = match['when'].strip() if match else ''


class Book:
    def __init__(self, chapters, spine_count, front_matter_known=True):
        self.chapters, self.spine_count = chapters, spine_count
        self.front_matter_known = front_matter_known   # False: no table of contents or landmarks, cast lists and blurbs may be included

    def by_spine(self, spine):
        return next((c for c in self.chapters if c.spine == spine), None)


def _zip_path(folder, href):
    """Name of a file inside the EPUB: href relative to its folder, URL-decoded ("My%20Book.xhtml"), without fragment."""
    return posixpath.normpath(posixpath.join(folder, unquote(href.split('#')[0])))


def _type(element):
    return next((v for k, v in element.attrib.items() if _local(k) == 'type'), '')


def _read_titles(z, base, nav_names):
    """Chapter titles and the first story file, from NCX, EPUB3 nav document (toc) and landmarks."""
    titles, body_start = {}, ''
    for name in z.namelist():
        if name.endswith('.ncx'):
            for point in ET.fromstring(z.read(name)).iter():
                if _local(point.tag) == 'navPoint':
                    label = next((_text(t) for t in point.iter() if _local(t.tag) == 'text'), '')
                    src = next((c.get('src') for c in point if _local(c.tag) == 'content'), '')
                    titles.setdefault(_zip_path(posixpath.dirname(name), src), label)
    for name in nav_names:
        try:
            root = ET.fromstring(z.read(name))
        except (KeyError, ET.ParseError):
            continue
        folder = posixpath.dirname(name)
        for nav in (n for n in root.iter() if _local(n.tag) == 'nav'):
            kind = _type(nav)
            for a in (a for a in nav.iter() if _local(a.tag) == 'a' and a.get('href')):
                if 'toc' in kind or not kind:
                    titles.setdefault(_zip_path(folder, a.get('href')), _text(a))
                elif 'landmarks' in kind and 'bodymatter' in _type(a) and not body_start:
                    body_start = _zip_path(folder, a.get('href'))
    return titles, body_start


def load(path):
    z = zipfile.ZipFile(path)
    opf_path = re.search(r'full-path="([^"]+)"', z.read('META-INF/container.xml').decode('utf-8', 'replace')).group(1)
    base = posixpath.dirname(opf_path)
    opf = ET.fromstring(z.read(opf_path))
    items = {i.get('id'): _zip_path(base, i.get('href')) for i in opf.iter() if _local(i.tag) == 'item' and i.get('href')}
    nav_names = [_zip_path(base, i.get('href')) for i in opf.iter()
                 if _local(i.tag) == 'item' and i.get('href') and 'nav' in (i.get('properties') or '').split()]
    spine = [i.get('idref') for i in opf.iter() if _local(i.tag) == 'itemref']
    titles, body_start = _read_titles(z, base, nav_names)
    if not body_start:   # EPUB2: <guide><reference type="text|bodymatter"> marks the start of the story
        body_start = next((_zip_path(base, r.get('href')) for r in opf.iter() if _local(r.tag) == 'reference'
                           and r.get('href') and (r.get('type') or '').lower() in ('text', 'bodymatter')), '')
    start = next((n for n, idref in enumerate(spine) if body_start and items.get(idref) == body_start), 0)
    chapters = []
    for number, idref in enumerate(spine, 1):
        href = items.get(idref)
        if not href or number - 1 < start:
            continue
        title = titles.get(href, '')
        if SKIP_TITLE.match(title.strip()):
            continue
        tree = ET.fromstring(z.read(href))
        paragraphs = [_text(p) for p in tree.iter() if _local(p.tag) == 'p']
        paragraphs = [p for p in paragraphs if p]
        if sum(map(len, paragraphs)) < MIN_STORY_CHARS:
            continue
        chapters.append(Chapter(len(chapters) + 1, number, title.strip(), paragraphs, tree))
    return Book(chapters, len(spine), bool(titles) or bool(body_start))


def locate(book, cutoff):
    """KOReader XPointer -> (chapter, paragraph_index, char_offset); paragraph_index counts <p> in document order.

    Returns None if the position is outside the story chapters (front matter) or not resolvable."""
    m = re.match(r'/body/DocFragment\[(\d+)\](/.*)', cutoff)
    if not m:
        return None
    chapter = book.by_spine(int(m.group(1)))
    if not chapter:
        return None
    node = next(n for n in chapter.tree.iter() if _local(n.tag) == 'body')
    offset = 0
    for step in m.group(2).split('/')[2:]:  # skip the leading '' and 'body'
        text_node = re.fullmatch(r'text\(\)(?:\[\d+\])?(?:\.(\d+))?', step)
        if text_node:
            offset = int(text_node.group(1) or 0)
            break
        s = re.fullmatch(r'([A-Za-z0-9]+)(?:\[(\d+)\])?', step)
        if not s:
            return None
        tag, nth = s.group(1), int(s.group(2) or 1)
        same = [c for c in node if _local(c.tag) == tag]
        if nth > len(same):
            return None
        node = same[nth - 1]
    paragraphs = [p for p in chapter.tree.iter() if _local(p.tag) == 'p' and _text(p)]
    containing = None
    for index, p in enumerate(paragraphs):
        if p is node or any(d is node for d in p.iter()):
            containing = index
            break
    if containing is None:
        return None
    return chapter, containing, offset


def text_upto(chapter, paragraph, offset=0):
    """Numbered paragraphs 0..paragraph of the chapter; the last one is cut at offset when given."""
    lines = []
    for i in range(paragraph + 1):
        text = chapter.paragraphs[i]
        if i == paragraph and offset and offset < len(text):
            text = text[:offset]
        lines.append((i, text))
    return lines


def cutoff_for(book, chapter_number, paragraph=None):
    """KOReader-style XPointer for the end of a chapter (or a given paragraph), for books read without a reader."""
    chapter = next(c for c in book.chapters if c.number == chapter_number)
    paragraphs = [p for p in chapter.tree.iter() if _local(p.tag) == 'p' and _text(p)]
    target = paragraphs[len(paragraphs) - 1 if paragraph is None else paragraph]
    body = next(n for n in chapter.tree.iter() if _local(n.tag) == 'body')

    def walk(node, steps):
        if node is target:
            return steps
        for child in node:
            tag = _local(child.tag)
            index = [c for c in node if _local(c.tag) == tag].index(child) + 1
            found = walk(child, steps + [f'{tag}[{index}]'])
            if found:
                return found
        return None
    steps = walk(body, [])
    return f'/body/DocFragment[{chapter.spine}]/body/' + '/'.join(steps) + '/text().0'

