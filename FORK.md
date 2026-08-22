# Fork 維護說明

本 repo fork 自 [`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill)，
沿用 MIT License 與完整 Git 歷史。

## 為什麼維護 fork

- 保留原作者持續更新的抽取器、技能規格與文件。
- 採 Windows-first 維護：Windows 11 + PowerShell 是主要開發、除錯與完整驗收環境。
- 公開入口改以繁體中文為主，英文鏡像放 `README.en.md`。
- 建立可重現的 Windows 開發 gate、Windows CI job，以及逐筆審查的上游追蹤。
- 避免 fork 誤把 MkDocs 部署到上游網域 `booktoskill.is-a.dev`。

**回貢判準：修的是上游的 bug 就送回去；這裡獨創的文件／Windows 維護骨架留在這裡。**

## 與上游的差異

| 項目 | 說明 |
|---|---|
| `README.md` / `README.en.md` | 繁中主檔 + 英文鏡像；不保留 `README.ru.md` 或其他語系 |
| `AGENTS.md` / `CLAUDE.md` | 本 fork 的 AI 維護單一真相源 |
| `NOTICE.md` / `FORK.md` | 來源、授權與同步說明 |
| `tools/dev_check.ps1` | Windows 本機一鍵 gate |
| `.github/workflows/ci.yml` | 新增 Windows pytest / ruff / SKILL 驗證 job |
| `.github/workflows/upstream-check.yml` | 每週對 `upstream/master` 做未審查 commit 檢查 |
| `.github/workflows/deploy-docs.yml` | 部署步驟僅在 `virgiliojr94/book-to-skill` 執行 |
| `docs/DECISIONS.md`、`docs/UPSTREAM.md`、`docs/DEVELOPMENT.md` | fork 維護文件，不列入 MkDocs nav |

產品 `SKILL.md`、`book_to_skill/`、`scripts/extract.py` 與選配抽取器行為以上游為準，除非有已記錄的 fork 修正。

## 分支與 remote

- `origin/master`：SanHsien 維護線。
- `upstream/master`：virgiliojr94 原始專案。
- 功能與修正使用短期分支；驗證通過後再合併到 `master`。

不要 `git push upstream`。同步方式見 [`docs/UPSTREAM.md`](docs/UPSTREAM.md)。

上游更新 `README.md` 時，把新內容併進 `README.en.md`，再把對應段落翻進 `README.md`。
不要把上游的第三語系 README 合回來。

## 換一台電腦怎麼開發

```powershell
git clone https://github.com/SanHsien/book-to-skill.git
cd book-to-skill
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install pytest ruff
pwsh -NoProfile -File tools\dev_check.ps1
.venv\Scripts\python scripts\extract.py --check
```

需要 PDF / EPUB 等格式時再裝 extra，例如：

```powershell
.venv\Scripts\python -m pip install -e ".[pdf,epub,docx]"
```
