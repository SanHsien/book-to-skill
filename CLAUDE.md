# CLAUDE.md

請先完整閱讀並遵守 [`AGENTS.md`](AGENTS.md)。本檔只補充 Claude Code 的最小入口：

- 這是保留上游歷史的 fork；不要移除 `upstream`、原作者或 MIT 授權標示。
- 根目錄 `SKILL.md` 是產品轉換器規格，不要改寫成本 fork 的維護索引。
- 修改抽取器、parsers 或技能規格前，先跑對應 pytest；提交前跑
  `pwsh -NoProfile -File tools\dev_check.ps1`。
- 書籍、產生技能、本機輸出一律不可提交。
- 不要啟用或繞過 `deploy-docs.yml` 對本 fork 的閘門；文件站仍屬上游。
- 使用繁體中文，直接交付可驗證結果，避免冗長背景鋪陳。
