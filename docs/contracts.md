# t2x-suite 跨專案整合契約

> 本文件定義 `t2x-suite`、`Novel Studio` 與 `T2VN / T2C` 之間的鬆耦合介面契約。
> **最高原則**：兩個主專案不互 `import`、不依賴 `t2x-suite`，單獨啟動時自動隱藏跨工具入口。

---

## 1. 服務與埠號預設

| 服務 | 預設網址 | 職責 |
|---|---|---|
| **t2x-suite Portal** | `http://127.0.0.1:8700` | 唯讀跨管線總覽儀表板與單鍵入口 |
| **Novel Studio** | `http://127.0.0.1:8765` | 小說寫作、大綱、設定集、結構化視覺卡（正本） |
| **T2VN / T2C** | `http://127.0.0.1:7866` | 視覺小說改編（Ren'Py / 語音 / 美術）與頁漫改編（`vendor/t2c`） |

---

## 2. 環境變數契約（皆為選填）

由 `start.ps1` 依 `suite.json`（及可選的 `suite.local.json`）自動注入：

| 變數 | 說明 | 讀取端 |
|---|---|---|
| `SUITE_URL` | Portal 網址（不含尾端 `/`） | Novel Studio、T2VN |
| `NS_URL` | Novel Studio 網址（不含尾端 `/`） | T2VN、Portal |
| `T2VN_URL` | T2VN / T2C 網址（不含尾端 `/`） | Novel Studio、Portal |
| `T2X_LIBRARY_DIR` | 共用書庫路徑（選填預設提示，不覆蓋已存設定） | Novel Studio、T2VN |
| `T2X_COMFYUI_URL` | 共用 ComfyUI 位址（選填預設提示） | Novel Studio、T2VN |
| `T2X_TAGCOMPLETE_CSV` | 共用 TagComplete CSV 路徑（選填預設提示） | Novel Studio、T2VN |

**降級規則**：未設定上述變數時，各專案頂列不顯示對應跳轉鍵，設定值完全沿用各自設定檔。

---

## 3. 深連結（Deep Link）契約

- **T2VN → Novel Studio**：
  - 總入口：`${NS_URL}/`
  - 指定書頁：`${NS_URL}/#/b/<encoded_book_folder>`
- **Novel Studio → T2VN**：
  - 總入口：`${T2VN_URL}/`
  - 帶來源書識別：`${T2VN_URL}/#/?source=<encoded_book_folder>`（T2VN 前端比對已匯入作品的 `source_dir`，已匯入者顯示快速開啟或直接導向，未匯入者可預填來源資料夾）
- **雙邊 → Portal**：
  - `${SUITE_URL}/`

---

## 4. 資料所有權與單向橋接契約

### 4.1 唯讀邊界
- Novel Studio 書庫（`<library>/<book>/`）是**唯讀上游**；T2VN 與 Portal 嚴禁寫入、改名或刪除書庫內的任何檔案（含 `.studio/`）。
- T2VN 的所有改編、標註、外觀卡與漫畫產出僅寫入 `works_dir`。

### 4.2 視覺卡 → 外觀卡／漫畫卡映射

來源：`<book>/bible/visual-cards/<id>.md`（YAML frontmatter + Markdown）
目標：`works/<book_id>/art/appearance/<char_id>.json`（含 `t2c` 子物件）

| Novel Studio 欄位 | T2VN 目標欄位 | 轉換規則 |
|---|---|---|
| `id` / `name` / `aliases` | 比對 `cast.json` 既有 `char_id` | 依序比對 `id` → `names` → `aliases`（正規化）；對不到的人不自動建假角色 |
| `sections.head` + `sections.accessory` + `vn.headshot_extra` | `headshot_prompt` | 過濾表情詞，保留頭頸固定特徵 |
| `sections.body` + `outfits.default.{set,top,bottom}` + `vn.sprite_pose` | `sprite_prompt` | 組合立繪外觀與站姿 |
| `sections`（5 段）+ `outfits` | `t2c.sections` + `t2c.outfits` | 直接對齊 `docs/37_資源共用規格.md`（D26）；寫入後若已有漫畫專案則重跑 `bible_cards(overwrite=True)` |
| `vn.expressions`（非空項） | `expressions` | 對應 7 種基礎表情，至少含 `neutral` |

- 預設保護已標記 `confirmed: true` 的外觀卡，需使用者明確勾選覆蓋才寫入。

### 4.3 新章節增量同步
- 來源：`<book>/manuscript/ch-*.md`（相容 v2 `正文/`）
- 目標：`works/<book_id>/chapters/chNNN.json` 與 `book.json`
- **保護規則**：只新增未匯入章節或更新指定章節的 `chapters/chNNN.json`，**絕不刪除或覆蓋已校對的 `scenes/chNNN.json` 與 `gold/`**。
