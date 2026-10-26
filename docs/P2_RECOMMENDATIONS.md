# P2 個人化車款推薦工作報告

日期：2026-10-26。基準：`30fa3c96194cc2f5cc1bc77f325e3dc6d056f841`。

## 使用方式

啟動既有 FastAPI 後進入 `/car-needs.html`，或由 `/vehicle.html` 的「幫我選車」進入。
完成三步問卷、勾選確認需求，再按「查看符合條件車款」。
完整排名需要里程、停車預算及付款方式；零里程、免費停車須明確填 0。
財務資料仍為選填；未提供時不宣稱已通過負擔能力評估。

## 資料與來源

目錄為 **7 個版本、4 個車系**，不是全市場車款資料庫。包含三種動力，非 SUV 車系有 FIT、Altis、Model 3。
查詢日皆為 2026-10-26；官網未明示年式時 `model_year=null`，不把查詢年份當成年式。

| 版本 | 官方參考售價 TWD | 官方效率 | 官方來源 |
|---|---:|---:|---|
| Corolla Cross 汽油豪華 | 809,000 | 14.3 km/L | [Toyota 完整規配](https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx) |
| Corolla Cross HYBRID 豪華 | 849,000 | 23.5 km/L | 同上 |
| Corolla Cross HYBRID 旗艦 | 989,000 | 23.5 km/L | 同上 |
| FIT HOME 汽油版 | 759,000 | 17.9 km/L | [Honda FIT](https://www.honda-taiwan.com.tw/Auto/Cars/FIT) |
| FIT e:HEV 油電版 | 829,000 | 26.9 km/L | 同上 |
| Corolla Altis 汽油經典 | 735,000 | 15.7 km/L | [Toyota Altis 售價規配](https://www.toyota.com.tw/showroom/ALTIS/) |
| Model 3 Long Range 後輪驅動 | 1,749,900 | 未核對，null | [Tesla 訂購](https://www.tesla.com/zh_tw/model3/design?redirect=no)、[規格](https://www.tesla.com/zh_tw/model3-performance) |

售價不是成交價；官方實驗室效率不是實際道路保證。Model 3 缺可核對電耗與成本校準，顯示「資料不足」，不計算或排名、不用 0 代替。
保險每年 20,000、稅費每年 12,000、維護每年 18,000，沿用既有 `ASSUMPTIONS`，**不是個別車款官方價格或稅額**。
油價 30 TWD/L 是比較假設，非即時市場報價；停車採使用者明確輸入。

## 規則與財務口徑

1. 伺服器重新驗證 P1 完整 JSON；不以 `confirmed` 或 `ready_for_p2` 取代欄位驗證。
2. 硬條件：車價預算、座位、排除車型；住家與公共充電皆明確不可用時排除純電車。未知資料不是不符合。
3. 缺必要成本輸入、官方效率或價格時列「資料不足」。頭期款與實際目錄售價再次核對。
4. 可完整計算車款依 **60 個月車輛現金支出升序**；同額用 ID 穩定排序。
5. 車價、效率、來源只讀後端目錄；API 不接受前端價格、油電費或任意車款 ID。
6. 重用 `resolve`、`build_scenario`、`ownership_cost_summary`、`run_timeline`、`evaluate`、`constraints`。未修改既有財務公式。
7. 支出包含首次付款、期間車貸付款及養車預算；不另扣折舊、不加第二次車價，不代表總持有成本或財富損失。
8. 同一請求使用相同財務條件、基準月份、次月購車及 60 個月期間；預設調薪 0%、支出通膨 2%，沿用引擎年度調整。
9. 個人財務比較另跑 baseline/scenario；顯示每月結餘、五年末現金、最低現金、預備金、限制明細。
10. 五年後仍有貸款者另列期數及後續付款總額（含利息，**不是未償本金**）。不能把五年內低付款當作沒有後續義務。
11. 車型、動力偏好只是符合標記；舒適、安全、空間等沒有可靠比較標準則標「資料不足」，不打分。職業不參與排序。

## API 與資料結構

`POST /decisions/vehicle/recommendations`，request 沿用 P1 `schema_version=1.0`，新增嚴格 Pydantic 後端契約。
`CarNeedsRequest` 包含 background、constraints、usage、preferences、financial_profile、payment、free_text、extraction、field_sources、recommendation_handoff。
拒絕額外欄位、未知列舉、負金額、非有限值、矛盾座位／偏好、錯誤貸款條件、偽造價格與能源成本。財務 profile 重用 `DecisionProfile`。
Mock 候選及來源只作流程 metadata，不直接修改需求或排序。自由文字不執行程式、不呼叫 LLM。

回應主要結構：

```json
{
  "provider": "deterministic",
  "is_real_ai": false,
  "horizon_months": 60,
  "ranked": [{"rank": 1, "vehicle": {}, "five_year_cash_outflow": 0, "costs": {}, "affordability": null, "preferences": []}],
  "incomplete": [],
  "excluded": [],
  "missing_inputs": [],
  "assumptions": [],
  "limitations": []
}
```

上例為結構示意，0 不是任何車款實際估價。個人財務回應有 metrics、baseline、constraints、passed、five_year_cash_change。
不新增資料庫或外部 AI 需求。既有單車、雙車及目錄 API 保持原樣。

## 修改檔案

- 新增：`app/recommendation_schemas.py`、`app/recommendation_catalog.py`、`app/services/car_recommendations.py`。
- 新增：`static/car-recommendations.js`、`tests/test_car_recommendations.py`、`tests/test_car_recommendations.js`。
- 新增：`tests/browser/car_recommendations.pw.js`、`tests/browser/vehicle_regression.pw.js`、本報告。
- 修改：`main.py`、`static/car-needs.html`、`static/car-needs.js`、`static/car-needs.css`、`static/car-needs-state.js`。
- 修改：`tests/test_car_needs.js`、`tests/test_car_needs_integration.py`、`tests/browser/car_needs.pw.js`，反映新增資源及 P2 連線 metadata。

## 測試與瀏覽器驗收

自動化測試不需要 API key。覆蓋預算／座位／SUV、缺資料、里程導致排序改變、付款差異、長期貸款、不同財務能力、偽造輸入、P1 實際序列化、充電與偏好。
Node 覆蓋格式化、結果分類、請求契約、錯誤／AbortSignal、Mock 已知限制。
完整 Python：367 passed；完整 Node：116 passed。Python 2 個既有 JWT 短金鑰測試警告，非本次新增。
提交後另以不含 `.env` 與未追蹤文件的本機乾淨 clone 重跑；提交 hash 與乾淨 HEAD 結果由交付回報記錄。

實際瀏覽器：內建 CUA 失敗 `failed to write kernel assets: 系統找不到指定的路徑 (os error 3)`，改用已安裝 Playwright CLI + Chrome。
問卷入口→三步輸入→需求確認→真正推薦 API→結果，測試桌面 1440×1000 與手機 390×844。
驗證排除 SUV＋84 期貸款（3 款可排名）、高里程現金（6 款可排名＋1 款資料不足）、低預算、7 人座無結果、未填里程、修改／JSON 匯出／鍵盤／503 重試、15 秒逾時後重試與無橫向溢位。
另跑原 P1 完整桌機／手機流程及既有單車成本、雙車個人財務比較流程。
截圖保存在系統暫存資料夾，不加入 Git。預期失敗測試的 503 與既有 favicon 404 不是未處理 JS 例外。

## 已知限制與 Claude Review 重點

- 小目錄僅四車系七版本，未涵蓋市場；純電車完整成本排名尚未交付。
- 尚未取得各車型保養／保險報價，通用假設會影響排序；沒有宣稱已做市場校準。
- 未知年式保留 null，沒有以 2026 偽造車型年份；來源為手動快照，不自動更新。
- 預計持有 1／3 年仍統一比較五年，不模擬出售、折舊、殘值或稅制變動。
- 年度支出按月提列，沒有月內收支順序；既有生活費不自動扣交通抵減，避免自行假設。
- 財務限制預設為預備金 3 月、現金 0、月結餘 5,000，不等於個別使用者充分安全。
- 月度分位捨入可能使年費直接乘法與現金累加差幾分；結果沿用現有引擎，不另造公式。
- Mock「不喜歡休旅車但是常載長輩」仍可能漏長輩需求；「後座舒服不重要」仍可能誤判，已保留特徵測試。自由文字不直接決定推薦。
- 沒有正式 LLM、RAG、任意權重、完整推薦分數、即時報價、PDF 或新決策情境。
- 請 Claude 重點核對：硬條件與偏好分離、未知不變 0、五年與期後貸款口徑、預算與負擔區分、來源可信度及既有 API 相容性。

P2 完成後停止，不自動進入 P3；未 push。
