# Security Policy

## Scope

This repository is the SanHsien maintenance fork of
[`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill).
Report vulnerabilities that affect **this fork** via this repository's Security tab.
Issues that also exist upstream should be reported there as well.

book-to-skill is a local conversion tool. It reads document files you point it at
and writes skill files to your skills directory. The extractor does **not** upload
your files or run a network service.

That local-only claim does **not** cover:

- `pip install` / `--install-missing yes` (downloads packages from PyPI),
- `--mode technical` with **docling** (first run may download models; not guaranteed offline),
- optional tools you install yourself (Calibre, Poppler, OCR).

The main security surface is:

- the Python extraction code (parsing untrusted document files), and
- the optional dependencies it can install on request (`pip install …` when you
  choose `--install-missing yes`).

On Windows the default work directory is `%LOCALAPPDATA%\book-to-skill\work`
instead of a shared `%TEMP%\book_skill_work` path. Override with
`BOOK_SKILL_WORKDIR` if you need an isolated location.

## Supported versions

This fork tracks upstream `1.x` and does not cut its own GitHub Releases unless a
fork-only fix needs an independent version. Please reproduce issues against the
current `master` of this repository.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead use GitHub's
private vulnerability reporting:

- Go to **this** repository's **Security** tab → **Report a vulnerability**.

Include: affected commit or tag, a minimal reproduction (ideally a small sample
file or crafted input), and the impact you observed.

## Good practices for users

- Run `python scripts/extract.py --check` (Windows) or
  `python3 scripts/extract.py --check` to see exactly which extractors are in
  use; install dependencies yourself if you prefer to control what is added.
- Only convert documents you trust and have the right to process (see the README's
  Copyright & fair-use section).
- Do not commit purchased ebooks, `full_text.txt`, or generated skills.
