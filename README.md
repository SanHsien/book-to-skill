<p align="center">
  <img src="docs/assets/banner.webp" alt="Booklin，book-to-skill 的巫師吉祥物，捧著一本散成星點、再收成有序格線的書" width="100%">
</p>

<h1 align="center">book-to-skill</h1>

<p align="center">
  <a href="README.md"><strong>繁體中文</strong></a> ·
  <a href="README.en.md">English</a>
</p>

<p align="center">
  <strong>把技術書、文件資料夾或一組來源，轉成可按需載入的 Agent 技能 — 給 GitHub Copilot CLI、Amp 與 Claude Code 在工作中直接查、直接用。</strong>
</p>

<p align="center">
  <a href="https://github.com/SanHsien/book-to-skill/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SanHsien/book-to-skill/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/Agent_Skills-Open_Standard-blueviolet?style=for-the-badge" alt="Agent Skills 標準">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="支援格式">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
  <a href="https://github.com/sponsors/virgiliojr94"><img src="https://img.shields.io/github/sponsors/virgiliojr94?style=for-the-badge&color=ea4aaa&logo=githubsponsors&logoColor=white" alt="Sponsor"></a>
</p>

> **這是 [`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill) 的 Windows-first 維護型 fork**，沿用 MIT License 與完整 Git 歷史。產品行為跟隨上游；本維護線補上繁中文件、Windows 開發／驗收 gate，以及逐筆審查的上游追蹤。差異見 [`FORK.md`](FORK.md)，同步策略見 [`docs/UPSTREAM.md`](docs/UPSTREAM.md)。

<p align="center">
  <a href="#為什麼需要">為什麼需要</a> ·
  <a href="#會產出什麼">會產出什麼</a> ·
  <a href="#不只是書">不只是書</a> ·
  <a href="docs/how-it-works.md">運作方式</a> ·
  <a href="docs/usage.md">用法</a> ·
  <a href="docs/install.md">安裝</a> ·
  <a href="docs/faq.md">FAQ</a> ·
  <a href="docs/performance.md">效能</a> ·
  <a href="docs/architecture.md">架構</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <strong>回答單一問題時，Token 用量可比把整本書丟進上下文少 24×–51×</strong>（以真實書籍量測，<a href="docs/performance.md#the-discovery-loop-tax">量測方法</a>）。
</p>

**三步看懂：**

1. **指向**檔案、資料夾或 glob — `/book-to-skill ./my-book.pdf`
2. **它抽結構** — 框架、決策規則、反模式，以及各章獨立檔。是結構，不是摘要。
3. **Agent 按需載入** — 問 `/my-book replication` 時只讀對應章節，用原文回答，不靠幻覺補洞。

---

## 為什麼需要

<img align="right" width="200" src="docs/assets/booklin.png" alt="Booklin — book-to-skill 吉祥物，紫色巫師捧著一本書">

你買了一本很好的技術書。讀完一次。三個月後，第七章存在過這件事你已經想不起來。

常見替代方案幫不上忙：

- 搜 PDF → 得到頁碼清單，不是答案
- 問 Agent「這本書怎麼說」→ 它要嘛幻覺，要嘛說沒有這份內容
- 邊讀邊做筆記 → 最後得到一份 200 行、再也不打開的文件

**book-to-skill 把書轉成 Agent 可按需載入的結構化技能。**

裝好之後，輸入 `/your-book-slug replication`，Agent 會讀對應章節、依實際內容回答。不用翻 PDF，也不用把整本書每次都塞進對話。

任何支援開放 [Agent Skills](https://github.com/agentskills/agentskills) 標準的宿主都能用同一份 `SKILL.md`：GitHub Copilot CLI、Amp、Claude Code。

---

## 會產出什麼

執行 `/book-to-skill your-book.pdf`（也可以是資料夾、glob 或檔案清單）後，會在 Agent 的 skills 目錄寫入完整技能（Copilot CLI：`~/.copilot/skills/<slug>/`；Amp／跨 Agent：`~/.agents/skills/<slug>/`；Claude Code：`~/.claude/skills/<slug>/`）：

| 檔案 | 用途 | 大約大小 |
|------|------|----------|
| `SKILL.md` | 核心心智模型 + 章節目錄 | ~4,000 tokens |
| `chapters/ch01-*.md` … | 每章一個檔，按需載入 | 各 ~1,000 tokens |
| `glossary.md` | 關鍵詞彙，依字母排序並標章節 | ~1,500 tokens |
| `patterns.md` | 技法、演算法、設計模式 | ~2,000 tokens |
| `cheatsheet.md` | 決策表與速查規則 | ~1,000 tokens |

**章節檔是按需載入的** — 你沒問到的章節，不佔這次技能預算。

---

## 不只是書

名字叫 book，輸入其實是任何有結構的長文。你會反覆重讀的知識都適用：

- **內部文件** — ADR、runbook、onboarding。把整個 `docs/` 收成一個技能，寫程式時直接問。
- **品牌與設計系統** — 語氣、元件原則。把 60 頁品牌手冊變成可查的技能，而不是每次掃 PDF。
- **研究叢集** — 一疊論文加上自己的筆記，合併成單一技能，有新材料再 fold-in（見 [Update / fold-in](docs/usage.md)）。
- **規格與標準** — RFC、API contract、合規文件。

只要你常重開一份文件、希望自己早該記住它，它就是候選。

---

## Discovery Loop Tax

讀 PDF 的 Agent 不只是在讀 — 它在**導航**：每輪重新抓目錄、回溯、再處理一遍。book-to-skill 把結構化成本付在**轉換當下一次**，之後查詢成本跟答案成正比，而不是跟整本書成正比。

完整方法、數字與各書表格 → [`docs/performance.md`](docs/performance.md#the-discovery-loop-tax)

---

## 運作方式

兩半：決定性的 Python **抽取器**（文件 → 乾淨文字 + metadata），以及規格驅動的 **產生器**（Agent 依本 repo 的 `SKILL.md` 把抽取結果編成技能）。章節檔按需載入，讓常駐技能保持精簡。

完整流程（Steps 0–10、抽取模式、token 預算）→ [`docs/how-it-works.md`](docs/how-it-works.md)

---

## 用法

`/book-to-skill <path|folder|glob> [skill-name]`，另外還有只分析、從既有分析產生、以及更新／fold-in。轉換後可把技能發到 GitHub（預設私人），讓其他宿主用 `npx skills add` 安裝。

所有模式與範例 → [`docs/usage.md`](docs/usage.md)

實務案例 → [use cases](https://github.com/virgiliojr94/book-to-skill-use-cases)（上游維護的索引）。

---

## 安裝

本 fork 建議直接 clone 到 skills 目錄（Windows 用 PowerShell）：

```powershell
git clone https://github.com/SanHsien/book-to-skill.git $HOME\.claude\skills\book-to-skill
# Copilot CLI：$HOME\.copilot\skills\
# Amp / 跨 Agent：$HOME\.agents\skills\
```

官方一鍵安裝（上游）：

```bash
npx skills add virgiliojr94/book-to-skill
```

獨立 CLI（只裝抽取引擎，**不會**註冊 `/book-to-skill` 技能）：

```powershell
python -m pip install "book-to-skill[pdf,epub,docx] @ git+https://github.com/SanHsien/book-to-skill.git"
python -m book_to_skill --check
```

所有宿主、選配抽取器與 CLI 細節 → [`docs/install.md`](docs/install.md)  
本機開發與 Windows 驗收 → [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)

---

## FAQ

常見問題：為什麼不直接丟 PDF、費用、隱私、非書籍輸入、多檔書籍。

答案 → [`docs/faq.md`](docs/faq.md)

---

<details>
<summary>🔧 <strong>需求與抽取器</strong></summary>

抽取器依格式依序嘗試，用第一個可用的工具。沒裝任何東西時，它會告訴你該跑哪條安裝指令。純文字、Markdown、reStructuredText、AsciiDoc 不需要額外依賴。

一次檢查環境：

```powershell
python scripts\extract.py --check
```

**PDF — 依書籍類型選工具：**

| 書籍類型 | 工具 | 安裝 | 速度 |
|----------|------|------|------|
| 以文字為主（散文、少表格） | `pdftotext`（poppler） | Windows：`winget install oschwartz10612.Poppler` 或 `choco install poppler`；Linux：`sudo apt install poppler-utils` | 極快 |
| 文字為主備援 | `pypdf` | `python -m pip install pypdf` | 極快 |
| 文字為主備援 | `pdfminer.six` | `python -m pip install pdfminer.six` | 極快 |
| **技術書（程式碼、表格、公式）** | **`docling`** | `python -m pip install docling` | 約 1.5s/頁 |

掃描版 PDF 必須先 OCR。沒有文字層的影像 PDF，抽取器會在前幾頁檢查後立刻停止，而不是空轉整本書。可先自行 OCR 再轉換：

```bash
ocrmypdf input.pdf output.pdf
```

**EPUB：** `ebooklib` + `beautifulsoup4`（最佳）或標準庫 `zipfile`（免安裝備援）。

**其他格式：** DOCX（`python-docx`）、HTML（`beautifulsoup4`）、RTF（`striprtf`）、MOBI/AZW（需安裝 [Calibre](https://calibre-ebook.com/download) 的 `ebook-convert`）。

</details>

---

## 這個 fork 額外提供什麼？

- **繁體中文為主的公開入口**：`README.md` 是中文主檔，英文鏡像在 `README.en.md`。
- **Windows-first 開發環境**：PowerShell `tools\dev_check.ps1`、venv 指令、CI 的 Windows job。
- **上游追蹤**：每週檢查 `virgiliojr94/book-to-skill` 的 `master`，有未審查 commit 就讓 workflow 失敗。
- **Agent 維護規則**：`AGENTS.md` 是單一真相源；`CLAUDE.md` 只補 Claude Code 入口。
- **不部署上游文件站**：fork 不會把 MkDocs 推到 `booktoskill.is-a.dev`。

產品抽取器、`SKILL.md` 規格與選配格式支援仍以上游為準。

---

## 著作權與合理使用

book-to-skill **不附帶任何書籍內容**。它是轉換器，你指向自己已經擁有的檔案。

- **抽取在本機；分析／技能生成取決於 Agent 宿主。** 這個專案沒有 hosted backend，也不會自行把來源檔案上傳到本專案服務；但如果 Copilot、Amp、Claude Code 或其他宿主使用雲端模型，提供給 Agent 的文字會依該供應商的資料條款與隱私設定處理。
- **`--mode technical` 例外。** 走 docling 時，第一次執行可能下載模型，**不保證離線**。文字型 PDF 請用 `--mode text`。
- **Windows 工作目錄。** 預設寫入 `%LOCALAPPDATA%\book-to-skill\work`，可用環境變數 `BOOK_SKILL_WORKDIR` 改到你指定的私人目錄。
- **用你自己的複本。** 你買的書、公司擁有的文件、或你有權閱讀的論文。
- **產出是筆記。** 產生的技能是結構化、綜合過的衍生資料（框架名稱、定義、要點），不是原文重製。不要把他人著作的技能公開散布。

有疑慮時，遵守來源文件的授權或條款。這是工具；怎麼用由你負責。

---

## 贊助上游

<img align="right" width="150" src="docs/assets/booklin-celebrating.png" alt="Booklin 在慶祝">

book-to-skill 是免費的 MIT 專案，由原作者在個人時間維護。若它幫你省了 token 或讀書時間，請考慮贊助上游：

**[成為贊助者 → github.com/sponsors/virgiliojr94](https://github.com/sponsors/virgiliojr94)**

每位贊助者列在 [BACKERS.md](BACKERS.md)。本 fork 不接收取代上游的贊助連結。

## License

MIT — 適用於本 repo 的轉換器（程式 + 技能定義），**不適用**於你拿來處理的任何書籍或文件。授權全文見 [`LICENSE.md`](LICENSE.md)，來源標示見 [`NOTICE.md`](NOTICE.md)。