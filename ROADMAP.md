# 路線圖

> 本 repo 後續工作的單一真相源。做完一項，就在同一個 commit 刪掉那一列；新工作只加在這裡。
> 現況段的數字是 2026-10-29 依 `main` `2a0dec474b64` 查的快照，開工前先重查 GitHub。

## 現況

本 repo 把技術書與文件抽取成按章載入的 Agent 技能；抽取以本機為主，但宿主模型可能送內容到雲端，technical mode 首次也可能下載模型，不能宣稱整體完全離線（`AGENTS.md:7-8,26-31`）。2026-10-29 快照 open PR、安全告警均為 0，CI、CodeQL、Dependency freshness、Deploy docs、Upstream check 最近結果為 success；issue 因停用而未查到（2026-10-29 `gh` 查詢，`2a0dec474b64`）。希伯來文章節與 sanitize 效能已採用；仍有鎖回收窄窗、特定旗標順序及 Docling 真實模型驗收條件（`docs/DECISIONS.md:485-490,515-522`；`.github/dependency-deferrals.json`）。

## 近期：可以直接動手

| 項目 | 為什麼 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 無：維持現狀 | 最新上游批次與安全過濾器等價驗證已完成，剩餘觀察項尚未滿足既定觸發條件 | 開工重查 `gh pr list --repo SanHsien/book-to-skill`、安全告警與 Actions；有實際回歸或下列條件成立再啟動 | 維護者 | 2026-10-29 `gh` 查詢；深掃上游審查報告（2026-10-28）〈檢查與結果〉；`docs/DECISIONS.md:485-490` |

## 中期：等條件成立再做

| 項目 | 觸發條件 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 增量審查 upstream/master | 超過 baseline 的 commit／PR／issue，或已審項目 head 改變 | `git fetch upstream master` 後執行 `python tools/check_upstream_updates.py --strict`；逐筆記錄取捨，Windows gate 與受影響格式測試通過才更新 baseline | Codex | `tools/upstream_baseline.json:2-8`；`AGENTS.md:48-57` |
| 修可選旗標吞掉輸入檔的順序問題 | 上游修正，或本 fork 呼叫端改成把旗標放在檔名前 | 先重現 `extract.py --install-missing book.pdf` 及 `--mode` 同類情境；驗證檔名不消失、合法模式與既有標準呼叫不變，相關 pytest 與 Windows gate 通過 | Codex | `docs/DECISIONS.md:489-490`；`book_to_skill/utils.py:957`；深掃報告（2026-10-26）〈觀察清單〉 |
| 封閉過期工作鎖回收的殘餘競態 | 出現並行回收實例，或正式需要原生 POSIX 並行支援 | 用兩個程序同步回收同一過期鎖，驗證只有一個持有者、輸出不覆寫；比較原子接手與 OS 鎖方案，Windows 及目標 POSIX 各實跑 | Claude Opus | `docs/DECISIONS.md:487`；`book_to_skill/utils.py:1414`；`9a95fbc`、`fc92bc8` |
| 重新評估 Docling 升版 | freshness 延後自動失效，或具備既有本機模型可完成 technical PDF 驗收 | 先查 release notes 與安全公告；以一份合法小型 PDF 走實際 StandardPdfPipeline，核對文字、表格及 fallback；無模型時記錄未驗，不宣稱不相容、不無限下載重試 | Codex | `.github/dependency-deferrals.json`；`docs/DECISIONS.md:366-388`；`AGENTS.md:70,95-106` |
| 評估 PDF 頁碼 sidecar | 上游 #307 合併，或維護者明確要求頁碼回溯 | 重讀 diff、定義公開旗標與輸出格式，驗證頁碼對應、無旗標時舊輸出不變；相關 PDF 測試、技能掃描與 Windows gate 通過 | Claude Sonnet | `docs/DECISIONS.md`〈2026-10-28〉的 #307／issue #306；`docs/UPSTREAM.md` 同日審查表 |

## 刻意不做

| 不做什麼 | 理由 | 什麼情況下重新考慮 |
| --- | --- | --- |
| 引進遠端 docling-serve、預設自動裝缺失套件或公開散布書籍產出 | 文件與安裝控制邊界見 `AGENTS.md:18-22`；上游 #308 與 issue #305 已審不採用 | 維護者明確變更相關邊界，並完成資料、授權與安裝風險評估 |
| 直接引進不存在的 pdf-inspector／resume／eval 子系統修補 | 本 fork 沒有對應層，不能當成本地未修缺陷；理由見 `docs/DECISIONS.md:436-438` 與 2026-10-28 條目 | 維護者要求新增該子系統，先評估整組依賴與驗收 |
| 為掃描轉綠新增廣泛抑制、把 SkillSpector 改從 PyPI 安裝或部署到上游網域 | 精準 baseline 綁內容，掃描器來源與 deploy 閘門已有決定；見 `docs/DECISIONS.md`〈2026-10-24〉、`AGENTS.md:20` | 掃描器來源或自有文件站有明確新需求，先定義安全與部署邊界 |

## 維護方式

每週依 upstream/master、baseline 與既有決策做增量審查；沒有共同祖先不改寫歷史，已審水位不表示所有功能已合併。
每月查依賴與安全告警；改抽取器須驗對應 extra／真實格式與 Windows gate，掃描指紋變動逐筆重審，不手改 release 產生的 CHANGELOG；其他文件只連結本路線圖。
