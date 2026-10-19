<p align="center">
  <img src="src/pack/pack.png" width="96" height="96"
       alt="ATM10 翻譯包圖示，沿用簡中上游素材">
</p>

# All the Mods 10 繁體中文（台灣）

本 Fork 提供 **ATM10 8.3** 的 `zh_tw` Client 翻譯包。
以簡中上游的 8.3 資源為底本，使用 OpenCC `s2twp` 轉換。
轉換時套用台灣術語與人工修正。
簡中來源與原建置架構保留，可在同步上游後重新建置。

[貢獻指南](CONTRIBUTING.md) · [建置說明](docs/zh_tw.md) · [授權](LICENSE)

## 來源與署名

| 來源 | 本 Fork 使用的內容 |
|---|---|
| [chiba233/atm10-zh-cn](https://github.com/chiba233/atm10-zh-cn) | 簡中譯文、資源、版本資料、建置系統與安裝器 |
| [上游 r27](https://github.com/chiba233/atm10-zh-cn/releases/tag/vr27) | ATM10 8.3 的簡中 Client 翻譯底本 |
| [George15526/atm10-zh-tw-fork](https://github.com/George15526/atm10-zh-tw-fork) | 繁中轉換核心、台灣術語與上下文規則 |
| [AllTheMods/ATM-10](https://github.com/AllTheMods/ATM-10) | 核對 8.3 任務原文與資源路徑 |

簡中上游整理與補譯：**星野夢華（Hoshino Yumeka）**。
上游引用的 CFPA 社群與各模組譯文，署名見 [CREDITS.md](CREDITS.md)。
該文件保留上游簡中包的技術說明與統計口徑。
本繁中包的內容與限制以本頁及包內 README 為準。

使用的來源版本與鎖定方式見 [繁中建置說明](docs/zh_tw.md#架構與來源)。
Just Dire Things 的名稱依據為 [MC 百科條目](https://www.mcmod.cn/class/14797.html)。
章節、任務標題與正文引用均保留 `Just Dire Things`。

## 適用範圍

- 只支援 **ATM10 8.3 客戶端**，語言代碼為 `zh_tw`。
- 包含任務書、模組語言、手冊及 KubeJS 等翻譯資源。
- 沿用 8.3 底本，不套用 8.1 的設定或任務資料。
- 本包不附帶 Mod JAR。
- 英文搜尋與雙語 Tooltip 由 PolyglotTooltip 處理。

## 安裝

使用檔名含 `zh_tw`、`client` 與 `atm8.3` 的 ZIP。
建置產物位於 `dist/`。

1. 關閉遊戲，備份存檔與設定。
2. 解壓 ZIP，將 `atm10-zh_tw-client` 放進遊戲目錄。
   遊戲目錄是含有 `mods/` 與 `options.txt` 的那一層。
3. Windows 執行 `install-windows.bat`。
   macOS / Linux 在安裝資料夾執行 `bash install.sh apply`。
4. 若出現選單，選 `[1] 应用汉化`。
5. 若詢問是否安裝 JEI 拼音搜尋，按 Enter 或選 `N`。
   本包沒有附帶該模組。
6. 遊戲內選擇「繁體中文（台灣）」。
7. 將 `ATM10-zh_tw-8.3.zip` 放到已啟用資源包的最上方。

```text
遊戲目錄/
├─ mods/
├─ options.txt
└─ atm10-zh_tw-client/
   ├─ install-windows.bat
   ├─ install.sh
   ├─ README.zh_tw.md
   └─ ...
```

Client ZIP 是安裝包，不能整份當作資源包啟用。
安裝器介面沿用上游簡中，安裝內容使用 `zh_tw`。
安裝器會先備份即將覆蓋的檔案。
需要復原時，執行安裝器並選 `[3] 恢复备份`。
更新繁中包時，解壓新版後重新執行安裝器。
本包停用安裝器的自動更新查詢。

## 建置與驗證

在倉庫根目錄執行：

```bash
python3 -m venv build/venv-zh_tw
build/venv-zh_tw/bin/python -m pip install --require-hashes -r requirements-zh_tw.lock
build/venv-zh_tw/bin/python scripts/zh_tw/fetch_translation.py
ATM_TW_PYTHON=build/venv-zh_tw/bin/python bash scripts/build_dist.sh r27 8.3 zh_tw build/inputs/atm10-zh_cn-client-r27-atm8.3.zip
```

下載器只取得鎖定的翻譯資源，不下載 Mod JAR。
繁中流程不下載或啟動 Minecraft、整合包及遊戲執行環境。
已有來源與依賴時，可完全離線建置。

預設產物為 `dist/atm10-zh_tw-client-r27-atm8.3.zip`。
靜態報告位於 `dist/reports/zh_tw-8.3/`。
檢查涵蓋 JSON、翻譯鍵、格式參數、特殊標記與 ZIP 完整性。
也會比對任務 ID、依賴與 KubeJS 非文字資料。
重建檢查會比對 ZIP 位元組與來源檔案雜湊。
測試命令與同步方式見 [繁中建置說明](docs/zh_tw.md)。

## 已知限制

圖片保留簡中原圖，尚未完成繁體化。
部分主選單文字位於圖片中，不會隨遊戲語言切換。
完整圖片清單見建置報告的 `images-manual.json`。

翻譯包未收錄的模組語言可能回退為英文。
VaultPatcher 替換表需要既有的相容 VaultPatcher 才能生效。
多人伺服器同步、動態翻譯鍵與部分任務圖片仍待驗證。

繁中建置只執行靜態驗證，沒有啟動遊戲測試。
遊戲內載入、排版與搜尋結果需自行確認。

## 授權

授權依內容區分，詳細範圍見 [LICENSE](LICENSE)。

| 內容 | 授權 |
|---|---|
| 建置程式、安裝器與 CI | GPL-3.0-or-later |
| 簡中上游譯文及其衍生翻譯 | CC BY-NC-SA 4.0 |
| 第三方素材 | 各自授權，保留上游聲明 |

程式碼授權正文見 [LICENSE-GPL-3.0](LICENSE-GPL-3.0)。
來源與第三方署名見 [CREDITS.md](CREDITS.md)。
