# FinSim 2.0 P1 選車問卷補齊與驗收

日期：2026-10-25。狀態：P1 完成，停在 Claude Review。

## 現況與範圍

- HEAD 確認為 `a9eb20f8a0a48ce0feb9a14e4abf52289c279019`。
- 10/23 的三步問卷已存在於未追蹤檔案，本輪沿用並補齊，沒有重做 P0。
- 所有既有未追蹤文件與原 `static/vehicle.html` 問卷入口修改保留。
- 本輪沒有修改財務公式、正式 API、單車或雙車服務，也未 commit、push、部署。

## 完成功能

1. 三步問卷：基本條件、用車與財務、自由補充；上／下一步、條件式問題、欄位驗證、返回修改與需求確認。
2. 補上停車方式與選填的每月停車預算；自有車位不自動填0，未指定或尚無車位時不匯出殘留預算。
3. 更新本機 Mock 樣本，能示範「不喜歡休旅車、常載長輩、後座舒服、保養費不要太高」。每項有原文證據，須逐項套用。
4. 明確否定的長輩接送／舒適偏好不會被這組 Mock 規則反向套用；仍只是有限字面樣本，不是通用中文語意解析。
5. 修正錯誤提示的無障礙描述：清除過期 error reference，同時保留原本的字數說明。
6. 確認頁列出所有答案、原始文字與 Mock 狀態；確認後提供 JSON 查看、複製、下載與回原試算頁入口。
7. 保留未填數值為null；未指定複選為空陣列；職業不推定收入、里程或車型。

## 新增與修改檔案

以下以本輪開始時工作目錄為基準：

| 檔案 | 變更 |
|---|---|
| `static/car-needs-state.js` | 停車狀態／驗證／輸出；中文 Mock 樣本與否定處理 |
| `static/car-needs.html` | 停車欄位、補充範例、20261025版本查詢字串 |
| `static/car-needs.js` | 停車欄位顯示、確認摘要、無障礙錯誤描述 |
| `tests/test_car_needs.js` | 新增3項，共12項狀態／資料契約測試 |
| `tests/test_car_needs_integration.py` | 新增2項實際FastAPI頁面／靜態資源／catalog依賴整合測試 |
| `tests/browser/car_needs.pw.js` | 新增可重跑的桌面／手機Playwright流程 |
| `docs/FINSIM_2_P1_WORK_REPORT_2026-10-25.md` | 本報告 |

既有P1檔案 `static/car-needs.css`、購車入口 `static/vehicle.html` 與 10/23 報告沿用。從Git HEAD看，P1檔案多數仍屬未追蹤檔案，並非已提交成果。

## 資料結構範例

以下為確認後的節錄；完整輸出另含revision、自由原文、候選明細與逐欄來源：

```json
{
  "schema_version": "1.0",
  "status": "confirmed",
  "currency": "TWD",
  "background": { "occupation": null },
  "constraints": {
    "budget_max": 1000000,
    "budget_basis": "vehicle_price",
    "min_seats": 3,
    "avoid_body_types": ["suv"]
  },
  "usage": {
    "purposes": ["commute", "elderly_transport"],
    "monthly_distance_km": null,
    "usual_passengers": 3,
    "ownership_years": 5,
    "parking_type": "rented",
    "monthly_parking": 3000,
    "home_charging": "no",
    "public_charging": "yes"
  },
  "preferences": {
    "body_types": [],
    "priorities": ["maintenance_cost", "comfort"],
    "powertrains": ["hev", "bev"]
  },
  "financial_profile": {
    "salary": 60000,
    "balance": 500000,
    "fixed_expense": 12000,
    "variable_expense": 8000,
    "required_monthly_debt": 0,
    "existing_debts": null,
    "raise_rate": null,
    "inflation_rate": null
  },
  "payment": {
    "payment_method": "financed",
    "down_payment": 200000,
    "annual_interest_rate": 0.03,
    "loan_term_months": 60
  },
  "extraction": {
    "provider": "mock",
    "is_real_ai": false,
    "status": "candidates"
  },
  "recommendation_handoff": {
    "status": "ready_for_p2",
    "engine_connected": false
  }
}
```

財務欄位沿用 `DecisionProfile` 名稱；尚未收集的調薪／通膨與債務明細保持null。這份JSON是需求快照，並非完整可直接提交的 `VehicleDecisionRequest`。P2/P3仍須做後端驗證、補齊計算條件與確認管理。

## 測試結果

- Python：`D:\DingFeng_Agent\Python312\python.exe -B -m pytest -p no:cacheprovider -q` → **339 passed**，20.86秒。原337項與新增2項全部通過；有2則既有JWT測試金鑰長度警告。
- Node：原8個測試檔＋`tests/test_car_needs.js` → **90 passed**；原78項與問卷12項全部通過。
- Playwright：同一腳本於 **1440×1000** 桌面與 **390×844** 手機各走完一次。
- 兩個尺寸皆驗證：入口、空表必填、鍵盤Space/Enter、BEV充電問題、停車負數驗證、返回保留答案、四項Mock逐項套用、確認checkbox gate、JSON內容與下載、修改需求入口、無橫向溢位。
- 桌面另外核對薪資／支出映射、停車3000、APR 3%→0.03；手機核對不提供財務資料與尚無車位時輸出null。
- 腳本檢查無pageerror、無`/ai/`請求、無推薦score欄位。問卷頁console無error/warn。
- 購車入口初次載入有既有 `/favicon.ico` 404；與問卷功能無關，沒有擴大本輪範圍修正。

內建瀏覽器工具兩次因kernel assets路徑遺失無法啟動，故依前端測試技能改用Playwright CLI的隔離Chrome session。沒有修改專案package dependencies。

重跑瀏覽器流程（先啟動本機服務；CLI的工作目錄建議設為暫存目錄）：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review open http://127.0.0.1:8000/vehicle.html --browser chrome
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review run-code --filename D:/project/FinSim-Core/tests/browser/car_needs.pw.js
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review close
```

桌面／手機及完成頁截圖位於 `C:\Users\weisheng\AppData\Local\Temp\finsim-p1-*-20261025.png`，不列入Git。下載樣本位於同一暫存目錄的 `.playwright-cli/finsim-car-needs.json`，均為合成測試資料。

## 本機使用與未串接項目

- 開啟 `http://127.0.0.1:8000/car-needs.html`；或原購車頁的「幫我選車」。
- 若需啟動：在 `D:\project\FinSim-Core` 執行 `D:\DingFeng_Agent\Python312\python.exe main.py`。
- 資料保留在本分頁記憶體，上／下一步不會清除；重新整理會清除，可先下載JSON。
- 尚未接入真實LLM、車款推薦、五年現金支出排序、偏好符合標記或個人負擔能力串接；現有目錄只是明示的預覽。
- 本輪沒有加入推薦權重或綜合分數。後續按硬條件篩選、五年車輛現金支出排序、偏好符合標記及既有財務引擎處理。
- P1完成後停止，交Claude Review；不自行展開P2。
