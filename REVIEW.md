# Project Review 2026-08-22

## 結論

`SanHsien/book-to-skill` 已從上游 `virgiliojr94/book-to-skill` fork，並補上與其他維護型 fork 相同的開發環境與治理檔。產品抽取器與根目錄 `SKILL.md` 規格未改寫。

本機 Windows 11 gate 通過：**486 passed, 12 skipped**。Upstream baseline 對齊 fork 起點，沒有未審查的上游 commit。

這是維護骨架落地，**不是**功能改寫。選配 Python 抽取器尚未列為必裝；本機目前只有 Calibre（MOBI/AZW）可用。

## 本輪實證

- Fork：`https://github.com/SanHsien/book-to-skill`，`origin/master` 追上游 `3a97a7115ab3c82edf47f315b544fbcefdd8559c`。
- `pwsh -NoProfile -File tools\dev_check.ps1`：**WINDOWS DEV CHECK GREEN**
  - compileall 通過
  - ruff E9+F：All checks passed
  - pytest：486 passed, 12 skipped（8.22s）
  - `tools/validate_skill.py SKILL.md`：無 Claude Code-breaking issues（1 個 soft warning：body 703 行 > 500）
- `python tools/check_upstream_updates.py`：No new upstream commits.
- `python scripts/extract.py --check`：Calibre `ebook-convert` 可用；venv 已裝 `.[pdf,epub,docx,html,rtf]`（pypdf、pdfminer、ebooklib、bs4、python-docx、trafilatura、striprtf）。尚未安裝 docling 與系統 Poppler `pdftotext`。
- Markdown smoke：`scripts/extract.py sample/note.md --mode text` 成功寫出 `full_text.txt` / `metadata.json`（14 words、1 chapter）。

## 本輪落地

| 項目 | 狀態 |
| --- | --- |
| 繁中 `README.md` + 英文 `README.en.md` | 完成 |
| `AGENTS.md` / `CLAUDE.md` / `FORK.md` / `NOTICE.md` | 完成 |
| `docs/DECISIONS.md` / `UPSTREAM.md` / `DEVELOPMENT.md` | 完成 |
| Windows gate `tools/dev_check.ps1` + CI Windows job | 完成 |
| `upstream-check` + `dependency-freshness` | 完成 |
| `deploy-docs.yml` 僅允許上游 repo 部署 | 完成 |
| 產品 `SKILL.md` | 保留上游原文 |

## 尚未通過 / 後續

- 系統 Poppler `pdftotext` 與 `docling`（technical extra）未裝；文字型 PDF 仍可用 pypdf / pdfminer。要轉掃描書需先 OCR。
- `SKILL.md` 超過 Claude Code 500 行軟上限，屬上游規格，本輪不改。
- 本 fork 尚無自己的 GitHub Release；發行仍以上游 tag 為準，直到有 fork-only 修正需要獨立版本。
