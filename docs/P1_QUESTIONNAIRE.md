# P1 三步驟個人化選車問卷

入口：啟動 `python main.py` 後開啟 `http://127.0.0.1:8000/car-needs.html`，或從購車頁點「幫我選車」。

## 功能與範圍

- 三步驟：基本條件、用車／財務、自由補充；最後檢查與確認需求。
- 返回修改保留答案，修改後必須重新確認；可以複製或下載JSON。
- 財務資料選填，未提供的數值保留null；選擇貸款後頭期款、年利率及期數必填。
- 頭期款為非負且小於車價預算，APR範圍0–98%（最多兩位小數），期數為1–600整數月，與目前車輛API範圍一致。實際選車後仍需依實際車價再次驗證貸款本金。
- 百分比利率以明確六位小數序列化：1.1%為0.011，0.7%為0.007。
- 確認及序列化皆重新檢查資料；即使直接改動confirmed旗標，驗證失敗也不能得到ready_for_p2。
- Mock候選有原文證據且必須逐項套用，不推定收入、里程或車款；「不是很在意」不視為正向偏好。「五年後」不推論持有年限，只有明確的「預計持有五年」等有限樣本才產生候選。
- 這是前端需求快照；沒有外部AI、推薦排序、綜合權重或新增財務公式。完成頁車款清單只是現有目錄預覽。
- 資料保留在分頁記憶體，重新整理會清除。後續後端必須重新驗證，這份JSON不是身分或授權憑證。

## 檔案與契約

- `static/car-needs.html/css/js`：問卷、確認、匯出與版面。
- `static/car-needs-state.js`：純狀態、validate、confirm、serialize與可注入的Mock extraction adapter。
- `static/vehicle.html`：問卷入口，同一提交必須包含以上四個目標資源。
- 輸出為schema_version=1.0、currency=TWD；包含background、constraints、usage、preferences、financial_profile、payment、free_text、extraction、field_sources、recommendation_handoff。
- 合法且確認的資料才輸出status=confirmed、handoff=ready_for_p2；其他為draft／awaiting_confirmation。

## 驗收

單元／整合測試：

```powershell
python -B -m pytest -p no:cacheprovider -q
node --test tests/test_profile_onboarding.js tests/test_scenario_draft.js tests/test_transparency.js tests/test_vehicle_ui.js tests/test_vehicle_stress_ui.js tests/test_vehicle_analysis_ui.js tests/test_vehicle_catalog_ui.js tests/test_vehicle_costs_ui.js tests/test_car_needs.js
```

瀏覽器測試請在暫存目錄執行，將URL換成待驗證server（可用獨立checkout的其他port）：

```powershell
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review open http://127.0.0.1:8000/vehicle.html --browser chrome
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review run-code --filename D:/project/FinSim-Core/tests/browser/car_needs.pw.js
npx --yes --package @playwright/cli playwright-cli -s=finsim-p1-review close
```

腳本使用目前page的origin，依序驗證1440×1000與390×844：入口、必填、貸款不可留空、錯誤無障礙描述、鍵盤、條件式欄位、Mock負向／正向、返回修改、需求確認、利率精度、JSON下載、無橫向溢位與無外部AI請求。截圖及下載檔寫入CLI目前目錄，不應加入Git。

乾淨提交驗證應從新的local clone啟動，不能複製原工作目錄的.env或未追蹤檔案。執行上述完整測試及瀏覽器腳本，確保入口和所有資源包含在提交內。
