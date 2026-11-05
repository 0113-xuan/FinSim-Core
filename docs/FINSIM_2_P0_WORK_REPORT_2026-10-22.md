# FinSim 2.0 P0 工作報告

- 日期：2026-10-22（Asia/Taipei）
- Repository：`0113-xuan/FinSim-Core`
- 範圍：只處理既有問題；本輪未實作 AI 問卷、需求擷取或推薦系統。

## 完成項目

### 1. 失業壓力測試判定

現行失業情境會在購車生效月起讓收入歸零三個月。原本仍直接套用「購車生效月最低每月結餘」門檻，因此所有案例在失業月都會因月結餘為負而失敗，即使現金與預備金足以承受衝擊。

新增 `stress_constraints()`：失業測試將失業期間的月結餘標記為 `applicable=false`，不把預期中的零收入視為額外失敗；最低現金與最低預備金仍照既有門檻判定。回應新增壓力測試層級的 `passed`。

回歸案例：

- 財務充足：通過現金與預備金條件。
- 財務緊繃：因最低現金／預備金不足而不通過。
- 無法承受失業：明確不通過。

### 2. 價格邊界搜尋效能驗證

工作區原有的 cent-boundary 搜尋修改仍保留，並以同一代表性請求比較舊浮點搜尋與目前版本：

| 版本 | 時間 | 結果 |
|---|---:|---:|
| 舊浮點搜尋 | 4.182 秒 | 1,198,119.21 |
| 目前 cent 搜尋 | 3.062 秒 | 1,198,119.21 |

改善約 26.8%，且結果一致。這是本機 warm Python benchmark，不代表正式部署 p95。

## 測試

- Python：`314 passed, 2 warnings`，74.98 秒。
- Node：`72 passed`。
- 警告是既有 API 測試使用短 JWT HMAC key，不是本輪新增。

## API 與財務計算影響

- 沒有新增或移除既有 API。
- 沒有改變 baseline、一般購車模擬、雙車比較或財務引擎的計算公式。
- 失業測試只調整壓力結果的適用性標記與整體判定口徑；失業現金流仍由原有 simulation engine 計算。

## 尚未解決

- 正式部署的冷啟動、並發與 p95 尚未量測。
- Python 測試數量與舊文件的 306 項不同，現況為 314 項；Node 現況為 72 項。
- 既有 JWT 短金鑰警告仍待另案處理。
- 車型資料來源、BEV 能源模型與 AI 需求擷取仍在 MVP 後續階段。

## 下一階段建議

先建立固定測試資料的三步驟問卷與規則式車款篩選流程，重用既有財務輸入與 API；完成基本流程後，再實作單一 Structured Outputs/Pydantic 需求擷取 API。不要在此之前加入多 Agent、完整 RAG 或新的財務模型。

## Review 注意事項

本輪開始前工作區已有未提交修改：`app/services/vehicle_decision.py`、`static/vehicle.html`、`static/vehicle.js`、`tests/test_vehicle_decision.py`、`tests/test_vehicle_ui.js`，以及未追蹤文件 `docs/AI_PERSONALIZED_CAR_RECOMMENDATION_PLAN_2026-10-20.md`、`docs/PROFESSOR_MEETING_2026-10-12.md`。本輪只在 `vehicle_decision.py`、`tests/test_vehicle_decision.py` 追加 P0 修正與測試，未覆蓋其他修改。
