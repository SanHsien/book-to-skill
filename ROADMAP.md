# 路線圖

> 本 repo 後續工作的單一真相源。做完一項，就在同一個 commit 刪掉那一列；新工作只加在這裡。
> 現況段的數字是 2026-11-21 依 `main` `283f4a7` 查的快照，開工前先重查 GitHub。

## 現況

本 repo 把技術書與文件抽取成按章載入的 Agent 技能；抽取以本機為主，但宿主模型可能送內容到雲端，technical mode 首次也可能下載模型，不能宣稱整體完全離線（`AGENTS.md:7-8,26-31`）。2026-11-21 快照（`main` `283f4a7`）：open PR 0、Dependabot 與 code scanning open alert 0；CI、CodeQL、Deploy docs 在 `283f4a7` success；`Upstream check` 最近一次（`f0e115a`）failure。2026-11-20 增量審查（`2b2e787..53b2bd9`，[`REVIEW.md`](REVIEW.md)）的 F-01～F-03、H-01～H-02 已修並推上 main：過期鎖回收改由 OS 檔案鎖序列化（`2678def`）、RTF `\ucN` 與 fallback 跳過（`514c6b6`、`c00c85b`）、DOCX 定位點不輸出 Tab（`77f3da7`）、Part 編號解析（`e32ba5b`）、選配解析器 CI job 釘整棵依賴並在安裝後核對（`463feda`、`4e0179c`、`283f4a7`）。上游 2026-11-19 發布 v2.0.0／v2.0.1，baseline `e7bb659` 後 40 個 commit、PR 15 筆（#331 之後）、issue 6 筆（#330 之後）未審（`python tools/check_upstream_updates.py --strict`，2026-11-21 exit 1），其中 v2.0 的 Search & Read 遠端 MCP 模式碰到「不上傳文件」與著作權邊界；PR #327、#331 已合併，頁碼 sidecar 那列的觸發條件成立。仍未驗收：Docling 真實模型、以真實 Word 檔驗 F-02／F-03（`REVIEW.md`「尚未宣稱範圍」）。

## 近期：可以直接動手

| 項目 | 為什麼 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 增量審查 upstream/master（上游 v2.0.0／v2.0.1） | 觸發條件已成立：baseline `e7bb659` 後 40 個 commit、PR 15 筆、issue 6 筆未審（2026-11-21 `check_upstream_updates.py --strict` exit 1）。v2.0 新增的 Search & Read 遠端 MCP 模式（`book_to_skill/remote/`，例如 `a3fd262` 對齊 libgen-mcp）要先對照 `AGENTS.md:18-22` 的邊界與「刻意不做」第一列再決定；同批還有 PDF／DOCX／RTF／Markdown 抽取修正（#332、#333、#335、#336、#351、#352） | `git fetch upstream master` 後執行 `python tools/check_upstream_updates.py --strict`；逐筆記錄取捨，Windows gate 與受影響格式測試通過才更新 baseline | Codex | `tools/upstream_baseline.json:2-8`；`AGENTS.md:48-57`；`python tools/check_upstream_updates.py --strict` |
| 評估 PDF 頁碼 sidecar | 觸發條件已成立：上游 #327、#331 已於 2026-11-19 合併，issue #326、#330 已關閉；與上一列的增量審查一起做 | 重讀 diff、定義公開旗標與輸出格式，驗證頁碼對應、無旗標時舊輸出不變；相關 PDF 測試、技能掃描與 Windows gate 通過 | Claude Sonnet | `docs/DECISIONS.md`〈2026-11-09〉的 #307／#327／#331；`tools/upstream_baseline.json` 的 `monitored` |

## 中期：等條件成立再做

| 項目 | 觸發條件 | 驗收方式 | 建議執行者 | 證據 |
| --- | --- | --- | --- | --- |
| 修可選旗標吞掉輸入檔的順序問題 | 上游修正，或本 fork 呼叫端改成把旗標放在檔名前 | 先重現 `extract.py --install-missing book.pdf` 及 `--mode` 同類情境；驗證檔名不消失、合法模式與既有標準呼叫不變，相關 pytest 與 Windows gate 通過 | Codex | `docs/DECISIONS.md:489-490`；`book_to_skill/utils.py:984`（`parse_arguments`）；深掃報告（2026-10-26）〈觀察清單〉 |
| 重新評估 Docling 升版 | freshness 延後自動失效，或具備既有本機模型可完成 technical PDF 驗收 | 先查 release notes 與安全公告；以一份合法小型 PDF 走實際 StandardPdfPipeline，核對文字、表格及 fallback；無模型時記錄未驗，不宣稱不相容、不無限下載重試 | Codex | `.github/dependency-deferrals.json`；`docs/DECISIONS.md:366-388`；`AGENTS.md:70,95-106` |
| 以真實 Word 產生的檔案驗收 RTF `\uc2` 與 DOCX 自動目錄修正 | 取得可合法使用、由 Word 產生的 `\uc2`（雙位元組字碼頁）RTF 與含自動目錄的 docx，或使用者回報這兩種輸入仍有雜字／多餘 Tab | 以真實檔案跑抽取，確認無 PUA／U+FFFD／半形片假名雜字、目錄段落無開頭 Tab；不成立就先補紅燈測試再修；結果記回 `REVIEW.md`「尚未宣稱範圍」 | 維護者 | `REVIEW.md`「尚未宣稱範圍」第 1 點；`514c6b6`、`c00c85b`、`77f3da7` |
| 評估 PDF 大綱章節偵測 | 有書的章節偵測因 PDF 大綱可用而在本 fork 實測失準，或維護者要求 | 先在合法小型 PDF 重現編號圖說被誤判成章節；只取 `parsers/pdf.py` 與 `utils.py` 的大綱路徑，不引進 `pdf_inspector_integration.py`；先紅後綠，Windows gate 通過 | Claude Sonnet | `docs/DECISIONS.md`〈2026-11-09〉的 `182e185`（#315） |

## 刻意不做

| 不做什麼 | 理由 | 什麼情況下重新考慮 |
| --- | --- | --- |
| 引進遠端 docling-serve、預設自動裝缺失套件或公開散布書籍產出 | 文件與安裝控制邊界見 `AGENTS.md:18-22`；上游 #308 與 issue #305 已審不採用 | 維護者明確變更相關邊界，並完成資料、授權與安裝風險評估 |
| 直接引進不存在的 pdf-inspector／resume／eval 子系統修補 | 本 fork 沒有對應層，不能當成本地未修缺陷；理由見 `docs/DECISIONS.md:436-438` 與 2026-10-28 條目 | 維護者要求新增該子系統，先評估整組依賴與驗收 |
| 為掃描轉綠新增廣泛抑制、把 SkillSpector 改從 PyPI 安裝或部署到上游網域 | 精準 baseline 綁內容，掃描器來源與 deploy 閘門已有決定；見 `docs/DECISIONS.md`〈2026-10-24〉、`AGENTS.md:20` | 掃描器來源或自有文件站有明確新需求，先定義安全與部署邊界 |

## 維護方式

每週依 upstream/master、baseline 與既有決策做增量審查；沒有共同祖先不改寫歷史，已審水位不表示所有功能已合併。
每月查依賴與安全告警；改抽取器須驗對應 extra／真實格式與 Windows gate，掃描指紋變動逐筆重審，不手改 release 產生的 CHANGELOG；其他文件只連結本路線圖。
