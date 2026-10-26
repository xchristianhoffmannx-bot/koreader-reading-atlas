import tempfile, unittest, zipfile
from pathlib import Path
from reading_atlas import epub_chapters as E

def doc(paras):
    body = ''.join(f'<p>{p}</p>' for p in paras)
    return f'<html xmlns="http://www.w3.org/1999/xhtml"><body><section>{body}</section></body></html>'

def make_epub():
    path = Path(tempfile.mkdtemp()) / 'b.epub'
    long = ['Satz ' * 120] * 6
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
        z.writestr('OEBPS/c.opf', '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                   '<item id="a" href="a.xhtml"/><item id="b" href="b.xhtml"/><item id="c" href="c.xhtml"/></manifest>'
                   '<spine><itemref idref="a"/><itemref idref="b"/><itemref idref="c"/></spine></package>')
        z.writestr('OEBPS/t.ncx', '<ncx><navMap>'
                   + ''.join(f'<navPoint><navLabel><text>{t}</text></navLabel><content src="{s}"/></navPoint>'
                             for t, s in [('DRAMATIS PERSONAE', 'a.xhtml'), ('Oakfield, October 1013', 'b.xhtml'),
                                          ('Harbourtown, October 1013', 'c.xhtml')]) + '</navMap></ncx>')
        z.writestr('OEBPS/a.xhtml', doc(long))
        z.writestr('OEBPS/b.xhtml', doc(long + ['Spaet.']))
        z.writestr('OEBPS/c.xhtml', doc(long))
    return path


class EpubTest(unittest.TestCase):
    def test_front_matter_is_excluded_and_titles_parsed(self):
        book = E.load(make_epub())
        self.assertEqual([c.title for c in book.chapters], ['Oakfield, October 1013', 'Harbourtown, October 1013'])
        self.assertEqual((book.chapters[0].place, book.chapters[0].when), ('Oakfield', 'October 1013'))

    def test_locate_resolves_spine_and_paragraph(self):
        book = E.load(make_epub())
        chapter, index, offset = E.locate(book, '/body/DocFragment[2]/body/section/p[7]/text().0')
        self.assertEqual((chapter.number, index), (1, 6))
        self.assertIsNone(E.locate(book, '/body/DocFragment[1]/body/section/p[1]/text().0'))  # front matter
        self.assertEqual(len(E.text_upto(chapter, index)), 7)

    def test_cutoff_for_a_chapter_end_resolves_back_to_that_chapter(self):
        book = E.load(make_epub())
        for number in (1, 2):
            chapter, index, _ = E.locate(book, E.cutoff_for(book, number))
            self.assertEqual((chapter.number, index), (number, len(chapter.paragraphs) - 1))
        chapter, index, _ = E.locate(book, E.cutoff_for(book, 1, paragraph=3))
        self.assertEqual(index, 3)


def make_epub_variant(toc='none', file_b='b.xhtml', href_b='b.xhtml'):
    """Three files: a = cast list (front matter), b and c = story. toc: none | nav | landmarks | guide."""
    path = Path(tempfile.mkdtemp()) / 'v.epub'
    long = ['Satz ' * 120] * 6
    manifest = f'<item id="a" href="a.xhtml"/><item id="b" href="{href_b}"/><item id="c" href="c.xhtml"/>'
    guide = ''
    if toc in ('nav', 'landmarks'):
        manifest += '<item id="nav" href="nav.xhtml" properties="nav"/>'
    if toc == 'guide':
        guide = '<guide><reference type="text" href="b.xhtml"/></guide>'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('META-INF/container.xml', '<container><rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
        z.writestr('OEBPS/c.opf', f'<package xmlns="http://www.idpf.org/2007/opf"><manifest>{manifest}</manifest>'
                   f'<spine><itemref idref="a"/><itemref idref="b"/><itemref idref="c"/></spine>{guide}</package>')
        if toc == 'nav':
            links = ''.join(f'<li><a href="{h}">{t}</a></li>' for t, h in [('Cast of Characters', 'a.xhtml'), ('One, May 1010', href_b), ('Two, May 1010', 'c.xhtml')])
            z.writestr('OEBPS/nav.xhtml', '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>'
                       f'<nav epub:type="toc"><ol>{links}</ol></nav></body></html>')
        if toc == 'landmarks':
            z.writestr('OEBPS/nav.xhtml', '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>'
                       f'<nav epub:type="landmarks"><ol><li><a epub:type="bodymatter" href="{href_b}">Start</a></li></ol></nav></body></html>')
        z.writestr('OEBPS/a.xhtml', doc(long + ['Spoiler: Alice stirbt']))
        z.writestr('OEBPS/' + file_b, doc(long))
        z.writestr('OEBPS/c.xhtml', doc(long))
    return path


class FrontMatterFallbackTest(unittest.TestCase):
    def numbers(self, book):
        return [c.spine for c in book.chapters]

    def test_epub3_nav_document_marks_the_cast_list(self):
        book = E.load(make_epub_variant('nav'))
        self.assertEqual(self.numbers(book), [2, 3])
        self.assertEqual(book.chapters[0].title, 'One, May 1010')
        self.assertTrue(book.front_matter_known)

    def test_landmarks_bodymatter_skips_everything_before_the_story(self):
        self.assertEqual(self.numbers(E.load(make_epub_variant('landmarks'))), [2, 3])

    def test_opf_guide_text_reference_skips_front_matter(self):
        self.assertEqual(self.numbers(E.load(make_epub_variant('guide'))), [2, 3])

    def test_book_without_any_toc_loads_and_is_flagged(self):
        book = E.load(make_epub_variant('none'))
        self.assertEqual(self.numbers(book), [1, 2, 3])
        self.assertFalse(book.front_matter_known)

    def test_url_encoded_href_is_resolved(self):
        book = E.load(make_epub_variant('nav', file_b='my b.xhtml', href_b='my%20b.xhtml'))
        self.assertEqual(self.numbers(book), [2, 3])
        self.assertEqual(book.chapters[0].title, 'One, May 1010')


if __name__ == '__main__':
    unittest.main()
