# t2x-suite

統合 **Novel Studio**（寫小說／設定集／視覺卡）與 **T2VN / T2C**（視覺小說／漫畫改編）的本機套件中樞：提供統一啟動器、唯讀跨管線總覽 Portal 與跨專案契約。

> 兩個主專案維持各自獨立開發、測試與單獨啟動；不透過 `t2x-suite` 啟動時，跨工具入口會自動隱藏。

## 使用方式

雙擊 `start.bat`（或在 PowerShell 執行 `.\start.ps1`）：
- 同時啟動 **Portal 總覽**（預設 `http://127.0.0.1:8700`）、**Novel Studio**（`http://127.0.0.1:8765`）與 **T2VN / T2C**（`http://127.0.0.1:7866`）。
- 預設自動開啟 **Portal** 分頁，從總覽一覽全書的寫作／VN／漫畫進度並單鍵直達對應工具。
- 自動注入 `SUITE_URL`、`NS_URL`、`T2VN_URL`（以及 `suite.json` 中選填的 `shared` 預設路徑），兩邊頂列會自動顯示雙向快速跳轉鍵。
- 偵測到埠號已在執行時自動略過，不重複啟動；按 `Ctrl+C` 或關閉視窗時一併結束啟動的服務。

## 路徑與本機覆寫

- 預設設定在 `suite.json`。
- 若需覆寫本機路徑（如 `shared.library_dir`、`shared.comfyui_url`、`shared.tagcomplete_csv` 或自訂埠號），可建立 `suite.local.json`（已列入 `.gitignore`），不影響版控。

## 文件

- 跨專案整合契約：[docs/contracts.md](docs/contracts.md)
