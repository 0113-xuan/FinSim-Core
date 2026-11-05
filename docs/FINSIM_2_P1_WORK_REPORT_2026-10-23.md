# FinSim 2.0 P1 三步驟選車問卷工作報告

日期：2026-10-23。狀態：P1 完成，待 Claude Review。

## 基準與 Git

- 開始時 HEAD：`a9eb20f8a0a48ce0feb9a14e4abf52289c279019`，與指定基準一致。
- 原有未追蹤文件全部保留。本輪未修改 Python、財務引擎、既有 API 或 P0 計算邏輯。
- 唯一既有檔案修改是 `static/vehicle.html`：頁首加入「幫我選車」連結。
- `git ls-remote origin refs/heads/main` 確認遠端仍為 `d3483f48e100ff94fcc71ee919472ba486bc0f23`；本機 main 領先10個commit。
- 本輪未 commit／push。日後確認推送權限與目標後，先 fetch、檢查 divergence，再以一般 `git push origin main` 同步；若遠端有新改動需整合，不強制推送。

## 完成內容

1. 從購車頁「幫我選車」進入 `/car-needs.html`。
2. 三步：基本條件、生活與財務、自由補充。進度條、上／下一步、返回修改、驗證與欄位錯誤提示均可操作。
3. 職業選填；預算與至少一個用途必填；里程不確定可留空。乘車人數與持有年限必填，其他偏好可略過。
4. 動力未指定或包含BEV才顯示充電問題；貸款才顯示頭期／利率／期數；勾選加入財務資料才要求收入、支出、存款、還款。
5. 貸款參數尚未決定可留空，確認頁明示未提供。此份資料仍是需求快照，不能直接當成已完整的 `VehicleDecisionRequest` 送去計算。
6. 確認頁列出答案、未提供項目、原始補充文字與Mock狀態；勾選確認後產生 `status=confirmed` 的需求JSON。
7. 支援查看、複製與下載JSON。返回修改會取消確認；再次確認才重新產生快照。
8. 完成頁顯示既有目錄前兩項，明確標示「非推薦結果」；可回原購車頁試算。沒有假裝推薦演算法已完成。

## 新增與修改檔案

| 檔案 | 用途 |
|---|---|
| `static/car-needs.html` | 三步問卷、確認頁、完成頁 |
| `static/car-needs.css` | 桌面／手機版面、焦點、錯誤與選取狀態 |
| `static/car-needs-state.js` | 獨立狀態、驗證、序列化、Mock候選與擷取adapter；可由Node測試 |
| `static/car-needs.js` | DOM渲染、事件、進度、確認、catalog讀取、JSON匯出 |
| `static/vehicle.html` | 加入問卷入口；原單車／雙車頁保留 |
| `tests/test_car_needs.js` | 新增9項前端狀態與需求契約測試 |
| `docs/FINSIM_2_P1_WORK_REPORT_2026-10-23.md` | 本報告 |

## 資料結構

實際確認後的範例（測試資料；省略候選明細與逐欄來源）：

```json
{
  "schema_version": "1.0",
  "revision": 7,
  "status": "confirmed",
  "currency": "TWD",
  "background": { "occupation": null },
  "constraints": {
    "budget_max": 800000,
    "budget_basis": "vehicle_price",
    "min_seats": 2,
    "avoid_body_types": []
  },
  "usage": {
    "purposes": ["commute"],
    "monthly_distance_km": null,
    "usual_passengers": 2,
    "ownership_years": 3,
    "home_charging": null,
    "public_charging": null
  },
  "preferences": {
    "body_types": [],
    "priorities": [],
    "powertrains": ["ice"]
  },
  "financial_profile": null,
  "payment": {
    "payment_method": "cash",
    "down_payment": null,
    "annual_interest_rate": null,
    "loan_term_months": null
  },
  "free_text": "希望停車方便",
  "extraction": {
    "provider": "mock",
    "is_real_ai": false,
    "status": "no_match",
    "candidates": []
  },
  "recommendation_handoff": {
    "status": "ready_for_p2",
    "engine_connected": false
  }
}
```

- 空白數字／單選保留 `null`，未指定的複選是空陣列；0只來自明確輸入。
- 選擇財務評估後，`financial_profile` 使用既有 `salary/balance/fixed_expense/variable_expense/required_monthly_debt` 名稱；`existing_debts/raise_rate/inflation_rate` 尚未蒐集而保留null。
- 利率畫面使用百分比，JSON轉成小數：3% → 0.03。
- 隱藏的財務資料不匯出；現金付款不匯出舊貸款值；不考慮BEV時充電值匯出null。
- `field_sources` 記錄 `user_provided` 或 `user_confirmed_mock`。所有欄位仍須在P2/P3後端重新驗證；P1的確認是前端狀態，沒有後端簽章／持久化。

## Mock 與 API 預留

- 畫面明示「模擬 AI 擷取 · 未連接 LLM」，資料明示 `provider=mock/is_real_ai=false`。
- 本機固定字面樣本：不喜歡SUV、載長輩、保養費低、五年後。只有原文明確包含樣本文字才回候選；不代表通用語意辨識。
- 候選不自動更改問卷；使用者逐項按套用，既有偏好／年限衝突時提示回第二步確認。
- 不匹配時保留原文，問卷仍能完成；職業不推導收入、里程或偏好。
- `createExtractionClient(transport)` 提供可注入的非同步接口，預留 `{text, related_answers, revision}` → extraction result。P3可換成HTTP transport；本輪沒有新增假API route或呼叫真實LLM。
- 原始文字以 `textContent` 顯示，沒有當成HTML插入。

## 測試與操作驗收

- Python：`python -B -m pytest -p no:cacheprovider -q` → **337 passed**，16.13秒；2則原有JWT測試金鑰長度警告。
- Node：所有9個 `tests/*.js` → **87 passed**，包含原有78項與新問卷9項。
- `git diff --check` 通過（只有既有 Windows line-ending 提醒）。
- 自動化新增範圍：null／0、職業不推論、必填／範圍／整數驗證、財務相容欄位、條件欄位隔離、APR換算、Mock證據／衝突／失效候選、確認失效與revision、未來transport注入。

瀏覽器使用Codex內建瀏覽器的Playwright locator操作；不是只讀靜態HTML。本輪沒有安裝新瀏覽器套件。

| 驗收 | 結果 |
|---|---|
| 從vehicle頁連結進問卷 | 通過 |
| 空表下一步、欄位錯誤、修正後前進 | 通過 |
| 桌面1440×1000：完整三步＋財務／貸款 | 通過 |
| 油電單選隱藏充電，加入純電顯示充電 | 通過 |
| Mock四候選逐項套用、確認checkbox gate | 通過 |
| 桌面完整JSON：薪資60000、APR0.03、還款0 | 通過 |
| 手機390×844：無財務、現金付款、里程留空 | 通過 |
| 上一步後人數、文字保留；重新確認可完成 | 通過 |
| 鍵盤Space切換checkbox、Enter前進 | 通過 |
| JSON複製與下載，下載檔可重新解析 | 通過 |
| 手機橫向溢位 | 無；document寬375≤viewport390 |
| 頁面／console | 內容正常、無框架錯誤頁、無error/warn |

截圖位於機器暫存目錄 `C:UsersweishengAppDataLocalTempinsim-p1-qa`：`desktop.png`、`mobile.png`、`mobile-review.png`。非Git提交檔案。下載測試產生 `C:UsersweishengDownloadsinsim-car-needs.json`（合成測試資料）。

視覺檢查以原購車工作區的白底、綠色主操作、6px控制項與原生表單為基準；檢查字級層級、欄位對齊、選取對比、按鈕、手機進度與寬度。修正了全域nav樣式干擾手機進度列，以及數字圓標在直排時被壓縮的問題。

## 本機使用與限制

- 本輪已啟動本機服務。開啟 `http://127.0.0.1:8000/car-needs.html`，或原購車頁右上角「幫我選車」。
- 重新啟動方式：在專案根目錄執行 `D:\DingFeng_Agent\Python312\python.exe main.py`。
- 資料只保留本分頁記憶體，重新整理會清除；可用JSON下載保存。沒有資料庫保存、真實AI或推薦排序。
- 尚未完成P2後端schema、規則推薦、P3真實擷取、P4需求預填既有財務頁；本輪只提供回試算頁連結。
- 已保留原單車／雙車畫面，337項Python與原78項Node回歸通過；沒有在本輪重跑所有原單／雙車瀏覽器數值展示案例。
- 後續停在Claude Review，請先檢查需求欄位、Mock標示、返回修改、JSON契約及P1範圍，再決定P2工作。
