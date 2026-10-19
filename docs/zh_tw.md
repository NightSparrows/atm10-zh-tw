# ATM10 8.3 繁中建置

繁中建置只接受 ATM10 8.3 的簡中 Client ZIP。
簡中來源與原建置流程保留不變。
建置過程不需要安裝或啟動遊戲。

## 架構與來源

上游的 `assemble.py` 會下載附帶模組與原版資源。
`generate_all.sh` 還需要模組 JAR、整合包與字型。
`build_dist.sh` 再按版本套用設定與任務書覆寫。
完整流程會接觸本次禁止下載的內容。

繁中流程接在上游 Client ZIP 之後。
它沿用上游的 `build_dist.sh` 入口與 `mkzip.py`。
轉換器不呼叫遊戲素材下載器。

| 來源 | 用途 |
|---|---|
| [上游 r27](https://github.com/chiba233/atm10-zh-cn/releases/tag/vr27) | 8.3 專用的完整簡中翻譯產物 |
| [上游程式碼](https://github.com/chiba233/atm10-zh-cn/tree/113ec0451596a8073e9455640b8e4d5f2de8af02) | 分層建置、版本覆寫與安裝器 |
| [繁中 Fork](https://github.com/George15526/atm10-zh-tw-fork/tree/5553ded861c169c94c58e00ba278c8a5a93c1768/scripts/zh_tw) | OpenCC 轉換器、術語、上下文規則與逐鍵覆寫格式 |

`source.lock.json` 記錄來源 commit 與逐檔雜湊。
r27 的 commit 與這次開工時的來源一致。
沒有使用 8.1 的設定或任務資料。

下載器先讀遠端 ZIP 的目錄與檔頭。
它只取得翻譯成員的壓縮位元組。
所有 JAR、模組目錄與可選模組都會排除。
伺服器若不遵守 HTTP Range，下載器立即失敗。
各成員會核對 CRC 與 SHA-256。

原 release 的完整 SHA-256 僅記錄為來源資訊。
因未取得完整 ZIP，沒有驗證該完整雜湊。
驗證基準是鎖檔內的逐成員雜湊。

## 建置

在倉庫根目錄執行：

```bash
python3 -m venv build/venv-zh_tw
build/venv-zh_tw/bin/python -m pip install --require-hashes -r requirements-zh_tw.lock
build/venv-zh_tw/bin/python scripts/zh_tw/fetch_translation.py
ATM_TW_PYTHON=build/venv-zh_tw/bin/python bash scripts/build_dist.sh r27 8.3 zh_tw build/inputs/atm10-zh_cn-client-r27-atm8.3.zip
```

下載步驟只取漢化資源。
已有來源 ZIP 與依賴時，建置本身完全離線。
輸出為 `dist/atm10-zh_tw-client-r27-atm8.3.zip`。
報告放在 `dist/reports/zh_tw-8.3/`。

重建與來源保護驗證：

```bash
build/venv-zh_tw/bin/python scripts/zh_tw/test_zh_tw.py
build/venv-zh_tw/bin/python scripts/zh_tw/check_tw.py build/inputs/atm10-zh_cn-client-r27-atm8.3.zip dist/atm10-zh_tw-client-r27-atm8.3.zip
build/venv-zh_tw/bin/python scripts/zh_tw/reproduce.py build/inputs/atm10-zh_cn-client-r27-atm8.3.zip dist/atm10-zh_tw-client-r27-atm8.3.zip
```

`.github/workflows/zh-tw.yml` 提供手動建置入口。
它不執行上游的完整遊戲素材建置。

## 同步上游

保留 `src/` 的簡中內容。
同步後，先取得更新的 8.3 簡中 Client ZIP。
也可以使用已完成的上游建置產物。
需要接受自製產物時，明確指定 `--unlocked`：

```bash
build/venv-zh_tw/bin/python scripts/zh_tw/build_tw.py build/inputs/atm10-zh_cn-client-custom-atm8.3.zip --unlocked
```

`--unlocked` 不驗證來源 release 的成員雜湊。
它仍驗證格式、結構、標記與檔案完整性。
正式更新來源時，應更新 `source.lock.json`。
`fetch_translation.py --record` 可重建成員清單。
更新鎖檔後，應核對來源與排除清單。

## 轉換規則

文字先套用繁中 Fork 的術語與上下文規則。
剩餘文字以 OpenCC `s2twp` 轉換。
`terms.json` 的所有詞組與規則都會移植。
`overrides.json` 提供逐鍵人工覆寫。
本流程不下載原版語言檔或模組 JAR。
因此不套用 Fork 的原版名稱字典與 JAR 補位。

| 類型 | 轉換範圍 |
|---|---|
| Mod 語言檔 | 值。JSON keys 全部保留 |
| Patchouli 與其他 JSON 手冊 | 已列明的顯示欄位與目錄名稱 |
| AE2 / Oracle Index / 沉浸工程手冊 | 正文。程式碼與特殊標記保留 |
| FTB Quests | 語言條目與顯示欄位 |
| SNBT 中的告示牌與文字元件 | 已知的文字欄位 |
| KubeJS | 已列明的文字 API 參數與翻譯表值 |
| VaultPatcher | `pairs[].value` 與預設語言 |
| RFTools GUI | 文字標籤。`choice()` 參數保留 |
| 字型與圖片 | 原樣保留 |

JSON keys、資源 ID 與任務 ID 不翻譯。
KubeJS 的物件鍵、比較字串與未知資料保留。
註解與中繼資料可能保留簡體字。
語言路徑的 `zh_cn` 改為 `zh_tw`。
語言檔的語言代碼與地區也會一併設定。
`pack.mcmeta` 的語言宣告也會對應調整。
這是 JSON keys 比對中唯一的明示例外。

來源中兩份 Herbs & Harvest JSON 多了結尾括號。
`repairs.json` 只准修正指定雜湊的這兩份檔案。
其他無法解析的 JSON 一律中止建置。

## 報告與限制

| 檔案 | 內容 |
|---|---|
| `validation.json` | 靜態驗證、條目數、缺漏與未驗證項目 |
| `manifest.json` | 來源及產物的逐檔雜湊 |
| `changes.json` | 已轉換的文字條目 |
| `simplified-residue.json` | 簡體候選、受保護資料與共用字 |
| `images-manual.json` | 保留原圖的完整清單 |
| `quest-image-references.json` | 任務圖片引用、官方來源索引與未驗證項目 |
| `reproducibility.json` | 重建 ZIP 與來源保護結果 |

簡體候選不等於漏譯數。
指令、來源比對資料與字形表會保留原文。
共用字需要依上下文判斷。
掃描器有已知簡體字的正例測試。

本包沒有附帶 VaultPatcher JAR。
需要既有的相容 VaultPatcher 才能套用替換表。
安裝器沿用上游介面，套用 `zh_tw` 設定。
自動更新查詢停用，避免下載未核對的產物。

模組自行附帶、未收錄的簡中內容未轉換。
這些內容在繁中語言下可能回退為英文。
獎杯的中文動態鍵保留來源，需進入遊戲驗證。
所有圖片都保留原圖，沒有宣稱完成繁體化。
「幽冥」任務的失效圖片引用依官方英文任務撤除。
依據與原文保存在 `src/zh_tw/quest_images.json`。
該檔只保存 GitHub 檔名與比對資料，不保存圖片。
官方版本由 `config/bcc-common.toml` 核對。
修正只套用指定任務的一條描述，不改任務 ID。
其他圖片若依賴整合包或模組，載入狀態仍未驗證。
圖片引用報告會分列缺檔候選與路徑大小寫差異。
執行時 API、字形、排版與多人同步均未驗證。
