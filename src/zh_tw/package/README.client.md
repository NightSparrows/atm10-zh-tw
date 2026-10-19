# ATM10 8.3 繁體中文（台灣）翻譯包

本包由 ATM10 8.3 的 r27 簡中翻譯產生。
只適用於 ATM10 8.3。

## 來源與署名

| 來源 | 使用內容 |
|---|---|
| [chiba233/atm10-zh-cn](https://github.com/chiba233/atm10-zh-cn) | 簡中翻譯、建置架構與安裝器 |
| [上游 r27](https://github.com/chiba233/atm10-zh-cn/releases/tag/vr27) | ATM10 8.3 簡中 Client 翻譯底本 |
| [George15526/atm10-zh-tw-fork](https://github.com/George15526/atm10-zh-tw-fork) | 繁中轉換核心、台灣術語與上下文規則 |
| [AllTheMods/ATM-10](https://github.com/AllTheMods/ATM-10) | 核對 8.3 任務原文與資源路徑 |

簡中上游整理與補譯：星野夢華（Hoshino Yumeka）。
文字以 OpenCC `s2twp` 轉換，並套用台灣術語與人工修正。
Just Dire Things 的名稱依據為 [MC 百科條目](https://www.mcmod.cn/class/14797.html)。
章節、任務與正文中的模組名稱保留英文。
來源版本與建置方式見 Repository 的 `docs/zh_tw.md`。
第三方來源與署名見隨包的 `CREDITS.md`。
該文件保留上游簡中包的技術說明。
本繁中包的內容與限制以本 README 為準。
程式碼採 GPL-3.0-or-later，衍生譯文採 CC BY-NC-SA 4.0。
詳細授權範圍見隨包的 `LICENSE`。

## 安裝

1. 關閉遊戲並備份存檔與設定。
2. 將 `atm10-zh_tw-client` 整個資料夾放進遊戲目錄。
3. Windows 執行 `install-windows.bat`。
4. macOS / Linux 執行 `bash install.sh apply`。
5. 安裝器保留上游介面。選擇套用漢化。
   若詢問是否安裝 JEI 拼音搜尋，按 Enter 或選 `N`。
   本包沒有附帶該模組。
6. 在遊戲內選擇「繁體中文（台灣）」。
7. 將 `ATM10-zh_tw-8.3.zip` 移到資源包最上方。

不要把 Client ZIP 當作單一資源包放入 `resourcepacks`。
不要將本包裝到其他 ATM10 版本。
不要將本包裝到專用伺服器。

安裝器會備份即將覆蓋的檔案。
需要復原時，執行安裝器並選擇恢復備份。
本包停用安裝器的自動更新查詢。

## 已知限制

圖片保留簡中原圖，尚未完成繁體化。
圖片清單見隨下載提供的 `images-manual.json`。
「幽冥」任務已撤除失效的配圖引用。
這項修正與官方 8.3 英文任務一致。
其餘任務圖片的載入狀態仍需進入遊戲確認。

本包不包含任何 Mod JAR。
VaultPatcher 替換表需要既有的 VaultPatcher 才能生效。
若未安裝，部分寫死在模組中的文字仍為英文。
請保留已有的相容 VaultPatcher。
本次建置沒有下載或驗證它。

模組自行附帶、且未收進上游翻譯包的簡中內容未轉換。
繁中語言下，這些內容可能回退為英文。
獎杯的動態翻譯鍵保留來源，尚待遊戲內驗證。
多人遊戲的任務書與伺服器文字也需要另行驗證。

本包未啟動 Minecraft 測試。
靜態驗證不能確認遊戲內排版與載入順序。
英文搜尋與雙語 Tooltip 由 PolyglotTooltip 處理。
