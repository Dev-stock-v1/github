# 加權指數 C浪追蹤（每日自動更新）

每個交易日台北 14:40，GitHub Actions 會自動抓 Yahoo Finance 的 ^TWII（日K、60分K、5分K），
重新繪製 日K、60分K 兩張波浪圖（含目前波浪標記、預估路徑、關鍵價位），輸出 docs/index.html。

## 部署（約 10 分鐘，免費）
1. 在 GitHub 建立新儲存庫（公開），把本資料夾全部上傳，需包含隱藏資料夾 `.github/workflows/update.yml`
   （網頁拖曳可能漏掉，建議用 git push，或在網頁 Add file → Create new file，路徑輸入 `.github/workflows/update.yml` 後貼上內容）。
2. Settings → Pages → Build and deployment → Source 選 **GitHub Actions**（不要選 Deploy from a branch）。
3. Actions → update → Run workflow，手動跑一次。成功後網頁網址會顯示在該次執行的 deploy 步驟。
4. 之後每個交易日自動更新。網址：https://你的帳號.github.io/儲存庫名稱/

## 台指期（含夜盤）
網頁上方有「加權指數／台指期（含夜盤）」兩個分頁。期貨圖由期交所「前30個交易日期貨每筆成交資料」逐筆彙總成 5分K、60分K（日盤從 08:45、夜盤從 15:00 起算），灰底為夜盤。
- 排程：台北 05:40（補前一晚夜盤）與 15:40（日盤收盤後）各跑一次。
- 取近月合約（當日成交量最大的月份）。換月日價格會有跳空，屬正常。
- 圖上的波浪與價位線取自加權圖，依「期現價差」平移，僅供參考。
- 第一次在 GitHub 跑時，請看 Actions 日誌的 `futures:` 開頭行，確認每天都有抓到筆數；若顯示 no file，代表下載網址需要調整，把日誌貼給我。

## 日常維護
- 波浪計數是你的判斷，程式不會自動數浪。要改圖上的波浪、預估路徑、價位線，請編輯 config.json：
  `chartD`（日K）/ `chart60` / `chart5`（期貨5分K沿用）內的 `waves`（[時間, 價位, 標籤]）、`main` / `alt`（[往後幾根K, 價位]）、`levels`、`tick_every`（日期標示間隔，60分K 為每 5 個交易日加當日）；`ref_low` 與 `v` 是頂端判斷文字的門檻。
- 本機測試：`pip install -r requirements.txt`，然後 `python update.py --offline`（用 sample/ 內的 CSV，不需網路）。

## 注意
- Yahoo 偶爾擋自動請求，失敗時 Actions 會顯示紅燈，重跑通常可解。
- 排程可能延遲數分鐘；儲存庫長期無活動，GitHub 會停用排程，到 Actions 頁面重新啟用即可。
- 台灣休市日（颱風假、國定假日）會抓不到新資料，頁面沿用上一個交易日。
- 個人研究工具，非投資建議。
