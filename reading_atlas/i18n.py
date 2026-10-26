"""Translation of the page template.

templates/atlas.html is written in English. For language "de" every visible text is replaced by its German
counterpart from TABLE. Entries are whole string literals (or whole HTML texts), matched together with their quotes or
tags, so identifiers and CSS can never be hit by accident. Entries with raw=True are replaced as plain text.
tests/test_i18n.py checks that every literal is covered and that no German is left in the English page.
"""

# (english, german, raw)
TABLE = [
    ('All', 'Alle', False), ('Short', 'Kurz', False), ('Character', 'Figur', False), ('Map', 'Karte', False),
    ('Done', 'Fertig', False), ('Medium', 'Mittel', False), ('Next', 'Weiter', False),
    ('Concept', 'Begriff', False), ('Characters', 'Figuren', False), ('Idea', 'Gedanke', False),
    ('Timeline', 'Verlauf', False), ('✎ Note', '✎ Notiz', False), ('Appearance', 'Aussehen', False),
    ('Concepts', 'Begriffe', False), ('Event', 'Ereignis', False), ('Ideas', 'Gedanken', False),
    ('☆ Bookmark', '☆ Merken', False), ('Relationship', 'Beziehung', False), ('▶ Watch', '▶ Ansehen', False),
    ('★ Bookmarked', '★ Gemerkt', False), ('Involved', 'Beteiligte', False), ('Events', 'Ereignisse', False),
    ('Insight', 'Erkenntnis', False), ('Location', 'Schauplatz', False), ('Profile', 'Steckbrief', False),
    (' (approximate)', ' (ungefähr)', False), ('Detailed', 'Ausführlich', False), ('Relationships', 'Beziehungen', False),
    ('Locations', 'Schauplätze', False), ('Profiles', 'Steckbriefe', False), ('Insights', 'Erkenntnisse', False),
    ('AI interpretation: ', 'KI-Deutung: ', False), ('✎ Edit', '✎ Bearbeiten', False), ('Traits', 'Eigenschaften', False),
    ('Your reading position', 'Dein Lesestand', False), ('Search character …', 'Figur suchen …', False),
    ('Show in network', 'Im Netz zeigen', False), ('The character network', 'Das Figurennetz', False),
    ('Your timeline', 'Dein Zeitstrahl', False), ('Show in atlas', 'Im Atlas zeigen', False),
    ('No entries.', 'Keine Einträge.', False), ('Search concept …', 'Begriff suchen …', False),
    ('Own guess', 'Eigene Vermutung', False), ('Origin & status', 'Herkunft & Stand', False),
    ('Nothing found.', 'Nichts gefunden.', False), ('Age according to the text: ', 'Alter laut Text: ', False),
    ('Your train of thought', 'Dein Gedankengang', False), ('New insight: ', 'Neue Erkenntnis: ', False),
    ('✎ Edit note', '✎ Notiz bearbeiten', False), ('Correction from you: ', 'Korrektur von dir: ', False),
    ('Idea in the recap', 'Gedanke im Rückblick', False), ('State of this view', 'Stand dieser Ansicht', False),
    ('Profile updated: ', 'Steckbrief ergänzt: ', False), ('(nothing known yet)', '(noch nichts bekannt)', False),
    ('Concepts and people', 'Begriffe und Personen', False), ('Event in the recap', 'Ereignis im Rückblick', False),
    ('Show in character network', 'Im Figurennetz zeigen', False), ('No bookmarks yet.', 'Noch keine Lesezeichen.', False),
    ('This state ends here.', 'Hier endet dieser Stand.', False), (' – jump to location', ' – zum Schauplatz springen', False), (' – show names', ' – Namen zeigen', False),
    ('${pos+1} of ${seq.length}', '${pos+1} von ${seq.length}', False), ('Your recap ends here.', 'Hier endet dein Rückblick.', False),
    ('Nothing new in the file.', 'Nichts Neues in der Datei.', False),
    ('AI interpretation of the description', 'KI-Deutung der Beschreibung', False),
    ('✎ Notes (${notes.length})', '✎ Notizen (${notes.length})', False),
    ('${added} entries imported.', '${added} Angaben übernommen.', False),
    ('Map of the story locations', 'Karte mit den Handlungsorten', False),
    ('★ Bookmarks (${marks.length})', '★ Lesezeichen (${marks.length})', False),
    ('${x.profile.length} new entries', '${x.profile.length} neue Angaben', False),
    ('Backup downloaded.', 'Sicherung wurde heruntergeladen.', False),
    ('Paste the backup text first.', 'Füge zuerst den Sicherungstext ein.', False),
    ('This is not a valid backup file.', 'Das ist keine gültige Sicherungsdatei.', False),
    ('What became known when (${rel.length})', 'Was wann bekannt wurde (${rel.length})', False),
    ('Backup copied to the clipboard.', 'Sicherung in die Zwischenablage kopiert.', False),
    ('Download not possible. Use “Copy”.', 'Download nicht möglich. Nutze „Kopieren“.', False),
    ('Where the places of your recap lie today.', 'Wo die Orte deines Rückblicks heute liegen.', False),
    ('`Chapter “${LABEL[at[0]]||at[0]}”${pct!=null?`, about ${pct} % into the chapter`:\'\'}`',
     '`Kapitel „${LABEL[at[0]]||at[0]}“${pct!=null?`, etwa ${pct} % im Kapitel`:\'\'}`', True),
    ('${vis.length} discoveries up to this state.', '${vis.length} Entdeckungen bis zu diesem Stand.', False),
    ('The key ideas in the order you read them.', 'Die Kerngedanken in der Reihenfolge deines Lesens.', False),
    ("atlas-${(D.book_id||'book').slice(0,8)}-state.json", "atlas-${(D.book_id||'buch').slice(0,8)}-zustand.json", False),
    ('Events are in order, not dated.', 'Die Ereignisse stehen in Reihenfolge, nicht mit Datum.', False),
    ('Approximate area of the invented places; not an exact position.', 'Ungefährer Raum der erfundenen Orte; keine genaue Lage.', False),
    ('Tap a concept. The lines show connections.', 'Tippe einen Begriff an. Die Linien zeigen Zusammenhänge.', False),
    ('Own guess · written at ${stateLabel(n.state)}', 'Eigene Vermutung · geschrieben bei ${stateLabel(n.state)}', False),
    ('Copying not allowed. The text is below for selecting.', 'Kopieren nicht erlaubt. Der Text steht unten zum Markieren.', False),
    ('Tap a character. The lines show who is connected to whom.', 'Tippe eine Figur an. Die Linien zeigen, wer mit wem verbunden ist.', False),
    ('The file does not belong to this book or has an unknown format.', 'Die Datei gehört nicht zu diesem Buch oder hat ein unbekanntes Format.', False),
    ('Drawn only from what your text says about the appearance:', 'Gezeichnet nur aus dem, was dein gelesener Text über das Aussehen sagt:', False),
    ('You are seeing the world after “${cur.label}”. Later chapters are hidden.', 'Du siehst die Welt nach „${cur.label}“. Spätere Kapitel sind ausgeblendet.', False),
    ("${S[i].label}${i===MAX&&active===MAX?' · your reading position':''} (${rows.length})", "${S[i].label}${i===MAX&&active===MAX?' · deine Lesestelle':''} (${rows.length})", False),
    ("State ${active+1}/${S.length} · ${cur.label}${cur.complete?'':' · your reading position'}", "Stand ${active+1}/${S.length} · ${cur.label}${cur.complete?'':' · deine Lesestelle'}", False),
    ('No notes yet. Your notes are your own guesses and never become book facts.', 'Noch keine Notizen. Deine Notizen sind eigene Vermutungen und werden nie zu Buchfakten.', False),
    ('Present-day coastlines, not a historical map. The numbers match the locations.', 'Heutige Küstenlinien, keine historische Karte. Die Nummern entsprechen den Schauplätzen.', False),
    ('Basis: your recap, as of ${D.asof}. Built only from the text you have read, no later events added.', 'Grundlage: dein Rückblick, Stand ${D.asof}. Nur aus dem gelesenen Text erstellt, keine späteren Ereignisse ergänzt.', False),
    ('Own guess. Never becomes a book fact and is stored only on this device.', 'Eigene Vermutung. Wird nie zu einem Buchfakt und nur auf diesem Gerät gespeichert.', False),
    ('Status according to the text: ', 'Stand laut Text: ', False),
    ('Clothing: interpretation based on status', 'Kleidung: Deutung nach Stand', False),
    ('Load', 'Laden', False), ('List', 'Liste', False), ('Note', 'Notiz', False), ('Later', 'Später', False),
    ('Search', 'Suchen', False), ('Back', 'Zurück', False), ('Groups', 'Gruppen', False), ('Delete', 'Löschen', False),
    ('Copy', 'Kopieren', False), ('Search …', 'Suchen …', False), ('Cancel', 'Abbrechen', False), ('Close', 'Schließen', False),
    ('Save', 'Speichern', False), ('Enlarge', 'Vergrößern', False), ('View all', 'Alle ansehen', False),
    ('Discoveries', 'Entdeckungen', False), ('Skip', 'Überspringen', False), ('Story locations', 'Handlungsorte', False),
    ('Load from text', 'Aus Text laden', False), ('Relationship network', 'Beziehungsnetz', False),
    ('Backup text', 'Sicherungstext', False), ('At a glance', 'Auf einen Blick', False),
    ('Main navigation', 'Hauptnavigation', False), ('Enlarged map', 'Karte vergrößert', False),
    ('Hide images', 'Bilder ausblenden', False),
    ('Jump within the atlas', 'Im Atlas springen', False), ('Discovery journal', 'Entdeckungsjournal', False),
    ('Story so far', 'Was bisher geschah', False), ('Experience discoveries', 'Entdeckungen erleben', False),
    ('↺ Story so far', '↺ Was bisher geschah', False), ('Historical overview', 'Historische Übersicht', False),
    ('Load state (file)', 'Zustand laden (Datei)', False), ('Reduce animations', 'Animationen reduzieren', False),
    ('Drag to move', 'Ziehen zum Verschieben', False), ('Save state (file)', 'Zustand sichern (Datei)', False),
    ('Where the story takes place', 'Wo die Geschichte spielt', False),
    ('To your current reading position', 'Zur aktuellen Lesestelle', False),
    ('The world at this point', 'Die Welt zu diesem Zeitpunkt', False),
    ('Your story world has grown', 'Deine Romanwelt ist gewachsen', False),
    ('Paste backup text here', 'Sicherungstext hier einfügen', False),
    ('In story order. Arrangement and distances are schematic.', 'In der Reihenfolge der Handlung. Anordnung und Abstände sind schematisch.', False),
    ('new', 'neu', False),
    ('All open riddles', 'Alle offenen Rätsel', False),
    ('Tap a question – below it you find what the text says so far.', 'Tippe eine Frage an – darunter steht, was der Text bisher dazu hergibt.', False),
    ('Open in the story · ', 'Offen in der Geschichte · ', True),
    ('What is documented so far', 'Was bisher belegt ist', False),
    ('Next riddle →', 'Nächstes Rätsel →', False),
    ('🎲 Show me a character I have not met yet', '🎲 Zeig mir eine Figur, die ich noch nicht kenne', False),
    ('Spoiler-free: only what you have read up to your reading position is shown here.', 'Spoilerfrei: Hier steht nur, was du bis zu deiner Lesestelle gelesen hast.', False),
    ('You are viewing an earlier position – later chapters stay hidden.', 'Du siehst eine frühere Stelle – spätere Kapitel bleiben verborgen.', False),
    ('Who is close to whom?', 'Wer steht wem nah?', False),
    ('open riddles', 'offene Rätsel', False),
    ('What is still to come', 'Was noch aussteht', False),
    ('Where it all happens', 'Wo alles spielt', False),
    ('The path so far', 'Der Weg bis hier', False),
    ('Riddle ${qi+1} of ${qs.length}', 'Rätsel ${qi+1} von ${qs.length}', False),
    ('Riddles', 'Rätsel', False),
    ('Hide', 'Verbergen', False),
]


def _wrap(text):
    """All ways a whole literal can appear in the page source."""
    return [("'" + text + "'", "'{}'"), ('"' + text + '"', '"{}"'), ('`' + text + '`', '`{}`'),
            ('>' + text + '<', '>{}<'), ('> ' + text + '<', '> {}<')]


def translate(page, lang):
    if lang == 'en':
        return page
    if lang != 'de':
        raise ValueError("language must be 'en' or 'de'")
    for english, german, raw in sorted(TABLE, key=lambda row: -len(row[0])):
        if raw:
            page = page.replace(english, german)
            continue
        for source, template in _wrap(english):
            page = page.replace(source, template.format(german))
    return page.replace('<html lang="en">', '<html lang="de">')
