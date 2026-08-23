# 上游維護

## Remote

- Fork：`origin` → `https://github.com/SanHsien/book-to-skill.git`（預設 `main`）
- 原作者：`upstream` → `https://github.com/virgiliojr94/book-to-skill.git`
- 上游追蹤分支：`master`

## 檢查新提交

```powershell
git fetch upstream master
python tools\check_upstream_updates.py --strict
```

工具以 `tools/upstream_baseline.json` 的 `reviewed_through` 為起點，列出所有未審查提交。
有新提交或檢查失敗時，`--strict` 回傳非零；排程 workflow 也會因此明確失敗。

## 審查清冊

每次只做一次批次審查：

1. 讀 commit 主旨與變更檔案。
2. 判斷是否與繁中 README、Windows gate、deploy 閘門或測試衝突。
3. 可直接同步的提交用 merge；只需要部分修正時 cherry-pick 或最小重做。
4. 跑 `pwsh -NoProfile -File tools\dev_check.ps1`。
5. 在 `docs/DECISIONS.md` 記錄採用／略過理由。
6. 驗證完成後才把 baseline 推進到已審查的完整 40 字元 SHA。

Baseline 代表「已審查」，不代表「全部已合併」。

README 衝突的解法：上游新內容併進 `README.en.md`，再把對應段落翻進 `README.md`。
第三語系檔（例如 `README.ru.md`）略過，不要合進本 fork。

## 2026-08-22：fork 起點

本 fork 自上游 `master` `3a97a7115ab3c82edf47f315b544fbcefdd8559c`
（`Update README.md (#179)`）建立。此 SHA 設為第一個 `reviewed_through`。
之後的上游 commit 才需要進入審查清冊。

## 2026-08-22：上游 PR、issue、分支盤點（含實際引用）

盤點當時上游有 **14 個 open PR、7 個 open issue、15 個分支**。結論與已引用的項目如下，
之後只看編號比水位大的，不必重看這批。

### 已引用（cherry-pick，保留原作者）

| 上游 PR | 引用理由 | 本 fork 的 commit |
| --- | --- | --- |
| [#117](https://github.com/virgiliojr94/book-to-skill/pull/117) `-enc UTF-8` 給 pdftotext | **Windows 直接受害**：pdftotext 預設輸出平台 8-bit 編碼，只把 stdout 當 UTF-8 解不夠，中文書會變亂碼。本 fork 是 Windows-first。 | `74a9790`、`f7a29b5` |
| [#181](https://github.com/virgiliojr94/book-to-skill/pull/181) 解析帶 UTF-8 BOM 的 SKILL.md | Windows 編輯器（記事本、部分 VS Code 設定）會寫 BOM，驗證器原本會整個解析失敗。 | `44d23d0` |
| [#175](https://github.com/virgiliojr94/book-to-skill/pull/175) 康熙部首數字的章節偵測 | 繁中書籍常見以康熙部首碼點排版章節號，原本抓不到章節。 | `10ce573` |
| [#178](https://github.com/virgiliojr94/book-to-skill/pull/178) 剝除 Cf 過濾器碰不到的隱形載體 | 變體選擇符、行間註記控制、U+2800、音樂格式字元都能夾帶模型讀得到、人看不到的內容。本工具的產出是 agent 讀的 skill，這是注入通道。 | `20da83b` |
| [#182](https://github.com/virgiliojr94/book-to-skill/pull/182) 剝除已棄用的格式控制字元 | 補上 U+206A–206F 一段，#178 沒涵蓋。 | `fe79067` |

**兩個上游 PR 互相矛盾，本 fork 做了取捨**：#178 把 U+2800（BRAILLE PATTERN BLANK）當成
隱形載體剝除，#182 的測試卻要求保留它。兩個都還沒被上游合併。本 fork 兩個都採用，衝突處
**採剝除**——產出是 agent 讀的指令，會渲染成空白又躲過空白正規化的字元是走私通道，不是內文。
談盲文的書會少一個空白格，但帶著隱藏指令的 skill 是更糟的交換。測試改成兩條：可見符號留下、
U+2800 被剝除，理由寫在測試裡。

### 評估後不引用

| 項目 | 結論 |
| --- | --- |
| PR #125、#137（技能預設輸出到 `~/.agents/skills`） | 產品路徑政策，本 fork 沒有偏好，等上游定案隨 commit 進來。 |
| PR #126（ToC 偵測 + 併發共用 workdir）、#129／#166（多欄 PDF 閱讀順序）、#157／#170（漸進式揭露）、#161、#176、#180 | 都動到抽取器主流程或 SKILL.md 規格，屬產品方向，上游還在改版；等它合併成 commit 再一次審。**不要在這裡搶跑**，否則上游合併時整段衝突。 |
| issue #67、#128、#137、#156、#160、#169 | 產品功能討論，隨 commit 進來。 |
| issue [#174](https://github.com/virgiliojr94/book-to-skill/issues/174)（有人惡意重新上架本專案） | 與程式無關，但**與本 fork 的授權立場有關**：本 fork 保留原作者與 MIT 標示、`FORK.md` 寫明來源，正是這個 issue 要防的事。無須改動，記錄備查。 |

### 水位

- PR：已看到 **#182**（`reviewed_pr_through`）
- issue：已看到 **#174**（`reviewed_issue_through`）
- 兩者都記在 `tools/upstream_baseline.json`；下次只看編號更大的。

### 分支：13 個不是 PR head，逐一比對後不引用

不是只數數量。把每個分支與 `master` 比對後，只有這些有獨佔 commit，且多數已落後 118–132 個 commit：

| 分支 | 狀態 | 結論 |
| --- | --- | --- |
| `fix/windows-security-test-skips`（ahead 2、behind 8，2026-08-17） | 唯一還算新的 | **不引用：本 fork 的做法更嚴。** 它把 symlink 測試在 Windows 上一律 skip；本 fork 是**先嘗試建立 symlink**，只有主機真的拒絕（未開發人員模式的 `WinError 1314`）才 skip——開了開發人員模式的 Windows 會真的跑那條測試，上游版本則永遠不跑。 |
| `fix/chapter-detection`（ahead 1，2026-06-08，behind 122） | 已被後續取代 | 章節偵測本 fork 已引用更新的 PR #175（康熙部首）與 #161 系列的成果；這個分支是三個月前的舊版。 |
| `ci/github-actions`、`skill/claude-conformance`、`docs/align-readme-skill-defaults`、`docs/real-benchmarks`、`docs/release-1.0.0`、`chore/gitignore-stone`、`feat/adaptive-depth` | 全部 behind 118–132 | 上游自己的舊工作線，內容已被 `master` 取代。**這一列原本以「等」收尾，蓋掉了四條 behind 很小的分支**——已於 2026-08-23 逐條補在本檔末。 |

## 2026-08-23：重評先前「暫緩」的 PR，並引用 #126

前一輪把 #126／#129／#157／#161／#166／#170／#176／#180 一起以「動到抽取器主流程或
SKILL.md 規格，等上游合併」帶過。**那是似是而非的理由**：上游合不合併與「這個修正在本
fork 是不是真的有效」無關。這輪逐筆讀 diff 並到本 fork 程式碼裡驗證。

### 已引用：[PR #126](https://github.com/virgiliojr94/book-to-skill/pull/126) 兩半都適用

**第一半——ToC 標題被 Markdown 標記擋住**

- 事實：本 fork 的 `_TOC_PATTERN` 仍是 `^\s*(header)\s*$`。Markdown 的目錄標題寫成
  `## Table of Contents`，強調寫成 `**Contents**`，兩者都抓不到。實測 `grep` 確認本 fork
  沒有這一段。
- 影響：`has_toc` 回 False，Step 3 的章節對應只能靠 heading scan，輸出裡只會出現一行
  「No table of contents detected」的警告——看起來像文件本身沒有目錄。
- 已採用並延伸：接受 ATX／AsciiDoc 標記、強調、尾端冒號，額外涵蓋全形冒號與全形空白
  （CJK 目錄需要）。

**移植時抓到上游版本的一個 Windows 盲點**：PR #126 的尾端字元類是 `[ \t]*$`。Windows
的抽取文字保留 CRLF，而 `MULTILINE` 的 `$` 只匹配 `\n` 之前——`\r` 卡在中間，於是那個
pattern 在本 fork 的主要平台上等於全部失效（舊的 `\s*$` 是靠 `\s` 涵蓋 `\r` 才沒事）。
移植時把 `\r` 加回字元類，並補兩個 CRLF 回歸測試。**這是 verbatim cherry-pick 會靜靜壞掉
的例子。**

**第二半——併發跑會互相覆蓋 workdir**

- 事實：本 fork 先前只把預設 workdir 改成 Windows per-user（`%LOCALAPPDATA%`），那解決的是
  多使用者共用 `%TEMP%` 的問題，**不是併發**。同一個使用者同時跑兩次抽取，仍共用一個目錄：
  後者覆蓋 `full_text.txt`，前者照樣寫自己的 `metadata.json`，於是 metadata 描述的是它沒有
  產出的文字，而輸出裡沒有任何跡象。
- 已採用：`claim_workdir()` / `release_workdir()` 以 PID lock 檔佔用，第二個 run 直接拒絕啟動
  並指出解法（設 `BOOK_SKILL_WORKDIR`）；holder 行程已消失的 stale lock 自動回收，崩潰的 run
  不會卡死下一次。
- **Windows 驗證**：`os.kill(pid, 0)` 在 Windows 對活著的行程不丟例外（會擋）、對不存在的 PID
  丟 `OSError [WinError 87]`（判為 stale），行為正確。上游測試用「PID 1 一定存在」是 POSIX
  假設，在 Windows 會讓測試失敗——改成實際 spawn 一個子行程，這樣三個平台都真的驗到。

### 已引用：[PR #180](https://github.com/virgiliojr94/book-to-skill/pull/180) 只有標點的 setext 標題

- **本來寫「本 fork 已不受影響」，實測推翻**：`detect_structure("Intro line\n!!!\n---\n\nBody.\n")`
  回報 `chapters_detected == 1`。`_structural_chapter_count` 有兩條標題分支，ATX 那條會用
  `re.search(r"\w", title)` 擋掉沒有文字的標題，setext 那條沒有——**同一個字串寫成 `## ***`
  被拒、寫成 `***` 加一行 `---` 就被當標題**。兩個連續的主題分隔、ASCII 方框線、一排點、
  標點型表格邊框都會鑄出幽靈章節。
- 幽靈章節在輸出裡看不出來，它只是把使用者被要求信任的那個數字往上加。
- 已採用同一個 `\w` 檢查，並補回歸測試；同時確認合格的 setext 標題（底線長度足夠）仍算得到。

### 重評後仍不引用（理由換成讀完 diff 的事實）

| PR | 事實 | 結論 |
| --- | --- | --- |
| [#129](https://github.com/virgiliojr94/book-to-skill/pull/129) / [#166](https://github.com/virgiliojr94/book-to-skill/pull/166) 多欄 PDF 閱讀順序 | 兩支互為替代方案（#166 是 #129 的 draft 重做），都改 `pdftotext` 的呼叫方式：拿掉 `-layout` 改用預設閱讀順序。本 fork 剛引用 #117 在同一行加了 `-enc UTF-8`。 | **等上游二選一定案**——這不是「產品方向」的推託：兩個 open PR 對同一行有衝突的改法，先挑一個會在另一個合併時製造衝突，且沒有證據顯示哪一版更好。**觸發條件**：上游合併其中一支，或本線出現多欄 PDF 亂序的實例。 |
| [#157](https://github.com/virgiliojr94/book-to-skill/pull/157) / [#170](https://github.com/virgiliojr94/book-to-skill/pull/170) 漸進式揭露 | 把 `SKILL.md` 拆成輕量入口 + `HOW_TO_USE.md`／`GENERATION.md`。#170 是 #157 的後續。 | **不引用**：本 fork 的 `SKILL.md` 已與上游分岔（Codex 宿主約定、source-text guardrails），拆檔會讓每次上游同步都在同一批檔案衝突，換到的只是入口檔行數。 |
| [#161](https://github.com/virgiliojr94/book-to-skill/pull/161) 章節偵測（Unit 式、羅馬數字） | 與本 fork 已引用的 #175（康熙部首）同一區塊；#161 base 較舊，且本 fork 的 `_structural_chapter_count` 已重寫過。 | **不整支引用**；若出現抓不到的實例再按本 fork 的實作補規則。 |
| [#176](https://github.com/virgiliojr94/book-to-skill/pull/176) eval 協定凍結 | 新增 `eval/` 的假設預註冊與 v0 協定，屬上游的研究流程。 | 不引用：本 fork 不跑那套 eval。 |
（#180 已改列到上面的「已引用」——初稿本來寫「本 fork 已不受影響」，實測後發現不成立，見下。）

### 水位

- PR：已看到 **#182**；issue：已看到 **#174**（記在 `tools/upstream_baseline.json`）。
- 下次只看更大的編號，或已評估 PR **出現新 commit**（有新 commit 才重讀 diff）。

## 2026-08-23（補）：分支逐條列完，不再用「等」帶過

上面那張分支表用「`docs/*`、`chore/gitignore-stone`、`feat/adaptive-depth` 等」把一批分支
合併成一列，理由寫「全部 behind 118–132」。那個理由對其中大多數成立，但**有四條不在那個
區間**，等於被那個「等」字蓋掉了。逐條補上（`ahead`／`behind` 皆為 2026-08-23 實測）：

| 分支 | ahead / behind | 實際內容 | 結論 |
| --- | --- | --- | --- |
| `eval/v0-preregistration` | 3 / **1** | 三個 commit 全部只新增 `eval/v0/` 底下的三份 Markdown（`EVAL-V0-DEMANDA.md` 293 行、`EVAL-V0-PREREG.md`、`BACKLOG-POS-V0.md`），+335 −0，不動任何程式碼。 | **不引用**：上游自己的評估設計文件（預先登記假設與需求凍結），不是本 fork 要驗的行為。 |
| `virgiliojr94-patch-1` | 1 / **1** | 單一 commit，`README.md` **−10 行**（刪段落）。 | **不引用**：本 fork 的 README 已獨立改寫。 |
| `docs/shorten-readme-mascots` | 1 / 49 | 拆 README 成多頁並加吉祥物圖（含兩張 PNG）、動 `mkdocs.yml`，+312 −267。 | **不引用**：本 fork 不維護 mkdocs 站台，README 結構也已自行定案。 |
| `gh-pages` | 1 / 155 | MkDocs 的建置產物分支（`Deployed 3a97a71 with MkDocs 1.6.1`），與 `master` **沒有 merge base**。 | **不引用**：部署產物，不是原始碼。 |

其餘八條（`chore/gitignore-stone`、`ci/github-actions`、`docs/align-readme-skill-defaults`、
`docs/real-benchmarks`、`docs/release-1.0.0`、`feat/adaptive-depth`、`fix/chapter-detection`、
`skill/claude-conformance`）behind 118–132，仍如上表。`copilot/fix-issue-159` 的 ahead 為 0，
沒有獨佔 commit。

**下次的判準**：分支表不要再用「等」收尾。`behind` 很大的舊分支可以合併成一列，但**任何
`behind` 在個位數的分支都要單獨一列**——那代表它跟得上 `master`，有可能帶著還沒進主線的東西。

## 2026-08-23（補二）：PR 水位其實漏了兩筆——盤點時只查了 open

上一輪的 PR 盤點用 `--state open` 查。那漏掉了兩件事：**已關閉的項目**，以及水位之後才出現的
新 PR。`--state all` 一查就看到 `#182` 之後還有兩筆：

| PR | 狀態 | 實查結果 |
| --- | --- | --- |
| [#183](https://github.com/virgiliojr94/book-to-skill/pull/183) `fix: close review findings without sending them upstream` | 已關閉 | **不是上游的變更，是本 fork 端誤開到上游後關掉的那一個**（author `SanHsien`，內容全是本 fork 自己的檔案：`FORK.md`、`tools/dev_check.ps1`、`tools/upstream_baseline.json`⋯）。記在這裡是為了下次看到它時不用再查一次。判準見 `AGENTS.md` 的「對外只打本 fork」。 |
| [#184](https://github.com/virgiliojr94/book-to-skill/pull/184) `fix(config): give each run its own workdir so concurrent extractions cannot clobber each other` | **open**（第三方貢獻者 `Jgiet001-AI`） | **部分引用**，見下。 |

### PR #184：引用「精確清理」那一半，不引用「每次跑換一個目錄」那一半

它要解的缺陷本 fork **已經處理過**：`claim_workdir()` 的 PID lock（引用自上游 #126）讓第二個
並行的 run 直接被擋下並指名解法（`BOOK_SKILL_WORKDIR`），不會靜默覆蓋彼此的 `full_text.txt`。

但它裡面有一個本 fork **真的還有**的問題：`SKILL.md` 的 Step 10 清理步驟不是刪「這次 run 用的
目錄」，而是**照環境變數與作業系統重新推導一次**再 `rmtree`。重新推導可能推出**不同的目錄**
——並行 run 的、或 `BOOK_SKILL_WORKDIR` 在抽取之後被改掉的那個舊的——而 `rm -rf` 不會問第二次。

因此引用 #184 的這一半，做法照本 fork 的結構：

- `metadata.json` 新增 `workdir` 欄位，記下這次 run 實際解析出來的目錄；
- `SKILL.md` Step 10 改成從該 run 的 `metadata.json` 讀回 `workdir` 再刪；讀不到就**不刪並說明**
  ——那時候任何猜測都是在猜「要刪哪個目錄」；
- `tests/test_default_workdir.py` 新增一條把 `metadata["workdir"]` 釘在解析後的路徑上。

**不引用**「預設目錄改成 `book_skill_work-<pid>`」那一半：本 fork 的 lock 已經消除靜默覆蓋，而
那個改動要把 `SKILL.md` 裡固定路徑的契約整段重寫（#184 自己就改了六處），換來的只是「第二個
並行 run 自動有自己的目錄」而不是「被擋下並被告知怎麼做」。**觸發條件**：上游合併 #184（屆時
契約以上游為準），或本線實際出現並行抽取的用法。

### 水位

- PR：**#184**（`reviewed_pr_through` 182 → 184）
- issue：仍是 **#174**（`--state all` 查過，沒有更大的編號）
- commit：仍是 `3a97a71`

**判準補一條**：PR 與 issue 一律用 `--state all` 查。一個項目在兩次檢查之間被開了又關，對本 fork
來說仍然是「從來沒有被審過」。
