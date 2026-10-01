# FinSim 2.0 Sprint 1 實作報告

日期：2026-10-01。未建立 Git commit，保留原工作區既有修改。

## A. 本次新增與修改檔案

| 檔案 | 變更與用途 |
|---|---|
| `app/core/financial_rules.py`（新增） | 共用預備金月數、缺口、年度通膨與 None fallback |
| `app/core/events.py` | 零收入、零薪資、零固定支出倍率不再被預設值覆蓋 |
| `app/core/expenses.py` | 快速模式採 profile 通膨；零變動支出倍率有效 |
| `app/core/simulation.py` | 月資料包含生活必要支出與預備金；既有必要月付；固定支出通膨選項；新流程停用舊風險評估 |
| `app/core/fsi.py` | 僅改用共用預備金分母，未建立新 FSI 公式 |
| `app/core/monte_carlo.py` | 舊流程缺口計算改用共用函式，未新增 Monte Carlo 功能 |
| `app/scenario_schemas.py` | typed 車輛輸入新增交通費抵減 |
| `app/services/scenario_engine.py` | 交通抵減建立獨立正向現金事件，不與車貸重複 |
| `app/services/scenario_parser.py` | 舊維護預算也引用集中假設，數值維持相容 |
| `app/decision_assumptions.py`（新增） | 薪資、通膨、持有成本、限制與壓測的集中規劃假設 |
| `app/decision_schemas.py`（新增） | 嚴格購車請求、財務輸入、限制與適用範圍驗證 |
| `app/services/vehicle_decision.py`（新增） | typed 建構、同一引擎模擬、獨立評估、四壓測與二分搜尋 |
| `main.py` | 新增購車決策與假設 API，不變更舊路由契約 |
| `static/vehicle.html`（新增） | 一頁財務與車輛表單、假設確認、獨立結果頁 |
| `static/vehicle.css`（新增） | 沿用既有色彩與樣式，手機單欄、表格局部捲動 |
| `static/vehicle.js`（新增） | typed API 提交、來源、比較、壓測、上限與單一現金圖；無財務公式 |
| `static/index.html` | 增加購車決策入口，保留舊工作區 |
| `tests/test_decision_reliability.py`（新增） | 8 個核心回歸與 PMT／通膨／預備金測試 |
| `tests/test_vehicle_decision.py`（新增） | 16 個購車、壓測、上限、來源、驗證與隔離測試 |
| `tests/test_vehicle_ui.js`（新增） | 4 個腳本、確認、圖表、API 邊界與響應式契約測試 |
| `.gitignore` | 排除環境變體、金鑰、secrets 目錄 |
| `.gitattributes`（新增） | git archive 排除環境檔、金鑰與執行日誌 |
| 本報告（新增） | 稽核、測試、限制與驗收紀錄 |

未刪除檔案。其他 `git status` 修改包含先前工作，不能全部歸因本 Sprint。

## B. 架構與稽核結果

既有系統為 FastAPI / Pydantic 2、原生 HTML/CSS/JavaScript 與 Chart.js，沒有前端編譯框架。未新增套件。

原始職責對照：income events / PMT 在 `core/events.py`；通膨在 `core/expenses.py`；baseline 在 `core/simulation.py`；車輛 typed 建構在 `services/scenario_engine.py`；自然語言橋接在 `services/scenario_bridge.py`；契約在 `scenario_schemas.py`；FSI 在 `core/fsi.py`；Monte Carlo 在 `core/monte_carlo.py`；optimizer 在 `services/optimizer.py`；advisor 在 `core/advisor.py`；舊結果 UI 在 `static/app.js`、`static/transparency.js`、`static/index.html`。

新路徑：

```text
vehicle.html 表單 + 假設確認
  -> POST /decisions/vehicle
  -> VehicleDecisionRequest + ScenarioRequest (vehicle_purchase)
  -> resolve: 補有來源的可覆寫假設
  -> build_scenario: 共用 typed 事件與貸款
  -> simulate_finance(evaluate_legacy_risk=False)
  -> evaluate: 現金與限制
  -> 同一引擎四壓測 / 二分搜尋
  -> vehicle.js: 只格式化與繪圖
```

`GET /decisions/vehicle/assumptions` 提供假設登錄表。新 API 不呼叫 AI、資料庫、optimizer、advisor 或 Monte Carlo。AI 不參與計算。

模擬沿用既有引擎；新評估與搜尋不另寫 PMT 或月現金公式。既有 ProfileInput 為保留相容性而不重建；新增 DecisionProfile 明確限制只有現金、收支與既有月付。

## C. 修正的計算問題

1. 先新增測試，觀察 4 failed / 1 passed：零收入 1 月、失業 3 月、薪資設零、不同通膨結果相同。
2. 將 `or 1.0`、`or salary` 改為只對 None 套預設。零收入與零支出倍率有效。
3. 快速支出模式不再將所有分類鎖在 2%；採 profile 通膨。進階分類明確指定的通膨維持覆寫。
4. 共用預備金定義：現金 /（生活必要支出 + 必要還款）。新結果取全期最低月數，而非僅期末。
5. 保險、稅費、維護、油電、停車及交通抵減都可輸入並標示來源，不只計車貸。
6. 保留 PMT：500,000 / 3% / 60 月 = 8,984.35 元；全期利息 39,061 元（以分位月付款計算）。

## D. 功能與數值定義

- 比較基準與購車後：生效月份每月結餘、最低現金與月份、最低預備金月數、一次性現金需求、60 個月現金差額、車貸月付與全期利息。
- 生效月結餘排除一次性支出；不是全期平均，也不宣稱未來每月都保持相同。
- 期間為基準月份後的 60 個月；購車必須在第 1 至 58 個月，以完整包含失業三個月。
- 四壓測在購車月份生效：收入永久 -10%、收入為零 3 月、一次性 100,000 元支出、貸款利率 +2 百分點。現金購車利率壓測標記不適用。
- 壓測事件由集中系統假設定義；數值由同一引擎計算，不是機率或財務建議。
- 二分搜尋維持同一頭期款、期數、持有成本與購買日期，只改車價；精度 0.01 元。
- 上限回傳限制實際值、要求、通過狀態及增加 1% 後違反項目。無可行解、搜尋／驗證範圍限制均回傳明確狀態，不捏造最大車價。
- 車價模型上限 2,000 萬元。輸入利率上限 98%，保留壓測增加 2 百分點空間。
- 年度通膨每滿 12 個月調整：變動支出、持有預算、交通抵減；固定支出預設固定名目，可勾選調整；貸款與既有月付固定名目。
- 年度持有費用按月提列，未模擬實際年度繳款日。
- 來源維持 typed 模型，對外整理為 user / derived / system_assumption。前端提供來源表與引擎計算標示。
- 新頁面無 FSI、破產機率、advisor 分數、optimizer 或通用報告器。

## E. 測試

| 項目 | 修改前 | 修改後 |
|---|---:|---:|
| Python pytest | 240 passed | 264 passed |
| Node 前端測試 | 38 passed | 42 passed |
| 新增 | — | Python 24、Node 4 |

執行命令：

```text
python -m pytest -q
node --test tests/test_profile_onboarding.js tests/test_scenario_draft.js tests/test_transparency.js tests/test_vehicle_ui.js
node --check static/vehicle.js
git diff --check
```

覆蓋零收入、3 月失業、零薪資、零支出倍率、通膨傳播、進階覆寫、PMT 黃金值、預備金含債務、持有費與抵減只算一次、每個持有欄位零元覆寫、價格與費用單調性、決定性、來源、錯誤日期／利率／抵減、無可行解、搜尋範圍限制、上限及 +1%、新路徑不呼叫 legacy risk / AI。

瀏覽器使用 Codex CUA 實際操作：以標準 65 萬車價／15 萬頭期案例填表、勾選確認、送出，取得 baseline、購車結果、四壓測、約 119.8 萬車價上限；圖表繪製兩條現金線及最低點。桌面未見 console error/warn。390px 手機檢查無整頁水平溢出，寬表局部捲動。Node 新測試為靜態契約與語法測試，不假裝完整 E2E 自動測試。

設計檢測器執行一次，因缺少 HTML parser 套件降級為 regex；未回報匹配問題，但不視為完整可及性驗證。

## F. 已知限制與安全

- 模型只計月底現金，不計車輛殘值、投資資產、淨資產、月內付款順序、手續費或提前清償。利息採既有分位 PMT，末期微小攤還調整未另建。
- 既有必要還款視為 60 個月固定月付，尚未提供每筆舊債到期日。結果頁需以此假設解讀。
- 預備金分母為零時新結果回傳 null（不適用、無支出約束）；舊摘要欄位保留 0 相容值，舊 FSI 視為沒有預備金缺口。新流程不使用舊欄位替代 null。
- 新頁面需手動輸入，不呼叫 AI；舊自然語言功能保留於舊工作區，未移植預填。
- 車輛預算是規劃假設，不是外部價格或保險報價。交通抵減需由使用者確認已計入原生活支出。
- 可負擔上限只對目前列明限制成立，不要求所有壓測同時通過。壓測結果另行呈現。
- 上限尚無新增每使用者速率限制，僅供本機使用；對外部署前應加資源限制與效能量測。
- Chart.js 使用固定版本 CDN；離線時圖表可能不可用，現金明細仍可讀取。
- 原有 JWT 測試出現 2 個短金鑰警告。本次不覆寫使用者 `.env`，也不改驗證系統。
- `git ls-files` 未發現 `.env` / `.pem` / `.key`；`git log --all -- .env` 無結果。這不是完整歷史密鑰鑑識。新增 ignore 與 git archive 排除；手動壓縮整個目錄仍須排除 `.env` 與日誌，Git 規則無法限制任意 ZIP 工具。
- 沒有做全套人工可及性研究、跨瀏覽器矩陣或多人負載測試。

## G. 延後工作與舊邊界

- `app/routes.py` 明確標記 legacy，main.py 未 include；保留以免破壞既有 import 相容測試。
- 舊 `/simulate`、Monte Carlo、compare、optimizer 與報告路徑繼續服務舊工作區；不被新購車頁呼叫。
- `services/scenario_bridge.py` 是舊自然語言到 typed 的橋接；新表單直接傳 typed，不依賴舊解析器。
- `scenario_engine._delta` 為舊比較摘要，與新 evaluator 有語意相近但不同的輸出；未進行危險大刪除。新決策僅使用新 evaluator。
- 後續：legacy 清理、搬家／工作 offer 決策、敏感度分析、AI 預填改善、Monte Carlo 重新評估、可用性研究。均未在本次擴充。

## H. Definition of Done 檢查

- [x] 既有相關測試通過。
- [x] 新回歸與正確性測試通過。
- [x] income_multiplier=0 的收入為零。
- [x] 3 個月失業壓測有效。
- [x] 通膨傳入敏感支出。
- [x] 預備金共用定義；零分母舊版序列化例外已明列。
- [x] 主要車輛持有費完整且可覆寫。
- [x] 車輛假設有來源。
- [x] PMT 參考案例通過。
- [x] 新頁面不以 FSI 為指標。
- [x] 新頁面不顯示破產機率。
- [x] 新決策不使用 optimizer / advisor。
- [x] 四個確定性壓測運作。
- [x] 可負擔邊界搜尋運作，無解／範圍限制有明確結果。
- [x] 有界 P* 通過限制。
- [x] 有界 P* × 1.01 違反至少一項限制；超出支援範圍則不宣稱找到邊界。
- [x] 相同輸入回傳完全相同結果。
- [x] baseline vs scenario 結果頁運作。
- [x] 單一雙曲線現金圖與最低點運作。
- [x] 假設與來源可查看。
- [x] 未擴充其他決策、AI 報告或新驗證系統。

入口：http://127.0.0.1:8000/vehicle.html
