# Pokerrrr 2 官方網站

目前以 OFC: Pineapple Poker 官網（ptfarm/master `cd3db8d`）為基礎，架構與流程同 OFC：純靜態網站，Cloudflare 部署 `public/`。

導覽列：Home／News／How to Play／About／FAQ／Store。News、FAQ、Store 的內容取自 Dorcas 的 demo；其他頁面暫時與 OFC 相同，之後再逐頁換成 Pokerrrr 2 的內容。

## 常用指令

```bash
python3 tools/build_i18n.py               # 改完文案或頁面結構後執行，產生 zh/、ja/、game-rules/、sitemap
python3 tools/preview_server.py          # 本機預覽 http://localhost:8000（支援無 .html 網址）
```

## 改哪裡

| 要改的東西 | 檔案 |
|---|---|
| 三語文案（含 title／description） | `public/js/i18n.js` |
| 頁面結構（英文版＝範本） | `public/index.html`、`how-to-play.html`、`about.html`、`faq.html`、`news.html`、`store.html`、`news-*.html` |
| 規則內容 | `data/game-rules.json`、`tools/templates/*.html` |
| 新增頁面 | 加進 `tools/build_i18n.py` 的 `PAGES` |

`public/zh/`、`public/ja/`、`public/game-rules/`、`sitemap.xml`、`robots.txt` 都是產生的，不要手改。
改 CSS／JS（包括 i18n.js）時，所有頁面與 `tools/templates/` 的 `?v=` 版本號要一起 +1。

## News（部落格）

- 每篇文章一個檔：`content/news/<slug>.md`（檔頭寫 title／date／author／category／cover／excerpt，內文可寫 HTML 或 Markdown）。
- 跑 `python3 tools/build_i18n.py` 會自動產生列表頁（`news.html` 中 `news:list` 標記之間）、文章頁 `news/<slug>.html`、`_redirects`（舊 Wix 網址 301）和 sitemap。
- 分類：`strategy`／`guides`／`stories`／`legends`／`pokerrrr2`；`featured: true` 的最新一篇會放在列表最上方（沒有就放最新的）。
- 圖片放 `public/assets/images/news/<slug>/`，在檔案中寫成 `assets/images/news/<slug>/01.jpg`。
- 文章內文只有英文；中日文的列表頁會列出同樣的英文文章。
- 舊站搬家：`python3 tools/fetch_wix_news.py --all`（需要網路，請在 Mac 終端機執行）→ `python3 tools/import_wix_news.py` → build。

## 網址一律不帶 .html

正式站（Cloudflare）會把 `/xxx.html` 301 到 `/xxx`、`/index.html` 到 `/`，Google 只收錄最後停留的網址，所以 canonical、hreflang、sitemap、`_redirects` 目標和所有站內連結都要用無 .html 的網址。

- `build_i18n.py` 最後一步會跑 `tools/clean_urls.py`，自動把產出頁面裡的 `.html` 連結改成無 .html（`about.html` → `about`、`index.html` → `./`），寫頁面或文章時照常寫 `.html` 檔名即可。
- 圖片、CSS、JS 等資源路徑不受影響。
- 本機預覽請用 `tools/preview_server.py`；`python3 -m http.server` 打不開無 .html 的網址。

