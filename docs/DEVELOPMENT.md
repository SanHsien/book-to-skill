# 開發環境

維護者與 AI 接手用的開發文件。產品使用方式在 [`README.md`](../README.md)；上游同步在 [`UPSTREAM.md`](UPSTREAM.md)；決策在 [`DECISIONS.md`](DECISIONS.md)。

## 架構

```text
文件（PDF / EPUB / DOCX / HTML / RTF / MD / TXT / MOBI）
        │
        ▼
 scripts/extract.py  →  book_to_skill/parsers/*
        │
        ▼
  full_text.txt + metadata.json   （本機工作目錄）
        │
        ▼
 Agent 依根目錄 SKILL.md 產生技能
        │
        ▼
 ~/.claude/skills/<slug>/   或  ~/.copilot/skills/  或  ~/.agents/skills/
   SKILL.md + chapters/ + glossary.md + patterns.md + cheatsheet.md
```

抽取在本機離線執行。根目錄 `SKILL.md` 是**轉換器**規格；產生出來的書本技能是另一次輸出，不要提交進本 repo。

## 本機開發（Windows）

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install pytest ruff defusedxml
$env:PYTHONUTF8 = "1"
pwsh -NoProfile -File tools\dev_check.ps1
.venv\Scripts\python scripts\extract.py --check
```

可選 extra：

```powershell
.venv\Scripts\python -m pip install -e ".[pdf,epub,docx,html,rtf]"
# 技術書表格／程式碼：
.venv\Scripts\python -m pip install -e ".[technical]"
```

Windows 上的外部工具：

| 用途 | 工具 | 建議安裝 |
|------|------|----------|
| PDF（文字書，最快） | poppler `pdftotext` | `winget install oschwartz10612.Poppler` 或 `choco install poppler` |
| MOBI / AZW | Calibre `ebook-convert` | https://calibre-ebook.com/download |
| 掃描 PDF | OCR（例如 `ocrmypdf`） | 先做出文字層再丟給抽取器 |

沒裝選配工具時，`--check` 會列出缺什麼；純 Markdown／文字測試不需要它們。

Windows 預設工作目錄是 `%LOCALAPPDATA%\book-to-skill\work`。可用 `BOOK_SKILL_WORKDIR` 覆寫。`--mode technical`（docling）第一次跑可能下載模型，不要當成離線路徑。

## Canonical gate

`tools\dev_check.ps1` 會依序：

1. `python -m compileall`（`book_to_skill`、`scripts`、`tests`、`tools`）
2. `ruff check`（E9 + F，與上游 CI 相同）
3. `pytest tests/ -q`
4. `python tools/validate_skill.py SKILL.md`

PR CI 另在 Ubuntu 跑 3.9–3.13 矩陣、smoke extraction、bandit，以及本 fork 新增的 Windows job。

## 不要做的事

- 不要手改 `CHANGELOG.md`（git-cliff 產生）。
- 不要把 `docs/guide.md` / `docs/skill-reference.md` 提交進 git（deploy 時組裝，已在 `.gitignore`）。
- 不要對本 fork 開 GitHub Pages 並沿用 `docs/CNAME`。
- 測試不要使用正版電子書或產生出來的技能目錄。
