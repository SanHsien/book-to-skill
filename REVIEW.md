# Repository review（Windows-first）

- Review date: 2026-08-22
- Review baseline: `8a710a3385fac7062820d41a024d7925cfc3c20a`
- Upstream reviewed through: `3a97a7115ab3c82edf47f315b544fbcefdd8559c`
- Primary environment: Windows 11、PowerShell、Python 3.14（本機）、CI Windows 3.12 / Ubuntu 3.9–3.13
- Status: 維護骨架可用；產品抽取器未改寫；官方仍是上游 `virgiliojr94/book-to-skill`

## 結論

這個 fork 適合作為 Windows 本機、離線把書轉成 Agent 技能的維護線。抽取器沒有 `shell=True` / `eval` / `exec` / `pickle`，`--install-missing` 只會裝白名單套件，輸出目錄會拒絕 symlink。本機 gate 與 GitHub Actions 在 `8a710a3` 全綠。

現階段的主要風險不是轉換演算法，而是：

1. 文件入口仍有多處指向上游 clone URL，跟本 fork README 不一致。
2. `.gitignore` 不擋書籍／產出，誤 commit 靠政策。
3. `--mode technical`（docling）的離線假設尚未用實跑證明。

不把 fork 當成第二個「官方 repo」。惡意仿冒見上游 [`SECURITY-NOTICE.md`](SECURITY-NOTICE.md)；本線是標明來源的 MIT 維護 fork。

## 本輪實證

### 本機

```text
pwsh -NoProfile -File tools\dev_check.ps1
→ compileall / ruff E9+F / pytest / validate_skill 全綠
→ 498 collected; 491 passed, 7 skipped（3.03s）
→ SKILL.md：無 Claude Code-breaking issues（1 soft warning：703 行 > 500）

python -m bandit -q -r book_to_skill scripts tools --severity-level high --confidence-level medium
→ exit 0（High = 0）

python -m bandit -q -r book_to_skill scripts tools -ll
→ Medium 1：B314 xml.etree.ElementTree.fromstring @ book_to_skill/parsers/docx.py:54
→ Low 18（subprocess 探測，未當 finding）

python tools/check_upstream_updates.py
→ No new upstream commits.

python scripts/extract.py --check
→ PDF 文字鏈 / EPUB / DOCX / HTML / RTF / Calibre MOBI：ready
→ 缺：系統 Poppler pdftotext、docling
```

Windows skip（7）：POSIX `chmod 0o000`／`0o700` 語意、以及本機未開 Developer Mode 時無法建 directory symlink（WinError 1314）。

### GitHub Actions（`8a710a3` push）

| Workflow | 結果 | 說明 |
|---|---|---|
| [CI](https://github.com/SanHsien/book-to-skill/actions/runs/32551914676) | success | Ubuntu 3.9–3.13、Windows py3.12、lint、smoke、bandit、validate SKILL.md 全綠；PR-only jobs skipped |
| [Deploy docs](https://github.com/SanHsien/book-to-skill/actions/runs/32551914603) | success | MkDocs **build** 通過；`Deploy to gh-pages` **skipped**（repo 閘門生效） |
| [CodeQL](https://github.com/SanHsien/book-to-skill/actions/runs/32551914623) | success | |
| [Upstream check](https://github.com/SanHsien/book-to-skill/actions/runs/32551914669) | success | |
| [Dependency freshness](https://github.com/SanHsien/book-to-skill/actions/runs/32551914639) | success | |

GitHub Pages API 對本 fork 回 404（未開站）。`git ls-files` 無 `.pdf` / `.epub` / `.mobi` / `full_text.txt` / `.env`。

## 開放 findings

| ID | 嚴重度 | Finding | 證據 | 建議 |
|---|---|---|---|---|
| R-01 | P2 | 預設工作目錄是可預測的 `%TEMP%\book_skill_work`。POSIX 有 uid／`0o700` 閘門，Windows 不做擁有者檢查；symlink 測試在本機因權限 skip。 | `book_to_skill/config.py:5-10`、`utils.py:893-916`；`test_output_dir_security.py` 4 案 skip | 正式轉換設 `BOOK_SKILL_WORKDIR` 到私人目錄。多使用者機器不要共用預設暫存。 |
| R-02 | P2 | `--mode technical` 走 docling，程式碼未顯式禁網路；首次跑可能拉模型，與「完全離線」敘述有張力。本輪**沒有**實跑 docling。 | `book_to_skill/parsers/pdf.py:145-163`；`SECURITY.md` 寫不 phone home | 技術書路徑先當「可能外連」。要離線需另證 docling artifacts／HF cache。 |
| R-03 | P2 | `.gitignore` 不擋 `*.pdf` / `*.epub` / 產生技能；`test_repo_hygiene.py` 只閘 bytecode。 | `.gitignore`；`git check-ignore` 對 `book.pdf` 不匹配 | 至少 ignore 常見電子書副檔名與 `full_text.txt`。提交前人工檢查仍必要。 |
| R-04 | P2 | `CONTRIBUTING.md`、`docs/install.md` 的 clone / `npx` / pip URL 全指 `virgiliojr94`。跟本 fork `README.md` 的 SanHsien 安裝路徑不一致。 | `CONTRIBUTING.md:21`；`docs/install.md:17-25` | 加 fork 註記：產品安裝可走上游；要本線文件／Windows gate 才 clone SanHsien。 |
| R-05 | P2 | Bandit Medium B314：stdlib `ElementTree.fromstring` 解析 DOCX XML。已有 `validate_docx_xml_safety` 掃 `<!DOCTYPE` / `<!ENTITY>`，CI 刻意只閘 High。 | `docx.py:54`、`docx.py:93-108`；CI 註解將 ratchet 到 medium | 維持現況可接受。要關閉 finding 再換 `defusedxml` 並補對抗測試。 |
| R-06 | P3 | ~~`README.ru.md` 與繁中主檔真相源衝突。~~ **已關閉（2026-08-22）：** 刪除俄文 README，公開入口只留繁中／英文。 | 曾：`README.ru.md` | 上游再加第三語系時略過。 |
| R-07 | P3 | 繁中 README 用 SanHsien CI badge，英文 README 仍用上游 release / Trendshift，沒有本 fork CI。Sponsor 兩邊都指上游（正確）。 | `README.md` / `README.en.md` | 英文頁加一行 fork CI，避免「這是哪個 repo」混淆。 |
| R-08 | P3 | `codeql.yml` 仍 pin tag（`checkout@v7.0.1`、`codeql-action@v4`），與 ci／deploy 的 SHA pin 不一致。 | `.github/workflows/codeql.yml` | 下次 Dependabot 週期改 SHA。 |

## 已檢查、不列為 finding

- 全套件無 `os.system`、`shell=True`、`eval(`、`exec(`、`pickle`。`subprocess.run` 皆 argv 列表。
- `--install-missing` 的套件名只來自 `PYTHON_DEPENDENCIES` 白名單（`config.py:30-39`）。CLI 下一個參數是 `yes/no/ask`，不會 `pip install <任意字串>`。
- 預設不安裝：`BOOK_SKILL_INSTALL_MISSING` 預設 `ask`；非 TTY 不會自動 pip。
- EPUB／DOCX 用記憶體 `ZipFile.read`，未 `extractall`。
- HTML：`trafilatura.extract` 吃本地字串，不是 URL fetch。
- 產品 `SKILL.md` 仍是轉換器規格；`AGENTS.md` / `CLAUDE.md` 分開且禁止覆寫。
- `deploy-docs.yml` 的 `github.repository == 'virgiliojr94/book-to-skill'` 已在本 fork 的實際 run 上 skip deploy。
- Sponsor、use-cases、惡意仿冒警告維持指向上游，符合 `NOTICE.md`。
- Dependabot 不自動合併（`docs/DECISIONS.md`），合理。
- 本 fork 不自製 GitHub Release；`pyproject.toml` `1.4.0` 是上游產品版本。

## 尚未宣稱範圍

- **沒有**用真實購買的 PDF／EPUB／DOCX／掃描書做端到端轉換；閘門是單元測試 + Markdown smoke（Ubuntu CI）+ 本機無書檔抽取。
- **沒有**驗證 OCR、docling technical、Poppler `pdftotext` 在這台機器上的品質。
- **沒有**獨立 Windows 格式樣本矩陣；Windows job 跑的是與 `dev_check.ps1` 相同的 gate（CI 不安 extra）。
- `dev_check.ps1` **不含** bandit、MkDocs build、dependency-review。那些只在 GitHub Ubuntu jobs。
- **不宣稱** fork 托管官方文件站；`mkdocs.yml` / `docs/CNAME` 仍是 `booktoskill.is-a.dev`。
- **不宣稱** `docs/install.md`、`CONTRIBUTING.md` 已完全 fork 化。
- 產生技能目錄（`~/.claude/skills/<slug>/` 等）不在本 repo 工作樹，未掃描是否含原文。

## 建議下一步（未動手）

1. `docs/install.md` + `CONTRIBUTING.md` 加本 fork 與上游的分流說明。
2. `.gitignore` 加上電子書副檔名與抽取產出檔名。
3. 有真實技術書再決定要不要裝 `docling`，並記錄是否外連。
4. 需要關閉 B314 時才換 `defusedxml`，不要為了掃描綠燈改解析行為。
