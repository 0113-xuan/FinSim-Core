# Codex 任務：台灣歷史資料 Monte Carlo 與投資帳戶

日期：2026-10-31。完成後由 Claude 審查。

## 背景

- 目前 Monte Carlo 的通膨用 1%–5% 均勻抽樣，沒有資料來源。另外 `ProfileInput.inflation_rate` 預設為 0.02，所以從 API 進來的請求永遠不會抽樣；沒有隨機事件時，planner 的 p5、p50、p95 會完全相同。
- 這次改成用**台灣真實歷史資料**：主計總處 CPI 與台灣證交所「發行量加權股價報酬指數」（含股利再投入），用 12 個月區塊 bootstrap 抽樣。
- 同時加入**投資帳戶**：使用者的投資市值與每月投入會隨歷史報酬變動，計算結果另外顯示投資市值和淨資產（現金加投資）。**v1 永遠不會自動賣出投資**，現金不足就照實呈現。

## 工作規則

- 從 `feat/supabase-frontend` 建立新分支 `feat/historical-monte-carlo`。**不要 push**。
- 不讀 `.env`，不輸出任何 key。只 `git add` 你建立或修改的檔案，不要用 `git add .`。`docs/` 底下未追蹤的檔案與根目錄的 `futurewallet-flow.html` 不要動。
- 每個 commit 前執行 `python -m pytest -q` 和 `node --test tests/*.js`，全部通過才 commit。commit 結尾加上 `Co-Authored-By: Codex <noreply@openai.com>`。
- **購車流程的計算結果不可以改變**（`/decisions/vehicle*`、`vehicle.html`、`car-needs.html`）。現有的 vehicle 測試必須不修改就能通過。
- 不可以手打任何歷史數值。所有數字都必須來自下載的原始檔，經過程式轉換。

## 任務 A：歷史資料

所有資料放在 `data/market/`。程式執行時只讀這裡的 CSV，**不可以在執行時連網路**。

1. **台股報酬指數**：寫 `scripts/fetch_twse_total_return.py`。
   - 資料來源是 `https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U?date=YYYYMM01&response=json`，一次回傳一個月的每日數值，日期為民國年。
   - 從 2003-01 抓到最後一個完整月份，每月取最後一個交易日的數值。
   - 輸出 `data/market/twse_total_return_monthly.csv`，欄位為 `period,close`。
   - 每次請求之間至少間隔 3 秒，避免被證交所封鎖。
   - 執行一次，並把產生的 CSV commit 進去。
2. **CPI**：原始檔由使用者手動從主計總處匯出，放在 `data/market/raw/cpi_nstatdb.csv`。
   - 寫 `scripts/build_cpi.py`，把它轉成 `data/market/tw_cpi_monthly.csv`，欄位為 `period,cpi`。
   - 先讀原始檔的實際格式再寫解析程式。原始檔不存在時，停下來請使用者提供。
3. `data/market/SOURCES.md`：寫明兩份資料的發布機關、網址、查詢條件、下載日期、資料期間、授權方式，以及 CPI 的基期。
4. 寫 `app/core/market_data.py`，負責讀取兩份 CSV、在程式中快取，並提供：
   - 兩份資料共同期間的**成對月資料**：同一個月的通膨率 `cpi_t / cpi_{t-1} - 1` 與股市報酬 `close_t / close_{t-1} - 1`。
   - 年化幾何平均通膨率與年化幾何平均報酬率。
   - 資料期間與來源資訊，供回應使用。

## 任務 B：抽樣方式

- **12 個月區塊 bootstrap**：每次試驗從成對月資料中隨機選起點，連續取 12 個月，重複直到長度足夠，再截到模擬月數。起點可以是 `0` 到 `N-12`，不繞回開頭。
- 通膨與股市報酬**一定成對抽取**（同一個月份），以保留兩者的關聯。
- 使用 `seed` 時結果必須可以重現。
- 刪除舊的 1%–5% 均勻抽樣，以及為了保留舊亂數序列而多抽的那一行。

## 任務 C：計算引擎

`ProfileInput` 新增或修改以下欄位：

| 欄位 | 預設 | 說明 |
| --- | --- | --- |
| `inflation_rate` | **改成 `None`** | 使用者沒有提供時，確定性模擬用歷史年化通膨率，Monte Carlo 用抽樣路徑 |
| `investment_value` | 0 | 目前投資市值，不可小於 0 |
| `monthly_investment` | 0 | 每月從現金投入投資的金額，不可小於 0 |
| `expected_annual_return` | `None` | 只影響確定性模擬；沒有提供時用歷史年化報酬率 |

**通膨與調薪**沿用目前「每年調整一次」的規則：

- 第 k 年（k ≥ 1，也就是第 12k+1 到 12k+12 個月）的物價倍數 = 該路徑前 12k 個月的累積物價倍數。第一年為 1。
- 變動支出（以及 `fixed_expense_inflates` 為 true 時的固定支出）乘上這個倍數。
- `raise_rate` 為 `None` 時，薪資也乘上同一個倍數；有提供時維持 `(1 + raise_rate) ^ k`。
- 使用者有提供 `inflation_rate` 時，通膨固定不抽樣，跟現在一樣；股市報酬仍然抽樣。
- 確定性模擬等於把每個月的通膨與報酬都設成固定值，其他規則相同。

**投資帳戶**（每個月依序計算）：

1. `investment = investment × (1 + 當月報酬) + monthly_investment`
2. 現金減少 `monthly_investment`
3. 現金小於 0 時**不賣出投資**，投入也照常進行

其他要求：

- `monthly_investment` **不可以**算進 `living_expense`，緊急預備金月數只看生活支出與債務。
- 每月資料列加上 `investment_value` 和 `net_worth`（現金加投資）。
- 摘要加上 `final_investment_value`、`final_net_worth`。
- 現有的現金指標（最低現金、第一次現金小於 0、現金不足機率）定義不變，**只看現金**。

**購車流程**：如果 `vehicle_decision` 原本依賴 `inflation_rate` 的 0.02 預設值，要改成在 vehicle 那邊明確傳入原本的值，讓購車結果完全不變。

## 任務 D：Monte Carlo 回應

- 新增期末淨資產的 p5、p25、p50、p75、p95。
- 新增「以今日購買力計算」的期末淨資產 p5、p50、p95，算法是名目值除以該試驗的累積物價倍數。
- 新增 `data_sources`：每份資料的名稱、發布機關、網址、資料期間、下載日期。
- `sampled_parameters` 與 `sampling_note` 改成描述實際做法，至少包括：資料期間、12 個月區塊、通膨與報酬成對抽樣、哪些值因為使用者有提供而固定、`expected_annual_return` 不影響 Monte Carlo。
- `sampling_note` 必須加上這句話：「歷史期間台股表現特別好，過去報酬不代表未來。」

## 任務 E：planner 頁

- `static/planner-model.js`：不要再把 `monthly_investment` 轉成支出事件，改為直接送 `investment_value`、`monthly_investment`。同步更新測試。
- 結果區塊新增三項：期末投資市值、期末淨資產（p5、p50、p95）、以今日購買力計算的期末淨資產 p50。
- 刪除「投資市值尚未納入計算」的說明，改成顯示 `sampling_note` 與資料來源的名稱、期間。

## 任務 F：小修正

- `app/config.py` 的 `load_dotenv` 加上 `encoding="utf-8-sig"`，讓 `.env` 有沒有 BOM 都能正確讀取，並加一個測試。

## 必要的測試

- **資料完整性**：兩份 CSV 的月份連續、沒有缺月、數值都大於 0，共同期間至少 20 年。
- **抽樣**：同一個 seed 結果相同；每個區塊內的月份連續；通膨與報酬取自同一個月份。
- **投資帳戶手算案例**：初始 100,000、每月報酬固定 1%、每月投入 1,000，第 1、2、12 個月的市值要和手算結果一致，並把算式寫在測試註解中。
- **不自動賣出**：現金一路變成負數時，投資市值仍只隨報酬與投入變化。
- **緊急預備金**：`monthly_investment` 增加時，`living_expense` 不變。
- **調薪跟著實際通膨**：`raise_rate` 為 `None` 時，第 13 個月的薪資 = 原薪資 × 前 12 個月的累積物價倍數。
- **固定通膨**：提供 `inflation_rate` 時，各次試驗的物價倍數都相同，但期末淨資產仍然不同。
- **舊行為**：沒有投資、沒有事件時，確定性模擬的現金結果和使用歷史通膨率的手算結果一致。

## 不在本任務範圍

歷史回測（依序套用每個歷史起始月）、自動賣出投資、稅務、多個投資帳戶、前端視覺改版、`index.html` 舊頁面。發現相關問題時寫進回報，不要修改。

## 完成後的回報

1. 每個 commit 的 hash 與一句話說明。
2. 兩份資料的實際期間、筆數，以及年化通膨率、年化報酬率（四捨五入到小數第二位，用 %）。
3. API 欄位的新增、修改清單。
4. 測試指令與結果（通過數量、失敗數量）。
5. 沒有完成或刻意保留的部分，以及原因。
