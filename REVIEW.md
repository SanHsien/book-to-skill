# Repository review（Windows-first）

- Review date: 2026-08-22
- Review baseline: `8a710a3385fac7062820d41a024d7925cfc3c20a`
- Fix branch: `fix/review-findings`（本輪關閉可修 findings，不回貢）
- Upstream reviewed through: `3a97a7115ab3c82edf47f315b544fbcefdd8559c`
- Primary environment: Windows 11、PowerShell、Python 3.14（本機）、CI Windows 3.12 / Ubuntu 3.9–3.13
- Status: 可修 findings 已關；產品抽取器仍不回貢；官方仍是上游 `virgiliojr94/book-to-skill`

## 結論

這個 fork 適合作為 Windows 本機把書轉成 Agent 技能的維護線。抽取器沒有 `shell=True` / `eval` / `exec` / `pickle`，`--install-missing` 只會裝白名單套件，輸出目錄會拒絕 symlink。

本輪已在 fork 內修好 R-01～R-05、R-07、R-08（R-06 先前已關）。剩餘風險是能力邊界，不是未修的程式 finding：

1. `--mode technical`（docling）仍**沒有**本機實跑，只加了外連警示。
2. 沒有真實書籍端到端轉換。
3. 不把 fork 當成第二個官方 repo。

惡意仿冒見上游 [`SECURITY-NOTICE.md`](SECURITY-NOTICE.md)；本線是標明來源的 MIT 維護 fork。

## 本輪實證

### 本機（`fix/review-findings`）

```text
pwsh -NoProfile -File tools\dev_check.ps1
→ compileall / ruff E9+F / pytest / validate_skill 全綠
→ 495 passed, 8 skipped
→ SKILL.md：無 Claude Code-breaking issues（1 soft warning：712 行 > 500）

python -m bandit -q -r book_to_skill scripts tools --severity-level high --confidence-level medium
→ exit 0（High = 0）

python -m bandit -q -r book_to_skill scripts tools -ll
→ exit 0（Medium+ = 0；B314 已消失）
```

Windows skip（8）：POSIX `chmod` 語意、本機未開 Developer Mode 時無法建 directory symlink（WinError 1314）、以及 POSIX 工作目錄測試（Windows 無法實例化 `PosixPath`）。

### GitHub Actions（`8a710a3` push，修 finding 前）

| Workflow | 結果 | 說明 |
|---|---|---|
| [CI](https://github.com/SanHsien/book-to-skill/actions/runs/32551914676) | success | Ubuntu 3.9–3.13、Windows py3.12、lint、smoke、bandit、validate SKILL.md 全綠 |
| [Deploy docs](https://github.com/SanHsien/book-to-skill/actions/runs/32551914603) | success | MkDocs **build** 通過；`Deploy to gh-pages` **skipped** |
| [CodeQL](https://github.com/SanHsien/book-to-skill/actions/runs/32551914623) | success | |
| [Upstream check](https://github.com/SanHsien/book-to-skill/actions/runs/32551914669) | success | |
| [Dependency freshness](https://github.com/SanHsien/book-to-skill/actions/runs/32551914639) | success | |

`git ls-files` 無 `.pdf` / `.epub` / `.mobi` / `full_text.txt` / `.env`。本輪另以 `git check-ignore` 確認 `book.pdf` 與根目錄 `full_text.txt` 會被忽略。

## 已關閉 findings

| ID | 嚴重度 | 原 finding | 關閉方式 |
|---|---|---|---|
| R-01 | P2 | Windows 預設 `%TEMP%\book_skill_work`，多使用者可預測。 | `default_output_dir()`：Windows 改 `%LOCALAPPDATA%\book-to-skill\work`；`BOOK_SKILL_WORKDIR` 仍優先。POSIX 不變。見 `tests/test_default_workdir.py`。 |
| R-02 | P2 | `--mode technical` / docling 可能外連，文件寫完全離線。 | stderr 警示、README / SECURITY / SKILL.md 寫明首次可能下載模型。**未**實跑 docling，不宣稱已離線驗證。 |
| R-03 | P2 | `.gitignore` 不擋電子書／產出。 | 加入 `*.pdf` `*.epub` `*.mobi` `*.azw` `*.azw3` `/full_text.txt` `/metadata.json`；`test_repo_hygiene.py` 閘 pattern 與 `git check-ignore`。 |
| R-04 | P2 | `CONTRIBUTING.md` / `docs/install.md` 全指上游。 | 標明 SanHsien fork vs 上游產品安裝；PowerShell clone 與 pip 預設本線。 |
| R-05 | P2 | Bandit B314：`ElementTree.fromstring` 解析 DOCX。 | zipfile 路徑改 `defusedxml`（必要依賴）；缺套件直接 `ExtractionError`，不回退 stdlib。Bandit `-ll` 現為 0。 |
| R-06 | P3 | `README.ru.md` 與繁中主檔衝突。 | 已刪；公開入口只留繁中／英文。 |
| R-07 | P3 | 英文 README 沒有本 fork CI badge。 | `README.en.md` 加上 SanHsien CI；上游 release badge 改標 Upstream。 |
| R-08 | P3 | `codeql.yml` pin tag 而非 SHA。 | checkout `3d3c42e…`（v7.0.1）、codeql-action `db488dd…`（v4.37.8）；`persist-credentials: false`。 |

## 已檢查、不列為 finding

- 全套件無 `os.system`、`shell=True`、`eval(`、`exec(`、`pickle`。`subprocess.run` 皆 argv 列表。
- `--install-missing` 的套件名只來自 `PYTHON_DEPENDENCIES` 白名單。CLI 下一個參數是 `yes/no/ask`，不會 `pip install <任意字串>`。
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
- **沒有**驗證 OCR、docling technical、Poppler `pdftotext` 在這台機器上的品質。R-02 只保證有警告，不保證離線。
- **沒有**獨立 Windows 格式樣本矩陣；Windows job 跑的是與 `dev_check.ps1` 相同的 gate（CI 不安 extra）。
- `dev_check.ps1` **不含** bandit、MkDocs build、dependency-review。那些只在 GitHub Ubuntu jobs。
- **不宣稱** fork 托管官方文件站；`mkdocs.yml` / `docs/CNAME` 仍是 `booktoskill.is-a.dev`。
- `python-docx` 路徑仍走 `python-docx`（有裝 extra 時）；B314 關的是 stdlib zipfile 解析。
- 產生技能目錄（`~/.claude/skills/<slug>/` 等）不在本 repo 工作樹，未掃描是否含原文。

## 建議下一步（未動手）

1. 有真實技術書再決定要不要裝 `docling`，並記錄是否外連。
2. 需要時再裝 Poppler，做文字 PDF 對照。
3. 這些修正不送上游。
