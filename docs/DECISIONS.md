# 維護決策

## 2026-09-11：上游批次審查，採用一個可重現的缺陷修正，其餘延後或略過

**決定**：

- **採用** 上游 open PR #208（`fix(deps): honor alternative parser availability`，cherry-pick
  `b3891d8`）。本 fork 的 `prepare_dependencies()` 呼叫 `offer_dependency_install()` 給
  PDF／HTML 時沒有帶 `any_of_modules=True`，即使 `pypdf` 或 `trafilatura` 已可用，仍會提示安裝
  `pdfminer.six` 或漏掉 `trafilatura` 的存在判斷。這是本 fork **實測重現**的缺陷（stub
  `python_module_available` 只放行 `pypdf`，`prepare_dependencies(".pdf", "text", "yes")`
  仍呼叫 `install_python_packages(["pdfminer.six"])`），套用修正後同一測試不再觸發安裝。符合
  「open PR 只在修到本 fork 實際有的缺陷才採用」的門檻。
- **延後至合併，並附誤報證據** 上游 open PR #214（`sec: harden prompt-injection protection`）。
  它補的缺口是真的：既有 `prompt.ignore_previous` 只認 previous／prior 兩種受詞，
  ignore／disregard 搭配 above／following 的變形認不出來，也沒有 assistant 角色偽前綴規則。但同一個
  PR 另外三條規則的精確度不足以放進會擋流程的掃描器：`tools/scan_generated_skill.py` 任何 finding
  都回 exit 1，而 SKILL.md Step 9.5 規定非零就停下交人審。實測一份普通的測試主題章節（三句
  "you should／must／need to"、一個延伸閱讀網址、一個 40 位 commit SHA）與一行 "Use this skill
  when you need to..." 的 SKILL.md：未套用前 exit 0，套用 #214 後 6 筆 finding、exit 1——
  `prompt.ai_directive` 對書中常見的第二人稱建議句全數命中，`prompt.raw_url` 命中引用網址，
  `prompt.encoded_blob` 命中 commit SHA。幾乎每本書產生的 skill 都會被擋，警告因此失去意義。
  曾先 cherry-pick 在本機（未推送），驗證後移除。**觸發條件**：上游合併時重看最終 diff；若三條
  高誤報規則仍在，只以最小重做引入 `prompt.ignore_instructions` 與 `prompt.fake_assistant_prefix`
  兩條高精確度規則與其測試。
- **不採用（已涵蓋）** upstream commit `4117064`（PR #199 落地，俄文 `Глава N` 章節偵測）：
  本 fork 已於 2026-08-31 用**最小自製實作**採用同一個 PR（commit `5f523d8`），regex 與
  行為（大小寫不敏感、Markdown 前綴、拒絕 "В этой главе"/"Главная" 等變形）等價，只是註解較短、
  測試合併成一條。不是「跳過」，是先前已引用；比對測試斷言確認等價覆蓋。
- **不採用** `907be50`（Hermes Agent host discovery，PR #202 落地）：延續 2026-08-31 的判斷，
  內容未變（README/README.ru.md/SKILL.md/docs 的 host 擴張，本 fork 沒有 Hermes 的可驗證契約）。
- **不採用** `67f52fd`（pdf-inspector smart routing，PR #203 落地）：新增必要／選配相依套件
  `pdf-inspector>=1.15,<2`（Firecrawl 發布），改變 PDF 抽取的信任邊界（`_MIN_NATIVE_CONFIDENCE`
  門檻通過時完全略過既有 pdftotext/pypdf/pdfminer 鏈）。這是供應鏈信任決策，本 fork 沒有
  對這個套件的審查依據，**留給維護者決定**是否要引入這個新的執行期依賴；不阻塞其他項目。
- **不採用** `4f1ca4d`（eval 檔案排序穩定化，PR #200 落地）：實測確認本 fork 沒有 `tests/evals/`
  目錄，延續「本 fork 不跑那套 eval」的既有判斷。
- **不採用** `3398180`（CI SHA pin 加版本註解＋codeql-action pin，PR #198 落地）：本 fork 的
  `.github/workflows/ci.yml`／`codeql.yml` 已與上游分岔（`main` 分支、Windows gate job、
  自己的 SHA pin 慣例），不共用這些檔案，延續既有判斷。
- **不採用** `a6cad12`（新增簡體中文 README，PR #204 落地）：只新增第三語系 `README.zh-CN.md`
  並更新 `README.md`／`README.ru.md` 的語系切換連結；本 fork 公開文件只維護繁中
  `README.md` 與 `README.en.md`，延續 2026-08-22 的第三語系政策。
- **延後至合併**（open PR，非本 fork 缺陷）：
  - #206 Greek `Κεφάλαιο N`、#212 Tamil `அத்தியாயம் N` 章節偵測——與已採用的俄文／希臘文同型、
    自足且有回歸測試，但**還是 open PR**，不是缺陷修正（缺少某語言偵測不算本 fork 的
    demonstrable 缺陷），比照既有政策等上游合併再一次審查。
  - #209 OpenClaw、#216 Opencode host discovery——與 Hermes（#202）同形狀：改
    `README.md`／`README.ru.md`／`README.zh-CN.md`／`SKILL.md` 的 host 探索表，本 fork 對
    這些 host 沒有可驗證契約，且 SKILL.md 的 host 表已因拒絕 Hermes 而分岔。
  - #210 project-local skill path scope 選擇——修改 `SKILL.md` Step 5 的目的地選擇邏輯，是
    product-direction 功能而非缺陷，且該區塊已因 Hermes 拒絕而分岔，比照 #157/#170 的既有
    判準：等上游合併定案再讀 diff。
  - #211 grounding/fidelity gate（Step 9.5b `tools/ground_check.py`）——設計完整、有回歸測試、
    不動 host 表，是本次批次品質最高的一個，但仍是**新功能**（在生成流程中新增強制關卡）而非
    修本 fork 的缺陷，且會改變 Step 7／Step 9.5 之間的產出契約。延後至合併；**建議維護者優先
    複審**，其防禦的失效模式（一次性生成把 worked example 或分類數量從記憶填入而非來源文字）
    與本 fork 已有的 prompt-injection 掃描精神一致。
  - #215 cue-omni-reader 文件——推薦以 skills CLI 安裝第三方 `sensedeal/cue-skills` 套件中的
    cue-omni-reader skill（作者自述「may bill」）。
    純文件變更但引入對外部未審查套件的信任建議，**留給維護者決定**是否採用，不阻塞其他項目。
  - #213 dependabot 群組更新 `codeql-action` pin——只動上游自己的 `codeql.yml`，本 fork 不共用
    該檔案，延續 3398180 的判斷。
- **記錄備查，無需動作**：issue #205（OpenClaw 相容性請求，即 #209 的動機，判斷同上）、issue
  #207（dependency preflight 缺陷，已由採用的 #208 解決）。

**PR／issue 水位**：`reviewed_pr_through` 202 → 216；`reviewed_issue_through` 192 → 207。
commit 水位：`9c207f87` → `a6cad12dee07a7700068e2aa51cba871ef3b5349`（upstream/master tip）。

## 2026-08-31：採用俄文章節標題，拒絕未分割的 host／governance 擴張

**決定**：以最小 regex 與回歸測試採用上游 PR #199 的 `Глава N` 偵測；#200–#202 不採用，
PR 審查水位推至 #202。

**理由**：#199 自足、無新依賴，且誤判邊界可由 prose 測試固定。#200 是未啟用 eval，#201 把
多項 CI/安全/產品行為混在一起，#202 則需 Hermes 的 discovery/trust 實機證據並違反本 fork 語系政策。

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

**理由**：上游抽取器與 `SKILL.md` 規格已經可用，且解析完全在本機離線執行，符合維護者把技術書裝進 Agent、又不要每次丟整本 PDF 的需求。缺的是 Windows 11 上可重現的開發／驗收骨架，以及繁中入口。直接用上游 repo 難以長期記錄 fork 取捨。

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

## 2026-08-29：上游檢查補上 PR 與 issue 兩個面向

**決定**：`check_upstream_updates.py` 補上以 `--state all` 收集上游 PR／issue 的邏輯，
`upstream-check.yml` 補 `GH_TOKEN: ${{ github.token }}`，新增 `tests/test_upstream_updates.py`。
Baseline 既有的水位不動。

**理由**：`docs/UPSTREAM.md` 早就寫著「四個面向都要看」，`upstream_baseline.json` 也記著
`reviewed_pr_through` 與 `reviewed_issue_through`——但**沒有任何程式讀那兩個欄位**，檢查器只比對
commit 水位。那兩個面向不是「查過沒發現」，是根本沒查，而每週的排程報告長得跟查過一樣綠。
這是艦隊層級的問題：24 個 fork 裡 21 個都這樣（`SanHsien/repo-fleet-ops` 的 `docs/INCIDENTS.md`
第十條）。參考實作是 `SanHsien/harness-guard`。

三個性質，缺一不可：

- **`--state all`**：只查 `open` 看不到「開了又關、沒有合併」的 PR，而那正是「上游拒收、但可能對
  本 fork 有價值」的一類——已合併的遲早會經由 commit 抵達，被關掉的永遠不會。
- **`gh` 失敗時回 `None` 不回 `[]`**，報告寫 `Not checked` 並 **fail closed**（exit 2）。
  「沒查到」和「沒有」在綠色報告裡長得一樣，只有一個是真的。
- **`GH_TOKEN`**：`gh` 在 Actions 裡沒有憑證就列舉不到，配上 fail closed 會讓紅燈的意思變成
  「檢查器壞了」而不是「上游有東西」。

**證據**：落地後實跑 `python tools/check_upstream_updates.py`，三個面向都印出水位與待辦數；
本 repo 的 gate 全綠。

**已知代價**：水位以上真的有東西時，每週的 upstream-check 會回 exit 1。那是它該做的事——先前的
綠燈不是「沒有待辦」，是沒有人看。

**觸發條件**：報告列出項目時逐筆讀 diff、把採用／略過理由寫進本檔，然後才推進 baseline 的水位。

## 2026-09-06：文件 parser 與 SkillSpector gate 採可重現版本

**決定**：會處理不可信文件的 optional parser 固定為 `pypdf==6.17.0`、
`pdfminer.six==20260107`、`python-docx==1.2.0`、`docling==2.126.0`。
`pdfminer.six` 與 `docling` 加 Python 3.10+ 環境 marker；基礎套件與 `pypdf` 仍支援 Python 3.9。
SkillSpector 固定到 SanHsien fork 的精確 commit，canonical gate 以明確 Python
直譯器啟動，不依賴 PATH 上偶然存在的 console script。

**完整性契約**：任一適用 analyzer 的 partial、skipped、unaccounted 或未解釋 failed
都失敗。PNG/JPG/WEBP 被掃描器明確記為 `binary_content/out_of_scope` 時，僅在每個
failed 計數都能一對一對應到該 scope exclusion 時接受；不把它當成已掃描文字內容。
gate 另核對釘定 `--no-llm` revision 的 24 個 analyzer ID，缺少或多出任何 ID 都失敗。
頂層只有在 100% 元件完整檢查時才可通過；掃描器把一般文字誤判成路徑而產生的 nonfatal
`reference_unresolved` 可保留 `partial`，但每個 ledger source-line key 必須與
`references` 中的 missing/partial key set 完全一致，其他 exception 一律失敗。

**2026-09-07 pin 修正**：pin 從 `70cd263` 前進到 `185d610`。舊 revision 尚未支援
`SKILLSPECTOR_MAX_STATIC_SECONDS`／`SKILLSPECTOR_MAX_WORKFLOW_SECONDS`，fresh Windows
runner 因而仍在預設 60 秒 graph budget 停止；本機的 editable SkillSpector source 則已是新版，
讓先前本機 gate 無法揭露差異。新 revision 已確認位於 `SanHsien/SkillSpector` 遠端 main，且
該 SHA 的 CI、CodeQL、Scorecard 全綠。

**2026-09-12 pypdf 前進**：`pypdf==6.17.0` → `6.18.1`（上方決定句保留原始版本作為紀錄）。
6.18.0 限制 indirect object token 長度，6.18.1 限制 TrueType／Type1 字型 `/Widths` 條目數與
`parse_bfchar` token 長度，都是處理不可信 PDF 的 DoS 上限，正是本 pin 要跟的東西。6.18.0 要求
覆寫過預設上限的使用者改用新設定方式；本 repo 沒有覆寫任何 pypdf 上限。全測試通過，並以手工
兩頁 PDF 經 `extract_with_pypdf` 與 `count_pages` 實際抽出兩個章節標題。

**產品文字調整**：只把會讓 bounded shell parser 把 Markdown code span 誤當成未閉合
shell 語句的路徑表示改為等義 HTML code 或一般敘述；轉換流程、覆寫確認與發布邊界不變。
發布說明中的 `npx skills` 固定為 npm 當前查得的 `skills@1.5.23`，避免未鎖版 CLI
rug-pull 風險。安全回歸測試仍保留 prompt injection 與 `.env` 外傳樣本；這些刻意的
惡意 fixture 只用逐筆精確 fingerprint 接受，不改成漂移式 glob。
