# FutureWallet 前端升級與 Codex 三個 commit 審查報告（2026-11-03）

## 結論

- Codex 的三個 commit **通過審查**，沒有需要退回的問題：
  - 建立計畫對話框與事件選擇（`9474f1c`）
  - 購車保險明細與官方稅費（`f79b795`）
  - 所在地與停車場（`fa07e3a`）
- 前端升級已完成，做的是專題調整說明排定的前端項目：
  - P5–P95 淨資產分位數區間圖
  - 現金、投資、淨資產分開顯示
  - 「這次模擬用了哪些假設」面板
- 全部測試通過，Playwright 完整流程 29/29 通過。
- 前端升級的修改在 `feat/frontend-upgrade` 分支，**尚未 commit、尚未 push**。

## 專案背景

- **專案**：FutureWallet，靜宜大學資工畢業專題。repo 在 `D:\project\FinSim-Core`。
- **時程**：2026-11-15 功能凍結，2026-11-19 第二次口試。
- **原則**：Python 負責所有計算，前端只顯示；每個數字都要能說出來源。
- **分支關係**：`main` ← … ← `feat/ai-plan-explanation` ← `feat/event-template-picker`（`9474f1c`） ← `feat/vehicle-insurance-tax`（`f79b795`） ← `feat/location-parking-occupation`（`fa07e3a`） ← `feat/frontend-upgrade`（本次修改，未 commit）。
  - 以上分支都還沒合併到 `main`，也都沒有 push。

## 一、Codex 三個 commit 的審查

### 檢查方式與結果

| 檢查項目 | 指令／方式 | 結果 |
| --- | --- | --- |
| Python 測試 | `python -m pytest -q` | 765 passed |
| Node 測試 | `node --test tests/*.js` | 210 passed |
| 受保護檔案 | `git diff --stat c896df6 HEAD -- static/index.html static/app.js static/vehicle.* static/car-needs.* tests/test_vehicle*.py tests/test_planner_vehicle.py` | 只有新增的 `tests/test_vehicle_fees.py`，既有檔案都沒有修改 |
| 瀏覽器實測 | Playwright（Edge headless），真實 FastAPI 後端，Supabase 用 localStorage 模擬 | 見第三節，涵蓋對話框、事件選擇、保險稅費、所在地欄位 |

### 確認過的重點

- **建立計畫對話框**：
  - 用原生 `<dialog>`。按 Esc 關閉後，焦點回到原本的按鈕。
  - 「買房」等事件標示「即將推出」，有 `aria-disabled`，點了不會被選取。
  - 建立計畫後，網址的 `add` 參數會被移除，購車表單自動打開，焦點在事件名稱。
- **稅費**：
  - 使用牌照稅取自財政部稅務入口網（頁面更新日 115-04-09），公路養管費取自《公路使用養護安全管理費徵收及分配辦法》附表二。
  - Corolla Cross（1798 cc）顯示 7,120＋4,800＝11,920 元，和 Toyota 官方購車試算一致。
- **強制險**：Codex 取得了金管會的官方費率表（第 4 級首次投保）。預設值 1,398 元，是 30–60 歲男性的保費，並附上來源。
- **所在地**：行政區清單來自內政部資料，onboarding 頁有縣市和行政區欄位。

### 審查發現

| 等級 | 問題 | 證據 | 建議 |
| --- | --- | --- | --- |
| P1 | 停車場資料是空的，「附近停車場月租」功能目前沒有資料可以顯示 | `data/parking/taichung_carparks.json` 的 `status` 是 `awaiting_credentials`、`lots` 是空陣列；TDX 不登入時回傳 HTTP 401 | 使用者到 tdx.transportdata.tw 免費註冊，在本機環境變數設定 `TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`，再執行 `python scripts/fetch_tdx_parking.py` |
| P1 | 真實資料庫還沒有 `city`、`district`、`occupation` 欄位 | 需要執行 `docs/supabase/04_profiles_location_occupation.sql` | 在 Supabase SQL Editor 執行一次。這個 SQL 只新增選填欄位，不影響既有資料 |
| P2 | 月租價解析的測試案例是合理的範例，不是從真實資料抽樣 | `data/parking/SOURCES.md` 有註明 | 下載真實資料後，挑 10 種實際寫法補進測試 |
| P2 | 職業與薪資參考（第二階段）還沒做 | 任務說明的第二階段 | 照原本的順序交給 Codex |

## 二、前端升級（本次由 Claude 直接實作）

### 改了什麼

| 項目 | 內容 |
| --- | --- |
| 後端：每月分位數 | `/monte-carlo` 新增 `monthly_bands`：每個月底淨資產的 P5、P25、P50、P75、P95，以及現金、投資市值的 P5、P50、P95。另外新增 `historical_averages`（歷史平均通膨率、報酬率）。只是新增欄位，既有的數字都沒有改變。 |
| 後端：揭露假設 | `/simulate` 新增 `assumptions`：這次確定性模擬用的通膨率、調薪率、投資報酬率，以及每個數字的來源（使用者設定、歷史平均或抽樣）。 |
| 淨資產可能範圍圖 | 新的 Chart.js 區間圖：淺色是 90% 試驗的範圍（P5–P95），深色是中間一半（P25–P75），實線是中位數；事件月份有標記。圖下方的文字摘要說明 90% 範圍、中間一半，並註明「分位數線不是某一次試驗的實際路徑」。 |
| 現金、投資與淨資產圖 | 確定性模擬的圖從兩條線（現金、淨資產）改成三條線，多了投資市值，文字摘要也分成三行。 |
| 指標分組 | 原本混在一起的 14 個指標，改成「現金／投資／淨資產」三組，並新增期末投資市值的 P5 和 P50。手機寬度（420px 以下）改成單欄，避免數字從中間斷行。 |
| 假設面板 | 新增可以收合的「這次模擬用了哪些假設」：模擬期間、確定性通膨率（每年 1.34%，2003-02 至 2026-09 台灣 CPI 年化平均）、Monte Carlo 通膨抽樣方式、調薪率、確定性投資報酬率（每年 13.97%）、Monte Carlo 報酬抽樣、每月投資、預備金目標、試驗次數與亂數種子（300 次、種子 42），以及購車成本說明。資料來源和過去報酬警語也移進這個面板。 |

### 修改的檔案

- 後端：`app/core/monte_carlo.py`、`app/core/simulation.py`
- 前端：
  - `static/results-model.js`（新增，純函式）
  - `static/charts.js`、`static/plan.html`、`static/plan-page.js`、`static/shell.css`
  - 五個頁面加上載入 `results-model.js`
- 測試：`tests/test_frontend_upgrade_backend.py`（7 個）、`tests/test_results_model.js`（8 個）

## 三、測試結果

| 檢查項目 | 指令 | 結果 |
| --- | --- | --- |
| Python | `python -m pytest -q` | **772 passed**，0 failed（原本 765，加上新增的 7 個） |
| Node | `node --test tests/*.js` | **218 passed**，0 failed（原本 210，加上新增的 8 個） |
| Playwright 完整流程 | `%TEMP%\fw-pw\upgrade.e2e.js` | **29 passed**，0 failed |

### Playwright 驗證的項目

1. **登入與 onboarding**：登入後進到 onboarding，填財務資料和所在地（臺中市北屯區），儲存後進到儀表板。
2. **建立計畫對話框**：
   - 側欄「新增計畫」打開對話框，按 Esc 關閉後焦點回到原按鈕。
   - 「買房」標示即將推出，點了不會選取。
   - 選購車後建立計畫，網址的 `add` 參數已移除，購車表單已打開、焦點在事件名稱。
3. **購車事件**：選清單第一台車，稅費顯示 7,120＋4,800，事件儲存成功。
4. **240 個月模擬的區間圖**：
   - 5 條分位數線，241 個月份每個月都符合 P5≤P25≤P50≤P75≤P95。
   - 填色設定是 P95 到 P5、P75 到 P25。
   - 有購車月份的標記。
   - **圖上期末中位數 14,807,033.88，等於「期末淨資產中位數」指標**。
5. **確定性圖**：分開顯示現金、投資市值、淨資產三條線，文字摘要有三行。
6. **指標與假設面板**：
   - 指標分成三組，16 個指標都有值。
   - 投資 P5 小於 P50。
   - 假設面板列出所有項目，並含歷史資料期間和亂數種子；資料來源已移進面板。
7. **其他功能沒有被影響**：購車分析成功，儀表板的小走勢圖正常。
8. **手機與 console**：375px 寬度模擬成功，沒有橫向捲動；瀏覽器沒有 console 錯誤。

截圖都在 `C:\Users\weisheng\AppData\Local\Temp\fw-pw\`：

- `upgrade-plan-desktop.png`
- `upgrade-plan-mobile.png`
- `crop1.png`、`crop2.png`：結果區塊的裁切

## 四、沒有驗證的部分

- **真實 Supabase**：
  - 新欄位（所在地）存進真實資料庫，需要先執行 04 SQL。
  - 尚未執行 SQL 時的錯誤提示和重試流程，沒有在真實資料庫測過。
- **停車場清單**：資料是空的，所以「沒有車位時列出附近停車場」的畫面沒有實際顯示過。
- **AI 白話解釋**：還沒用真的 Gemini 跑過。
- **Render 線上網站**：上述分支都沒有部署；線上網站的 Supabase 環境變數，上次檢查時還沒有設好。

## 五、建議的下一步

1. **commit**：把前端升級 commit 到 `feat/frontend-upgrade`。
2. **合併與部署**：因為 11/15 就要凍結，建議盡快把已經審查通過的這一串分支合併到 `main` 並部署到 Render，萬一後面來不及，至少已完成的功能已經上線。
3. **使用者要做的事**：
   - 執行 `04_profiles_location_occupation.sql`。
   - 註冊 TDX，下載停車場資料。
   - 在 Render 設定 Supabase 和 AI 的環境變數。
4. **交給 Codex**：第二階段的職業與薪資參考。
