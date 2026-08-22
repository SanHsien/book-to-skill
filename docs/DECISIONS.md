# 維護決策

## 2026-08-22：建立 Windows-first 維護型 fork

**決定**：fork `virgiliojr94/book-to-skill`，保留 MIT 授權與完整歷史，預設分支維持 `master` 以降低與上游同步摩擦。本線聚焦繁中文件、Windows 開發 gate、Windows CI，以及逐筆審查的上游追蹤。

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
