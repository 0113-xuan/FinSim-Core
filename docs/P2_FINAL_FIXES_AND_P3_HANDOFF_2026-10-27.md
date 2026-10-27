# P2 最終修正與 P3 介面交接

整理日期：2026-10-27（Asia/Taipei）。基準提交：`b26ce0147f5e8aa7509e893a4f97314330359b9a`。
本輪僅修正 P2 審查問題，沒有接入正式 LLM、修改財務公式、重寫問卷或推薦演算法。

## 修正內容

### 全站 JSON 與驗證錯誤

- `app/request_validation.py` 新增 `FiniteJSONRoute`，目前全部 FastAPI API route 共用。
- 解析同一個 Request 的 JSON 並快取；在驗證、認證依賴與業務邏輯前拒絕裸 `NaN`、`Infinity`、`-Infinity`，以及 `1e9999` 等溢出成無限大的 JSON 數值。
- 巢狀物件／陣列一樣檢查；合法字串中的「NaN」不會被誤當成非法 JSON 數字。
- 非法 JSON、錯誤編碼與非有限值固定回傳 422，`detail` 為含 `type / loc / msg` 的陣列，不回傳原始輸入。
- 全域 `RequestValidationError` handler 同樣保留欄位位置、錯誤類型及訊息，移除 `input / ctx`，避免非有限數字、例外物件及財務原文造成序列化錯誤或回顯。
- 這是驗證錯誤回應的刻意收斂；不再提供原始 `input / ctx`。合法請求與成功回應不變；Pydantic 數值／列舉／額外欄位限制未放寬。
- 不攔截業務程式本身的任意 ValueError，也不把後端程式錯誤偽裝成輸入問題。

### 座位數

- `record()` 的 `seats` 為必填 keyword，沒有 5 的預設值。
- 明確的 `None` 表示未知；已知值須為 1–9 整數並附來源，否則建立目錄時就報錯。
- 每筆新增 `sources.seats`、`source_types`、`verification`、`verification_notes`，來源與核對狀態逐欄列示。
- 5 人、7 人、未知座位測試採明確的合成 fixture，沒有新增虛構生產車款。7 人需求下：5 人排除、7 人通過、未知列 incomplete。
- 有來源索引的 5 人資料仍沿用，但明確揭露未完成官網逐版確認；不是把未知值預設成 5。

### 起算日期

- `recommend_cars(needs, *, reference_date=None)` 重用既有 `resolve_reference_date(..., 'Asia/Taipei')`。
- 預設採台北當地日期，不再使用伺服器本機 `date.today()`；測試可直接注入固定日期。
- 購車月份仍為參考月份的次月，仍計算 60 個月；沒有更動通膨、貸款或現金流公式。
- 回應額外提供 `reference_date` 與 `timezone`，便於重現。P1 請求 JSON 不新增必填欄位，也不讓前端自行指定時區。
- 測試涵蓋月底、月初、閏日、跨年，以及 UTC 15:59:59／16:00:00 對應台北跨月的邊界。

## 車款資料核對表

來源擷取／查詢日：2026-10-26；本文件整理日：2026-10-27。`checked_on` 表示查詢／嘗試核對日期，**不表示所有欄位均已驗證**。
下表價格為新台幣；油耗單位 km/L；目前所有 `model_year=null`，沒有把生產適用月份或查詢年份當成年式。

| ID／版本 | 參考售價 | 效率 | 座位資料 | 核對狀態與來源 |
|---|---:|---:|---|---|
| cc-gas-luxury／Corolla Cross 豪華 | 809,000 | 14.3 | 5；第三方索引 | 價格／油耗已讀取 [Toyota CC 完整規配][cc]；座位僅 [U-CAR 對應規格索引][cc-seats] 佐證，直連 403，官方逐版待核對 |
| cc-hev-luxury／Corolla Cross HYBRID 豪華 | 849,000 | 23.5 | 5；第三方索引 | 價格／油耗已讀取 [Toyota CC 完整規配][cc]；座位狀態同上 |
| cc-hev-flagship／Corolla Cross HYBRID 旗艦 | 989,000 | 23.5 | 5；第三方索引 | 價格／油耗已讀取 [Toyota CC 完整規配][cc]；座位狀態同上 |
| fit-home／FIT HOME 汽油版 | 759,000 | 17.9 | 5；官方已核對 | [Honda FIT][fit] 規配表、能源效率及全車五席安全帶項目，兩版本各欄配備已核對 |
| fit-hev／FIT e:HEV 油電版 | 829,000 | 26.9 | 5；官方已核對 | 同上；採規配表建議售價，非促銷或舊換新補助後價 |
| altis-classic／Corolla Altis 經典 | 735,000 | 15.7 | 5；政府產品索引 | 價格／油耗已讀取 [Toyota Altis 完整規配][altis]；[環境部同車系登錄][altis-seats] 索引列 1798c.c. CVT 4D／5 人，頁面需 JavaScript，指定年式版本待核對 |
| model3-lr-rwd／Model 3 Long Range 後輪驅動 | 1,749,900（保留快照，現行未確認） | 未知，null | 5；官方索引 | [Tesla 訂購頁][tesla-price] 未回傳可讀價格；官方搜尋索引仍有此價；[台灣規格頁][tesla-seats] 索引有 LR 後驅 5 個座椅，但直連改版未回傳完整表格。電耗與完整成本模型仍 incomplete，不強行排名 |

[cc]: https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx
[cc-seats]: https://newcar.u-car.com.tw/Toyota/Corolla%20Cross/7183/spec
[fit]: https://www.honda-taiwan.com.tw/Auto/Cars/FIT
[altis]: https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx
[altis-seats]: https://greenlifestyle.moenv.gov.tw/categories/greenProductdetailPage?product=23905&type=1
[tesla-price]: https://www.tesla.com/zh_tw/model3/design?redirect=no
[tesla-seats]: https://www.tesla.com/zh_tw/model3-performance

### 未驗證或非官方內容

- 七筆年式均未確認，維持 null。
- CC 三版座位有第三方資料佐證，但沒有完成官網逐版核對；Altis 座位是政府同車系產品索引，非指定年式版本完整認證。
- Model 3 現行價格、座位現行頁面與可匹配電耗仍待確認。不得把搜尋索引當成即時官方確認。
- 年保險 20,000、年稅費 12,000、年維護 18,000 是既有共同比較假設，**不是各款實際保費、法定稅額或原廠報價**；本輪沒有改為假造車型專屬費用。
- 油價 30 TWD/L 是比較假設，官方實驗室油耗也不是實際道路保證。
- UI 新增逐欄來源及核對狀態，避免一律標示「官方已確認」。

## P3 介面盤點（尚未實作）

| 層 | 現有介面 | P3 接法／注意事項 |
|---|---|---|
| P1 問卷輸出 | `static/car-needs-state.js::serialize()`，schema_version 1.0 | 保留 background、constraints、usage、preferences、financial_profile、payment、free_text、revision 等欄位；未知保留 null |
| 擷取 adapter | `createExtractionClient(transport)`，目前 UI 未注入 transport，呼叫本機 mock | P3 可注入 API transport；不能把問卷正常運作綁到 AI 可用性 |
| 目前擷取輸入 | `{text, related_answers:{body_types, ownership_years}, revision}` | 只傳最小必要上下文，不送整筆財務資料或資料庫紀錄。補充欄位前先定義白名單及隱私界線 |
| 目前候選輸出 | `{provider:'mock',is_real_ai:false,status,candidates:[{id,field,value,label,evidence,source:'mock_literal_fixture'}]}` | 候選而非覆寫指令；AI 失敗、未知、衝突要分開處理 |
| 套用與確認 | `applyCandidate()`→逐項套用→問卷確認頁→`confirm()` | 現在 applyCandidate 會重新執行 mock 規則核對，**不能只替換 transport 就接受 LLM 候選**；P3 需新增受限候選驗證流程，保留使用者逐項確認及最終確認 |
| P2 後端 | `CarNeedsRequest`→`POST /decisions/vehicle/recommendations` | 後端再次驗證實際條件；不以 confirmed／ready_for_p2 當授權或合法性保證；不接受前端車價、油電成本或任意 ID |
| 現有 AI 基礎設施 | `app/services/ai_provider.py::AIProvider.generate_structured()`、`prompt_loader.load_prompt()` | 可評估重用，不能把財務 extraction schema 當成選車需求 schema。新增提示詞與 schema 前須獨立 review |

### P3 必須補的契約缺口

1. 後端目前 `ExtractionMetadata.provider` 僅允許 mock，`is_real_ai=False`，`MockCandidate.source` 只允許 mock_literal_fixture；**真 AI metadata 目前會被拒絕**，不能假稱已接通。
2. 應以向後相容的 union／版本化白名單支援真實 provider metadata，保留舊 P1 mock 請求。這個契約更動本輪只列計畫，未放寬現行 schema。
3. 真實 AI 輸出僅能是允許欄位的候選值與原文證據；價格、油耗、成本、排名、財務判斷不在 AI 可修改範圍。
4. 接收候選時比對 revision，使用者修改問卷後丟棄舊回應；衝突不得自動覆寫。
5. 使用者逐項確認、套用至問卷狀態並通過最終確認後，才把正規化條件送 P2。AI 候選 metadata 本身不參與推薦篩選與排名。
6. 後端 schema 驗證、prompt injection／超長輸入／逾時與預算控制、最小上下文、不記錄完整對話、Mock 回歸須納入 P3 驗收。

### 保留的語意測試

- 「不喜歡休旅車但是常載長輩」：目前 mock 可能漏掉長輩需求；未來 AI 應同時擷取 SUV 排除與長輩用途，並附原文證據供確認。
- 「後座舒服不重要」：目前 mock 可能誤判為重視舒適；未來 AI 不應建立正向舒適度偏好，不確定時要求釐清。
- 現有 Node 特徵測試仍保留，未重寫解析器。

## 相容性與驗收

- 未修改 `app/core/`、既有車貸、單車、雙車、敏感度及壓力測試公式。
- P1 問卷欄位與請求 schema 未改；成功 API response 只新增日期／來源 metadata，既有欄位與金額保留。
- 刻意改變：非法 JSON 固定 422；驗證錯誤不再回顯 input／ctx；目錄工廠必須明確提供座位；車型顯示名稱對齊官網「豪華／經典」，ID 不變。
- 固定日期測試確認跨基準月份仍有相同 60 個月成本與排名；不同貸款期數及後續付款由既有回歸覆蓋。
- 完整測試命令：`python -B -m pytest -p no:cacheprovider -q`；`node --test tests/*.js`。
- 本輪工作樹測試：Python 414 passed，Node 119 passed。Python 工作樹有 2 個既有 JWT 短金鑰警告，不屬本次修改。
- 桌面實測透過 CUA 控制 Chrome：三步問卷→確認→真實本機推薦 API→六款排名及一款 incomplete→檢查三種座位來源與 84 期貸款。未操作手機或新增手機 UI。
- Chrome 寬度 1745，文件寬度 1732，沒有橫向溢位；console 警告來自既有 MetaMask 擴充套件，未發現網站執行錯誤。
- 內建瀏覽器初次連線遇伺服器啟動時序，後續 POST 顯示 Failed to fetch 且未到伺服器；Chrome 同步版本可完成。本輪不把內建瀏覽器端限制說成網站已修復或完全通過。
- `tests/browser/p2_final_desktop.pw.js` 提供獨立 Playwright 重跑腳本；本輪實際驗收使用 CUA Chrome，不宣稱已執行該 CLI 腳本。
- 提交後另以不含 `.env` 與原工作樹未追蹤文件的乾淨 clone 執行完整測試；實際結果及 hash 列最終交付回報。

## 修改檔案

- 新增 `app/request_validation.py`、`tests/test_request_validation.py`、`tests/browser/p2_final_desktop.pw.js`、本文件。
- 修改 `main.py`、`app/recommendation_catalog.py`、`app/services/car_recommendations.py`、`static/car-recommendations.js`。
- 修改 `tests/test_car_recommendations.py`、`tests/test_car_recommendations.js`、`tests/test_standalone_vehicle_costs.py`。

## 結論

P2 程式問題已修正，可交 Claude 獨立 Review。P3 為 **CONDITIONAL GO**：可在覆審通過後開始契約／候選確認流程；不應直接把正式 LLM 接到目前 mock 契約。
資料面仍須保留未驗證標示；這些限制不應被 AI 解釋成官方確定事實。純電成本排名不在本輪補做。
依使用者 2026-10-27 最新授權：完成後推送 FinSim repository，沿用現有 Git 認證、不強制推送；完成後停止，不自動進入 P3。不新增或驗收手機專屬功能。
