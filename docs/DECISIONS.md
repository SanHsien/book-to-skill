# 維護決策

## 2026-08-22：本線預設分支改 `main`，日常直接推

**決定**：`origin` 預設分支從 `master` 改為 `main`，與其他 SanHsien 維護 fork 一致。日常修改在本機跑 `tools\dev_check.ps1` 後直接推 `origin/main`，不開 feature branch。Dependabot 與外部貢獻仍走 PR，合併前讀 diff。

**上游**：`upstream` 仍是 `master`。同步繼續 `git fetch upstream master`，不要把上游預設分支改名，也不要 `git push upstream`。

**理由**：對齊 video-autopilot-kit 等本線習慣。本 fork 的 CI 聽 `main`；deploy-docs 的實際部署閘門仍只允許上游 repo 的 `master`。

## 2026-08-22：關閉可修的 review findings（不回貢）

**決定**：在本 fork 修 R-01～R-05、R-07、R-08。不送上游。

- Windows 預設工作目錄改 `%LOCALAPPDATA%\book-to-skill\work`。
- DOCX zipfile 解析改 `defusedxml`（必要依賴）。
- `.gitignore` 擋電子書與根目錄抽取產出。
- `CONTRIBUTING.md` / `docs/install.md` / `SECURITY.md` 標明本 fork 與上游分流。
- `--mode technical` 明確警告可能外連；不假裝已驗證 docling 離線。
- CodeQL action 改 SHA pin。

## 2026-08-22：公開文件只保留繁中與英文

**決定**：刪除 `README.ru.md`。公開入口只維護 `README.md`（繁體中文）與 `README.en.md`（英文）。上游若再加其他語言 README，本 fork 不採用。

**理由**：本線的使用者文件契約是繁中為主、英文鏡像。第三語言會讓語言切換、真相源與同步成本失控（俄文頁仍把英文 `README.md` 當 canonical，與本 fork 已不符）。產品 `SKILL.md` 與上游 `docs/*.md` 維持英文原文，不另開語系檔。

## 2026-08-22：建立 Windows-first 維護型 fork

**決定**：fork `virgiliojr94/book-to-skill`，保留 MIT 授權與完整歷史。當時預設分支先跟上游用 `master`；後來本線改 `main`（見上）。本線聚焦繁中文件、Windows 開發 gate、Windows CI，以及逐筆審查的上游追蹤。

**理由**：上游抽取器與 `SKILL.md` 規格已經可用，且解析完全在本機離線執行，符合主人把技術書裝進 Agent、又不要每次丟整本 PDF 的需求。缺的是 Windows 11 上可重現的開發／驗收骨架，以及繁中入口。直接用上游 repo 難以長期記錄 fork 取捨。

**限制**：

- 不把 fork 包裝成原創專案，不移除原作者與贊助連結。
- 根目錄 `SKILL.md` 保持產品規格，不用維護索引覆寫。
- 不部署 MkDocs 到 `booktoskill.is-a.dev`。
- 上游更新必須逐筆審查。

## 2026-08-22：deploy-docs 只允許上游 repo 部署

**決定**：`.github/workflows/deploy-docs.yml` 的 gh-pages 部署步驟加上
`github.repository == 'virgiliojr94/book-to-skill'`。本 fork 仍可在 PR 上 build MkDocs 做檢查，但不推 site、不碰上游 CNAME。

**理由**：`docs/CNAME` 是 `booktoskill.is-a.dev`。fork 若原樣 `mkdocs gh-deploy --force`，會把 SanHsien 的 GitHub Pages 指到別人的網域，或至少發布一份不該由本 fork 托管的站。

## 2026-08-22：不啟用 Dependabot 自動合併

**決定**：Dependabot 只開 PR；CI 與人工讀 diff 通過後才合併。

**理由**：選配抽取器（pypdf、docling、trafilatura 等）會改變解析品質與 Windows 安裝體積，不適合自動合併。
