# AGENTS.md

給 Codex、Claude Code、Cursor 與其他自動化代理在本專案工作時的指引。產品與使用方式先讀 [`README.md`](README.md)；開發與驗收細節見 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)。

## 專案定位

這是 [`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill) 的 MIT fork。
核心價值是把技術書與文件以**本機抽取為主**的流程拆成結構化 Agent 技能：核心索引 + 各章獨立檔，查詢時只按需載入對應章節。抽取器本身不會把文件上傳到本專案服務，但後續由 Copilot、Amp、Claude Code 等宿主 Agent 分析／生成技能時，內容是否送往雲端取決於該宿主與所選模型；technical mode 的 Docling 首次執行也可能下載模型，因此不要把整體流程概括成「完全離線」。

`origin` 是 `SanHsien/book-to-skill`（預設分支 `main`），`upstream` 是原作者 repo（預設分支 `master`）。
保留上游作者、MIT 授權與產品 `SKILL.md`。本 fork 的維護差異記在 [`FORK.md`](FORK.md) 與 [`docs/DECISIONS.md`](docs/DECISIONS.md)。

主要開發與完整驗收環境是 **Windows 11 + PowerShell**；Ubuntu CI 補跨平台相容性。

## 硬性邊界

- **不要覆寫產品 `SKILL.md`。** 根目錄 `SKILL.md` 是給 Copilot / Amp / Claude Code 安裝的轉換器規格，不是本 fork 的維護索引。維護規則以本檔為準。
- 不提交書籍、PDF、EPUB、產生出來的技能、API key、cookie 或帳號資料。
- 不把他人著作的產生技能公開散布；轉換器本身不附帶任何書籍內容。
- 不把 fork 的 MkDocs 部署到上游網域 `booktoskill.is-a.dev`（見 `docs/CNAME` 與 `deploy-docs.yml` 的 repo 閘門）。
- 不推送到 `upstream`。上游同步先跑 `python tools/check_upstream_updates.py`，逐筆審查後再 merge / cherry-pick；不盲目覆蓋 fork 文件與 Windows gate。
- 不新增 hosted backend、不上傳使用者文件、不把 `--install-missing yes` 變成預設自動裝套件。

## 技術與資料流

- Python 3.9+；核心抽取路徑可在沒有選配 extra 時處理純文字 / Markdown。
- `book_to_skill/`：套件本體（CLI、parsers、sanitize、utils）。
- `scripts/extract.py`：給技能與本機使用的抽取入口。
- `tools/validate_skill.py`、`tools/discovery_tax.py`、`tools/scan_generated_skill.py`：技能規格與效能工具。
- `tests/`：pytest。CI 另跑 ruff（E9+F）、smoke extraction、bandit、SKILL.md 驗證。
- 選配 extra：`html` / `epub` / `pdf` / `docx` / `rtf` / `technical` / `all`（見 `pyproject.toml`）。

## 開發原則

- 日常修改在 `main` 驗證後直接 `git push origin main`，不開 feature branch。Dependabot 或外部貢獻仍走 PR。
- 修 bug 先補可重現失敗測試，再做最小修正。
- 上游公開 CLI、`SKILL.md` 步驟與 examples 視為相容性契約。
- 不為了套格式而大改上游程式；Ruff 只閘 E9（語法）與 F（pyflakes）。
- 使用繁體中文回覆；使用者文件以繁中為主，公開入口只維護 `README.md` 與 `README.en.md`。
- 不要新增或恢復其他語言 README（例如 `README.ru.md`）。上游若加第三語系，記錄略過即可。
- 上游更新 README 時：新英文進 `README.en.md`，再把對應段落翻進 `README.md`。
- **不要手改 `CHANGELOG.md`。** 它由 git-cliff 在 release 時從 Conventional Commits 產生。
- PR 標題必須是 Conventional Commit（CI 會檢查）。
- **合併任何 PR 前先讀 diff**（包含 Dependabot 開的）：`gh pr diff <編號>`。CI 綠燈證明的是「測試沒紅」，不是「改了什麼、該不該進 `main`」——lockfile 的連鎖升級、transitive major、跨出宣告範圍的變更，只有讀 diff 看得到。核准或合併訊息要寫出讀到什麼、為什麼可接受。
- `REVIEW.md` 是風險快照，不是每個一般 bug 的流水帳。

## 上游處理

1. `git fetch upstream master`
2. `python tools/check_upstream_updates.py --strict`
3. 逐筆判斷是否與 fork 的繁中文件、Windows gate、deploy 閘門衝突。
4. 可同步的提交用 merge；只需要部分修正時 cherry-pick 或最小重做。
5. 跑 `pwsh -NoProfile -File tools\dev_check.ps1`
6. 採用／略過寫進 `docs/DECISIONS.md`，驗證後才推進 `tools/upstream_baseline.json`

Baseline 代表「已審查」，不代表「全部已合併」。

## 驗證

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install pytest ruff defusedxml
pwsh -NoProfile -File tools\dev_check.ps1
.venv\Scripts\python scripts\extract.py --check
```

改抽取器或 parsers 時，再依格式補對應 extra（例如 `pip install -e ".[pdf,epub]"`）與真實樣本。沒有實際跑過的格式，不要宣稱已支援在本機可用。

## 文件責任

- `README.md` / `README.en.md`：公開產品與 fork 入口。
- `FORK.md`：與上游的關係、差異、同步方式。
- `NOTICE.md`：授權與 attribution。
- `docs/UPSTREAM.md`：upstream remote 與審查清冊。
- `docs/DEVELOPMENT.md`：本機開發、Windows 抽取器、驗收指令。
- `docs/DECISIONS.md`：長期取捨。
- `docs/how-it-works.md`、`docs/usage.md`、`docs/install.md` 等：上游產品文件，翻譯或行為變更才動。
- `CONTRIBUTING.md` / `SECURITY.md`：沿用上游流程；安全問題走 GitHub private advisory。

## 對外邊界：PR 只打本 fork

- **PR、push、release 一律指向 `SanHsien/book-to-skill`。** 對上游 `virgiliojr94/book-to-skill` 開 PR、push 或發 release
  需要維護者在當次對話明確同意回貢；「fork 一份」「建開發環境」「比照其他 repo」都不是同意。
- 根因是機制不是粗心：`gh` 在 fork clone 的**預設 repo 就是上游**（`gh repo set-default --view` 會回
  `virgiliojr94/book-to-skill`），裸跑 `gh pr create` 必然打上去。每個 clone 先跑一次
  `gh repo set-default SanHsien/book-to-skill`。
- 開 PR 仍明寫 `gh pr create --repo SanHsien/book-to-skill --base <分支> --head <分支>`，並**讀輸出的 URL**，
  owner 必須是 `SanHsien`。不是就立刻 `gh pr close` 留言道歉說明，再對 origin 重開。
- 2026-08-22 一天內兩個工作階段各誤開一個上游 PR（`lidge-jun/opencodex#2373`、
  `hamanpaul/paulsha-cortex#787`）。批次跑多個 repo 時最容易略過確認，而那正是兩次出事的場合。

## 依賴新鮮度：紅燈的兩條正當出口

每月的依賴新鮮度檢查比對的是**宣告**與現行版。當某個下限**不該**跟著現行版走時，只有兩種
留下理由的做法：

- **維持宣告**：在宣告那一行加 `# freshness-hold: <理由>`。用於長期政策（例如矩陣還有舊
  Python、或這個下限就是我們要的）。
- **已延後**：在 `.github/dependency-deferrals.json` 加
  `{"deferredLatest": "<當時看到的版本>", "reason": "<為什麼這次不升>"}`。PyPI 一超過該版本，
  延後自動失效、報告恢復提醒——所以不會變成永久靜音。沒有 `deferredLatest` 的條目直接忽略。

**不要用調高下限的方式讓紅燈消失**：宣告是相容性承諾，不是消音鍵。
