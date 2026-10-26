# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security > Report a vulnerability** on this repository
(private vulnerability reporting). Do not open a public issue for a vulnerability. This is a small hobby project;
expect an answer within a few weeks, not days.

## What matters here

- **Your keys:** API keys are read from environment variables or from the file that koreader-reading-recap already
  protects with Windows DPAPI. This project never writes a key to disk. If you find a way a key could leak (into a
  log, a page, a request to another host), that is a vulnerability.
- **Untrusted EPUB files:** Book text is passed to an AI as data. With API providers the model has no tools. The Codex
  CLI path runs `codex exec` in a read-only sandbox, but a model that can read files is a different risk class: prefer
  an API provider for EPUB files you did not make yourself.
- **The generated page:** it contains text produced by an AI from a book. The page has a Content Security Policy,
  writes all text with `textContent` and embeds the data as inert JSON. A way to run script from book text would be
  a vulnerability.
- **Spoilers are not a security topic** but a core promise: a page contains only states up to your reading position.
  Bugs that leak later chapters are welcome as normal issues.

## Supported versions

Only the latest commit on `main`.
