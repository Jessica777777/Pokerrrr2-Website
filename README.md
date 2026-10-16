# Pokerrrr 2 官方網站

純靜態網站（HTML／CSS／JS），由 `tools/build.py` 從 `src/` 與 `data/` 產生 `public/`。架構參考 OFC: Pineapple Poker 官網，設計以 Dorcas 的 demo 為準。

## 常用指令

```bash
python3 tools/build.py        # 產生所有頁面（改完任何 src/、data/ 後都要跑）
python3 tools/build.py -v     # 同上，並列出中文／日文還沒翻譯的 key
cd public && python3 -m http.server 8000   # 本機預覽 http://localhost:8000
```

## 目錄

| 路徑 | 內容 | 可以手改？ |
|---|---|---|
| `src/layout.html` | 頁面外框（head、導覽列、頁尾插槽） | ✅ |
| `src/partials/` | 共用片段：導覽列、頁尾、下載徽章、下載區塊 | ✅ |
| `src/pages/` | 首頁、About、FAQ、Store（英文原文寫在 HTML 裡） | ✅ |
| `src/templates/` | 由資料產生的頁面：News 列表、文章、規則總覽、規則頁 | ✅ |
| `data/site.json` | 網域、語言、下載連結、商店、Terms 連結 | ✅ |
| `data/i18n/zh.json`、`ja.json` | 中文、日文翻譯（key 對應 `data-i18n`） | ✅ |
| `data/i18n/en.json` | 所有 key 的英文原文（給翻譯參考） | ❌ build 產生 |
| `data/faq.json` | FAQ 內容（9 類） | ✅ |
| `data/news.json` | 文章（`published` 才會產生頁面，`draft` 不會） | ✅ |
| `data/game-rules.json` | 規則內容（三語，沿用 OFC 官網） | ✅ |
| `data/rules-meta.json` | 規則頁的 title／description／H1／卡片文字 | ✅ |
| `public/css/`、`public/js/`、`public/assets/` | 樣式、程式、圖片 | ✅ |
| `public/*.html`、`public/news/`、`public/game-rules/`、`public/zh/`、`public/ja/`、`sitemap.xml`、`robots.txt` | 產生的頁面 | ❌ build 產生 |

## 多語系

- 英文寫在原始 HTML；要翻譯的元素加 `data-i18n="key"`，屬性用 `data-i18n-attr="alt:key"`。
- 中文／日文缺翻譯時會先顯示英文，build 結束會列出還沒翻的數量。
- `site.json` 裡語言狀態是 `draft` 時：頁面照樣產生可預覽，但加上 `noindex`，不放進 hreflang 和 sitemap。翻譯完成後改成 `live`。

## 換網域、換下載連結

- 網域：改 `data/site.json` 的 `base_url`，重跑 build。
- OneLink：把 `download.app_store`、`download.google_play` 都換成 OneLink，重跑 build。
- CSS／JS 的快取版本號由 build 依檔案內容自動計算，不用手動 +1。

## 素材

原始美術檔放 `素材/`（不進 git），處理、壓縮後再放進 `public/assets/images/` 對應資料夾。
