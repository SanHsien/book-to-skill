# Repository review（Windows-first）

- Review date: 2026-11-20
- Review range: `2b2e787..53b2bd9`（51 commits，增量審查）
- Previous review baseline: `8a710a3`（2026-08-22）。那是重設歷史前的 commit，**不是** `main` 的祖先：`2b2e787`（2026-09-27 `release: initialize clean repository v1.0.0`）是新的根 commit，沒有 parent，樹內已含 `8a710a3` 的內容與上一輪 R-01～R-08 的修正（`git diff --stat 8a710a3 2b2e787`：66 檔）。所以本輪從 `2b2e787` 起算，舊檔頭寫的 `8a710a3` 只對上一輪成立。
- Fix status as of: 2026-11-20。下表 commit 為 rebase 到 `origin/main` 後的雜湊；F-02 與 H-01 的補強 commit 在本機 `main`，尚未 push
- Primary environment: Windows 11、PowerShell、Python 3.14（本機）、CI Windows 3.12 / Ubuntu 3.9–3.13
- Status: 本輪 3 筆 confirmed 與 2 筆 hardening 全部已修；產品抽取器仍不回貢；官方仍是上游 `virgiliojr94/book-to-skill`

## 結論

範圍內沒有新的高風險問題。3 筆 confirmed 都是抽取品質或並行安全的缺陷，觸發條件窄，但都會在沒有任何警告的情況下污染輸出，所以全部修掉，每筆都先補了在舊碼上會紅的測試。

## Findings

| ID | 類別 | Finding | 修正 commit | 日期 | 測試（修前紅、修後綠） |
|---|---|---|---|---|---|
| F-01 | confirmed | `claim_workdir` 回收過期鎖有競態：B 判定過期後、刪除前，A 已回收並寫好自己的 PID；B 的 `unlink` 刪掉 A 的有效鎖，兩個執行同時持有工作目錄。Windows 上一樣會發生（A 已關閉 handle），`docs/DECISIONS.md` 原本寫「Windows 上無法刪」不對。 | `2678def` | 2026-11-20 | `tests/test_workdir_lock.py::test_two_runs_reclaiming_one_stale_lock_do_not_both_own_the_workdir`（修前 `DID NOT RAISE`）。另以 6 個行程同時回收同一過期鎖跑 5 輪，每輪恰好 1 個取得。 |
| F-02 | confirmed | RTF 後備解析器只吞 `\uN` 後的一個 fallback 位元組；`\uc2` 時第二個位元組被 hex-run 解碼成亂碼（cp932 出現 PUA／半形片假名，cp936 出現 U+FFFD）。 | `514c6b6`、`c00c85b` | 2026-11-20 | `tests/test_rtf_unicode_skip_count.py`：`test_uc2_skips_both_fallback_bytes`（3 例）、`test_uc_is_scoped_to_its_group` 修前 4 紅；`test_uc0_skips_nothing`、`test_fallback_skip_stops_at_group_end` 為護欄。獨立驗收另指出（`c00c85b` 前就有，不是退步）：fallback 位元組被換行或巢狀 group 隔開時仍漏出雜字；`test_line_breaks_inside_a_fallback_are_ignored`（4 例）、`test_fallback_continues_into_a_nested_group`（2 例）、`test_uc_survives_a_nested_group_opened_inside_a_fallback` 修前 7 紅。CR／LF 不計數也不中止跳過；`{` 讓巢狀 group 繼承待跳過數；`}` 結束跳過，所以 `\uc2` 只在 group 內、位元組卻在 group 外的畸形輸入仍會留下一個字元（刻意，見護欄測試）。 |
| F-03 | confirmed | DOCX zip 解析器把段落定位點定義（`w:pPr/w:tabs/w:tab`）當成 Tab 輸出；有自動目錄的 docx 會整份走這條路，目錄段落多出開頭 Tab。 | `77f3da7` | 2026-11-20 | `tests/test_book_to_skill.py::TestDocxTableReconstruction::test_tab_stop_definitions_are_not_emitted_as_tabs`（修前得到 `'\t\tChapter 1\tIntro'`）。 |
| H-01 | hardening | CI job `test-optional-parsers` 安裝 `trafilatura`、`ebooklib`、`beautifulsoup4`、`striprtf`、`pytest` 時沒有釘版本。 | `463feda`、`4e0179c` | 2026-11-20 | 第一版只釘 5 個直接依賴、測試只比對一行安裝指令；獨立驗收指出 `defusedxml` 與 `lxml` 等間接依賴仍浮動，第二個 `pip install` 也擋不到。`4e0179c` 改釘上次綠燈 run 解析出的整棵依賴（31 個）。`tests/test_repo_hygiene.py::test_every_pip_install_in_the_optional_parser_job_is_constrained`（job 加一步 `pip install lxml` 時紅）、`test_optional_parser_ci_job_pins_its_whole_dependency_tree`（未釘 `defusedxml` 時紅；拿掉 `lxml` 時紅）。第二次驗收再指出：本機版本多與釘定不同，間接依賴走訪實際上沒在跑，且這個 job 不跑該測試；守門測試也漏掉 `pip3 install`、`pip -q install`、多個空白與只寫在註解裡的 `-c`。`CI_CHECK_COMMIT` 在 job 安裝後加跑 `tools/check_ci_constraints.py`，未釘、版本不符或釘了沒裝都失敗（`tests/test_ci_constraints_check.py`，修前因工具不存在無法收集）；守門改用 shlex 切 token（`test_pip_install_guard_catches_unconstrained_variants` 9 例中舊邏輯漏掉 6 例）。不做 hash：本 repo 其他安裝也沒有用 hash，理由與觸發條件見 `docs/DECISIONS.md` 2026-11-20。 |
| H-02 | hardening | `detect_structure` 以 `split()[1]` 取 Part 編號，`Part 1:Basics` 取到 `1:Basics`，Part-only 文件回報 0 章。 | `e32ba5b` | 2026-11-20 | `tests/test_part_chapter_count.py::test_part_number_is_read_when_no_space_follows_the_separator`（`:`、`.`、`-` 三例修前紅）。 |

上一輪（baseline `8a710a3`）的 R-01～R-08 已在重設歷史前全部關閉，修正內容包含在根 commit `2b2e787` 中；細節見該輪的 `REVIEW.md`（`git show 2b2e787:REVIEW.md`）。

## 本輪實證

本機（Windows 11、`.venv` Python 3.14，已裝 `pdf`／`epub`／`docx`／`rtf`／`html` extra）：

```text
pwsh -NoProfile -File tools\dev_check.ps1
→ compileall / ruff E9+F / pytest / validate_skill / SkillSpector 自我掃描 全綠
→ 864 passed, 8 skipped, 17 subtests passed
→ SKILL.md：無 Claude Code-breaking issues（1 soft warning：787 行 > 500）
```

SkillSpector 的精確指紋綁檔案內容，本輪改了 `docs/DECISIONS.md`、`tests/test_book_to_skill.py`、`tests/test_workdir_lock.py`，所以這三檔已審過的 8 筆指紋換新雜湊、理由不變；`tests/test_workdir_lock.py` 新增的競態測試多啟動一個固定的 30 秒子程序，多一筆同理由的 AST4。

## 已檢查、不列為 finding

- `sanitize_extracted_text` 的 ASCII 快速路徑：0–127 沒有碼位被判為不可見，行為與舊版等價；`_KANGXI_RADICAL_FOLD` 224 個映射皆一對一。
- `read_text_file` 遇 BOM 後資料損壞回 `None`，呼叫端（html、rtf、utils）都當失敗處理。
- `extract_with_docling` 改為往外丟例外：唯一呼叫端以 `except Exception` 接住並記 `fallback_reason = docling_failed`。
- EPUB：`../` 只影響 ZIP 成員名稱，一律經 `zf.read`；container 的 XML 參照只解預定義實體與合法碼位；UTF-16 偵測排除 UTF-32 LE。
- `text_from_soup`：`&`、`<` 經轉義再還原，script／style／head 事先移除。
- `tools/check_skillspector_report.py` 的 `reviewed_partials` 綁檔案 SHA-256，未涵蓋的 static 例外 fail closed；`tools/run_skillspector.py` 暫存 baseline 在 `finally` 刪除。
- `tools/check_upstream_updates.py`：子程序皆 argv 列表；`gh` 失敗回 `None` 並以 exit 2 表示未檢查；上游標題轉義 `|` 後才寫入 step summary。
- `validate_skill.get_scalar` 的 block scalar 讀取邊界正確；`extract_with_ebooklib` 依 spine 排序去重，spine 以外的文件附在最後。

## 尚未宣稱範圍

- **沒有**用真實 Word 產生的 `\uc2` RTF 與帶自動目錄的 docx 驗證 F-02、F-03；測試用的是手工合成的最小輸入。
- **沒有**實跑 `--mode technical`／Docling（本機沒有模型）。
- **沒有**看到本輪 commit 在 GitHub Actions 上的結果（尚未 push）；H-01 的 constraints 檔要等 CI 實跑才算驗證到 job 本身。
- **沒有**對 `check_upstream_updates.py` 做實際網路執行。
- 產生的技能目錄不在本 repo 工作樹，未掃描是否含原文。
