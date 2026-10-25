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


if __name__ == '__main__':
    unittest.main()
