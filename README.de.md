# KOReader Reading Atlas (Kurzfassung auf Deutsch)

Ein **spoilerfreier Atlas für die Bücher, die du liest**. Zu jedem Buch entsteht eine einzelne HTML-Seite mit Figuren, Beziehungen, Zeitstrahl, Schauplätzen auf einer Karte und einem Entdeckungsjournal. Die Seite **wächst mit deiner Leseposition**: Du siehst nur, was der Text bis dahin wirklich sagt, und ein Regler zeigt die Welt nach jedem früheren Kapitel.

Das Werkzeug ergänzt [koreader-reading-recap](https://github.com/xchristianhoffmannx-bot/koreader-reading-recap): Das Plugin meldet, wie weit du gelesen hast, der Atlas macht aus dem Text bis dahin die Seite. Du nutzt **dein eigenes KI-Konto** (Codex-Anmeldung oder eigener API-Schlüssel für OpenAI, Anthropic oder Google Gemini).

## Kurz erklärt

- **Figuren** mit Steckbrief (Aussehen, Eigenschaften, Herkunft) und Fundstelle („Kapitel …, etwa 45 %“), Beziehungsnetz, Liste mit Suche.
- **Zeitstrahl**, **Karte** mit Pins (Natural Earth und OpenStreetMap), **Zeitregler** „Die Welt zu diesem Zeitpunkt“.
- **Entdeckungsjournal** mit kurzen Animationen, Lesezeichen, eigenen Notizen (immer als Vermutung gekennzeichnet) und Sicherung als JSON-Datei.
- **Porträts** sind optional und standardmäßig aus (Bildgenerierung kostet Geld). Sie entstehen nur aus Aussehensangaben, die der Text nennt, und sind als KI-Deutung gekennzeichnet.
- Oberfläche und Texte auf Deutsch oder Englisch (`"language": "de"` in `config.json`). Bücher können in jeder Sprache sein.

## Wichtig

- Nur **kopierschutzfreie EPUB-Dateien**, die du selbst besitzt. Das Projekt enthält keine Bücher und keine Möglichkeit, Kopierschutz zu entfernen.
- Der Buchtext bis zu deiner Leseposition geht an den von dir gewählten KI-Anbieter. Gespeichert werden nur Fakten in eigenen Worten mit Fundstelle, kein Buchtext.
- Frühes Release: getestet auf einem Kindle mit KOReader unter Windows mit der Codex-Anmeldung. Die API-Wege sind mit simulierten Antworten getestet, noch nicht gegen die echten Dienste.

Installation, Einstellungen, Befehle und Grenzen stehen in der englischen [README.md](README.md). Technik: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md). Datenschutz und Urheberrecht: [docs/PRIVACY-AND-COPYRIGHT.md](docs/PRIVACY-AND-COPYRIGHT.md).

Lizenz: AGPL-3.0-oder-später, siehe [COPYING](COPYING).
