# Pokerrrr 2 官方網站

目前以 OFC: Pineapple Poker 官網（ptfarm/master `cd3db8d`）為基礎，架構與流程同 OFC：純靜態網站，Cloudflare 部署 `public/`。

導覽列：Home／News／How to Play／About／FAQ／Store。News、FAQ、Store 的內容取自 Dorcas 的 demo；其他頁面暫時與 OFC 相同，之後再逐頁換成 Pokerrrr 2 的內容。

## 常用指令

```bash
python3 tools/build_i18n.py               # 改完文案或頁面結構後執行，產生 zh/、ja/、game-rules/、sitemap
cd public && python3 -m http.server 8000  # 本機預覽 http://localhost:8000
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

## News 文章

- 文章頁是根目錄的 `news-<名稱>.html`，內文目前只有英文（中日文版頁面也顯示英文內文）。
- 新增文章：複製一個 `news-*.html` 改內容 → 在 `news.html` 加卡片 → 加進 `PAGES` → 跑 build。
