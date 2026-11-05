# FinSim 2.0 P2 個人化車款推薦 — Claude 獨立審查報告

審查日期：2026-10-26（Asia/Taipei）
審查對象：「P2 個人化車款推薦工作報告」，commit `b26ce0147f5e8aa7509e893a4f97314330359b9a`（父 commit `30fa3c9`）
審查方式：唯讀。未修改、未提交、未 reset／checkout；HEAD 以 `git archive` 匯出到 repo 外暫存區測試（匯出內無 `.env`、無未追蹤文件）；`AI_ENABLED=false`，AI／Gemini／Supabase 變數皆清空；探測用腳本放在 repo 外暫存目錄，以 FastAPI TestClient 呼叫，未啟動對外伺服器、未呼叫任何外部服務。

## 1. 結論

**有條件通過：無 P0／P1。計算口徑、硬條件與未知處理經實測與手算皆符合報告；有 3 項 P2（含 1 項既有全站問題）與「官方來源未逐一核對」這項未驗證事項。**

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD 與提交範圍 | `b26ce01`，17 檔、+807／−24；`app/` 下僅新增 3 個檔案（`recommendation_catalog.py`、`recommendation_schemas.py`、`services/car_recommendations.py`），既有財務服務檔案**未修改** |
| 乾淨 HEAD 匯出：Python | `python -m pytest -q -p no:cacheprovider`：**367 passed**（無警告） |
| 乾淨 HEAD 匯出：Node | `node --test tests/*.js`：**116 passed**，0 failed，0 skipped |
| 前端無危險 API | `car-recommendations.js`、`car-needs.js`、`car-needs.html` 無 `innerHTML`／`eval`／`localStorage`／`/ai/`；外部連結皆 `target=_blank` 且 `rel="noopener noreferrer"`；請求透過可注入的 `transport` |
| 後端契約嚴格 | 實測 422：額外欄位（`constraints.price`）、字串數字（`"1000000"`）、布林當數值、座位與乘車人數不一致、`status='draft'`、現金夾帶貸款條件；FastAPI 層另拒絕 `NaN`（見 P2-1） |
| 硬條件 | 預算 1,000,000 時 Model 3（1,749,900）列為「超過車價預算」；排除 SUV 時 3 款 Corolla Cross 被排除、3 款可排名；7 人座需求時 6 款皆「座位數不足」；住家與公共充電皆 `no` 且預算足夠時 Model 3 列為排除（充電條件） |
| 未知不等於 0 | 里程與停車預算皆 `null` 時，6 款全列為 `incomplete`，理由為「請補充每月行駛里程（可明確填 0）」「請填寫每月停車預算（免費停車請明確填 0）」，沒有排名；預算 200 萬＋住家可充電時 Model 3 列 `incomplete`（缺官方電耗、尚未校準純電成本），不排名 |
| 排序依五年現金支出 | 現金、1,000 km／月：Altis 1,301,875.92 ＜ FIT 1,311,210.00 ＜ FIT e:HEV 1,346,192.56 ＜ CC HEV 豪華 1,376,269.08 ＜ CC 汽油 1,387,558.16 ＜ CC HEV 旗艦 1,516,269.08 |
| 里程改變排序 | 3,000 km／月時，FIT e:HEV（1,485,482.68）反超 FIT 汽油與 Altis，成為第 1 名，符合「油耗差距隨里程放大」的預期 |
| 手算核對 Altis | 一次付清 735,000 ＋ 12 個月 ×（停車 3,000 ＋ 能源 1,000÷15.7×30＝1,910.83 ＋ 保險稅費維護 50,000÷12＝4,166.67）× 通膨年度係數和 5.20404016（1.00／1.02／1.0404／1.061208／1.08243216 各 12 個月）＝ 735,000 ＋ 566,875.9 ≈ **1,301,875.9**，與 API 輸出 1,301,875.92 一致 |
| 貸款口徑 | 60 期：每款 `remaining_loan_months=0`、`remaining_loan_payments=0`；84 期：`remaining_loan_months=24`，Altis 剩餘付款 169,658.88＝7,069.12×24，五年內現金支出降為 1,191,023.12（比 60 期低），但另列後續付款，與報告「五年低付款不等於無後續義務」一致；剩餘付款為付款總額（含利息），非未償本金 |
| 個人財務比較 | 帶 `financial_profile`（薪資 6 萬、存款 50 萬）時回傳 `affordability`：預備金月數與最低現金未通過、月結餘通過，`five_year_cash_change` ＝ −1,301,875.92，且排名與無財務資料時完全相同（財務結果不參與排序） |
| 效能 | 單次請求 0.00～0.02 秒（帶財務資料 0.12 秒） |

## 3. 發現

### P2-1 — 請求含裸 `NaN` 時回傳未處理例外（既有全站問題，非 P2 引入）

實測：對 `/decisions/vehicle/recommendations` 送 `"budget_max": NaN`，Pydantic 正確判定 `finite_number` 錯誤，但 FastAPI 在序列化 422 回應時因為要回傳原輸入 `nan` 而拋出 `ValueError: Out of range float values are not JSON compliant: nan`，變成 500（TestClient 中為未處理例外）。

對既有端點 `/decisions/vehicle/costs` 送含 `NaN` 的請求也出現完全相同的例外，因此這是專案既有行為，並非本次新增。報告說「拒絕非有限值」在驗證層屬實，但實際回應不是乾淨的 422。建議在全站加一個 `RequestValidationError` handler，或在 JSON 解析層拒絕 `NaN`／`Infinity`，同時處理新舊端點。

### P2-2 — 座位數 5 是目錄中的寫死預設值，未列入來源

`recommendation_catalog.record()` 對所有版本固定 `seats=5`，而 `sources` 只記錄價格、規格、效率三項連結，沒有座位的出處。目前 4 個車系的實際座位也是 5，結果正確；但「座位不足」是硬條件，之後新增 7 人座車款時，若漏改預設值會被靜默地當成 5 人座。建議把座位改成必填參數並一併列入 `sources`。

### P2-3 — 推薦起算月使用伺服器本機日期

`recommend_cars` 以 `date.today()` 取起算月，購車月為次月。此日期是伺服器時區而非 Asia/Taipei；跨月交界或部署在 UTC 的環境，會與使用者預期差一個月，也讓依賴「今天」的測試在月初月底有不穩定風險。報告已說明起算與購車月的設計，但未提到時區。建議明確使用 Asia/Taipei，或允許請求帶入參考月份（與既有 `reference_date` 做法一致）。

### 附註（非缺陷，報告已揭露或屬設計取捨）

- 保險／稅費／保養對所有車款相同（20,000／12,000／18,000 TWD／年），排名差異僅來自車價、能源與貸款；報告已明講不是個別車款報價。
- 油價 30 TWD/L 為比較假設，已列在 `assumptions`。
- 預計持有 1／3 年仍統一比較 60 個月，已列在 `limitations`。
- 「能源成本偏好」「保養費偏好」等偏好統一標「資料不足」，即使系統已計算能源成本；這是刻意不給分的保守設計，但使用者可能覺得不一致，可在 UI 說明。
- 該端點未做速率限制（AI 端點有 `rate_limit_ai`）；因為運算量小（毫秒級）且不呼叫外部服務，風險低。

## 4. 未驗證項目

- **官方價格、油耗與來源網址的真實性**：我沒有逐一開啟 Toyota／Honda／Tesla 官網核對 7 筆版本的售價、年式與效率數字，也未驗證來源連結目前是否仍有效。報告列為 Claude Review 重點的「來源可信度」，請以人工或另一個有網路驗證的流程確認；目前只確認這些值是靜態寫在 `recommendation_catalog.py`，前端與請求不能覆寫，且資料有 `checked_on`、`source_url`、`model_year=null` 與限制說明。
- **Playwright 桌面（1440×1000）／手機（390×844）流程**：含三步驟問卷到推薦結果、15 秒逾時重試、503 重試、鍵盤操作、無橫向溢位與截圖，我沒有重跑；僅確認 `tests/browser/car_recommendations.pw.js` 與 `vehicle_regression.pw.js` 已隨 commit 提交。
- **頁面實際外觀與無障礙行為**：只檢視前端程式碼與 Node 測試。
- **單車與雙車既有流程**：以乾淨 HEAD 全測試通過及既有端點的測試作為間接證據，未在瀏覽器重跑。
- **月度分位捨入差數**：報告提到的「年費直接乘法與現金累加差幾分」，我的手算與 API 在 0.0x 元內一致，未做更大範圍掃描。

## 5. 建議下一步

1. 處理 P2-1（全站 `NaN` 處理）與 P2-3（Asia/Taipei 起算月），P2-2 在新增車款前補上。
2. 以人工或獨立網路驗證核對 7 筆官方資料後，再對外宣稱「官方參考售價」。
3. 在進入 P3（真實 LLM）前維持「後端重新驗證需求，前端 `confirmed` 與 Mock 候選不是授權」的原則。
