# 加權指數 C浪追蹤（每日自動更新）

每個交易日台北 14:40，GitHub Actions 會自動抓 Yahoo Finance 的 ^TWII（日K、60分K、5分K），
重新繪製 日K、60分K 兩張波浪圖（含目前波浪標記、預估路徑、關鍵價位），輸出 docs/index.html。

## 部署（約 10 分鐘，免費）
1. 在 GitHub 建立新儲存庫（公開），把本資料夾全部上傳，需包含隱藏資料夾 `.github/workflows/update.yml`
   （網頁拖曳可能漏掉，建議用 git push，或在網頁 Add file → Create new file，路徑輸入 `.github/workflows/update.yml` 後貼上內容）。
2. Settings → Pages → Build and deployment → Source 選 **GitHub Actions**（不要選 Deploy from a branch）。
3. Actions → update → Run workflow，手動跑一次。成功後網頁網址會顯示在該次執行的 deploy 步驟。
4. 之後每個交易日自動更新。網址：https://你的帳號.github.io/儲存庫名稱/

## 台指期（含夜盤）資料流程
網頁有「加權指數／台指期（含夜盤）」兩個分頁。期貨圖由 1 分K 彙總成 5分K、60分K（日盤從 08:45、夜盤從 15:00 起算），灰底為夜盤。
1. **主要來源：期交所 MIS**（mis.py）。每次排程抓近月日盤（-F）與夜盤（-M）代號，轉成 1 分K，累積在 `data/txf_1m.csv`（工作流程會自動 commit 回儲存庫）。
2. **補充來源**：歷史不足（少於 6 個場次）時，嘗試用期交所逐筆成交檔回補（失敗不影響）。
3. 排程：台北 05:40（夜盤剛收）與 15:40（日盤剛收），各抓一次完整場次。

### 已確認的事實（使用者實測）
- 端點：POST https://mis.taifex.com.tw/futures/api/getChartData1M_mem，Payload `{"SymbolID": "TXFK6-F"}`。
- 日盤尾碼 -F、夜盤 -M；K=11月、6=2026年。Ticks 每筆 [HHMMSS, 開, 高, 低, 收, 量]，每筆是 1 分K。
- _mem 只回最新 2 根；時間標籤是 K 棒終點（程式減 1 分鐘）；整點可能寫成 HH6000、午夜 240000，程式用秒數相加處理。
### 尚未驗證
- getChartData1M（無 _mem）是否回傳整段場次歷史。第一次執行請看日誌 `mis:` 開頭的行：筆數約 300（日盤）或約 840（夜盤）代表可回補整段；只有 2 筆代表只能增量，此時要改成在自己電腦跑連續輪詢程式（tools/txf_collector.py 的做法），或改用較密的排程。
- 結算日遇假日順延、換月代號（例如 11/18 13:30 後改 TXFL6）。
- 國定假日靠「最新一根超過 2.5 小時」略過，未使用交易日曆。
- 夜盤歸屬哪個交易日各處說法不同，程式不依賴歸屬，直接依實際時間排列。

## 波浪規則檢查（config.json 的 rules）
1. 主升段③價差不能比①、⑤短。違反時，頂端卡片會出現「⚠ ③短於①與⑤」。
2. 若①>③>⑤（大中小），圖上會用淺灰底標出「拉回區（①高～②低，可破②低）」。
圖上標有①～⑤的波浪都會自動檢查；日K需在 `chartD.w_start` 設定①浪起點價位。

## 日常維護
- 波浪計數是你的判斷，程式不會自動數浪。要改圖上的波浪、預估路徑、價位線，請編輯 config.json：
  `chartD`（日K）/ `chart60` / `chart5`（期貨5分K沿用）內的 `waves`（[時間, 價位, 標籤]）、`main` / `alt`（[往後幾根K, 價位]）、`levels`、`tick_every`（日期標示間隔，60分K 為每 5 個交易日加當日）；`ref_low` 與 `v` 是頂端判斷文字的門檻。
- 本機測試：`pip install -r requirements.txt`，然後 `python update.py --offline`（用 sample/ 內的 CSV，不需網路）。

## 注意
- Yahoo 偶爾擋自動請求，失敗時 Actions 會顯示紅燈，重跑通常可解。
- 排程可能延遲數分鐘；儲存庫長期無活動，GitHub 會停用排程，到 Actions 頁面重新啟用即可。
- 台灣休市日（颱風假、國定假日）會抓不到新資料，頁面沿用上一個交易日。
- 個人研究工具，非投資建議。
