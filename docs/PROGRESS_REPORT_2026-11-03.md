# FutureWallet 進度回報（2026-11-02 ～ 11-03）

功能凍結：11/15。口試：11/19。

## 已上線（main，已 push，Render 已部署）

| commit | 功能 |
| --- | --- |
| f0e7820 | planner 拆成多頁：登入 → 填財務資料（onboarding）→ 儀表板 → 計畫頁 → 個人資料。儀表板有資產、負債、淨值卡片和各計畫的淨資產走勢 |
| 916caf3、2b3c164 | 車輛算進淨資產：車價逐年折舊，貸款剩餘本金扣除；計畫頁分開顯示「現金負擔」和「經濟成本」 |
| c896df6 | 首頁 `/` 改成導到登入頁 |

## 已完成、尚未合併到 main

以下分支一個接一個疊上去，目前都還沒合併到 main。

| 分支 | commit | 功能 | 審查 |
| --- | --- | --- | --- |
| `feat/ai-plan-explanation` | d959845、7e59184、72afbf7 | 計畫頁「用白話解釋結果」：數字由後端計算，AI 只能用 `{代號}` 寫數字，出現阿拉伯數字或中文數字就退回；AI 不可用時改用規則範本 | ✅ 通過（pytest 672、node 192） |
| `feat/event-template-picker` | 9474f1c | 建立計畫對話框：先輸入名稱，再選事件卡片（購車、換工作可用；買房、搬家、結婚、生小孩、旅遊、進修標「即將推出」） | 尚未審查 |
| `feat/vehicle-insurance-tax` | f79b795 | 購車保險明細（強制險必保，任意險可勾選並即時加總）與官方稅費（財政部牌照稅＋公路養管費，依排氣量計算） | 尚未審查 |
| `feat/location-parking-occupation` | fa07e3a | 財務資料新增所在地；購車選「沒有車位」時，列出該區停車場的參考資料（TDX 快照） | 尚未審查；只有第一階段，職業與薪資參考（第二階段）未見 commit |
| `feat/frontend-upgrade`（目前所在分支） | 2f17ff4、bd5447d、a0f9fde | 淨資產百分位區間圖、現金與投資拆分、假設條件說明；選好事件後跳過選擇畫面；TDX 支援更多縣市與月租解析修正 | 尚未審查 |

## 驗證結果（11/02）

- 多頁版 Playwright 完整流程：50/50 通過。涵蓋登入導頁、onboarding、儀表板、四種事件、模擬、購車分析、個人資料修改、手機版。
- 使用者用真的 Supabase 帳號測試，資料有存進 v2 四張表。

## 待辦（需要使用者操作）

1. **Render 環境變數**：要加在服務的 Environment，不是 Environment Group。`SUPABASE_URL` 前面不可以有空白。11/02 查詢時，線上的 `configured` 還是 false。
2. **Supabase Site URL**：設為 `https://finsim-core.onrender.com`。
3. **新增 profiles 欄位**：執行 `docs/supabase/04_profiles_location_occupation.sql`。
4. **舊資料表**：照 `docs/supabase/03_drop_legacy_tables.sql` 的步驟，先檢查、匯出 CSV，再刪除。
5. **真的 Gemini 測試**：本機設定 `AI_ENABLED`、`AI_PROVIDER=gemini`、`GEMINI_API_KEY` 後，測一次 AI 解釋。
6. **TDX 帳號**：如果停車場資料需要登入才能下載，免費註冊後執行下載 script。

## 待辦（開發）

- 審查 `feat/event-template-picker`、`feat/vehicle-insurance-tax`、`feat/location-parking-occupation`、`feat/frontend-upgrade`。
- 第二階段：職業與主計總處薪資參考，套用在換工作事件。
- 建議審查通過一個，就先合併到 main 並部署，避免 11/15 前一次合併太多分支。
- 之後：買房等事件範本、簡易 RAG、更新車款清單的價格（Toyota 試算顯示的價格和清單不同）。

## 已知限制

- 任意險保費是網路公開的參考範圍，不是報價；車體險的比例只來自一個範例車款。
- 停車場月租是從 TDX 收費說明文字解析出來的，不一定每間都有。
- 「千萬不要」這類用「千萬」加強語氣的句子，會被中文數字檢查誤擋，被擋時會改用規則範本。
