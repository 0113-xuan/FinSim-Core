# FinSim 2.0 P2 最終修正與 P3 介面交接 — Claude 獨立審查報告

審查日期：2026-10-27（Asia/Taipei）
審查對象：「P2 最終修正與 P3 介面交接」，commit `cd92f65f042ff3f1e9f1b4e0c490d1ec8ce06cb3`（父 commit `b26ce01`）
前次審查：`docs/CLAUDE_REVIEW_FINSIM2_P2_2026-10-26.md`（P2-1 ～ P2-3）
審查方式：唯讀。未修改、未提交、未 reset／checkout、未 push；HEAD 以 `git archive` 匯出到 repo 外暫存區測試（匯出內無 `.env`、無未追蹤文件）；`AI_ENABLED=false`，AI／Gemini／Supabase 變數皆清空；探測腳本放在 repo 外暫存目錄，以 FastAPI TestClient 與直接呼叫服務函式驗證，未呼叫任何外部服務、未連網。

## 1. 結論

**前次 3 項 P2 全數修正屬實，無 P0／P1，無新增 P2 阻擋項；P3 的 CONDITIONAL GO 判斷合理。** 資料面的「官方來源是否真實」仍未獨立核對（見第 5 節）。

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD 與範圍 | `cd92f65`，11 檔、+466／−20；`app/core`、`vehicle_decision.py`、`vehicle_cost_comparison.py`、`decision_assumptions.py` 皆**未修改** |
| 乾淨 HEAD 匯出：Python | `python -m pytest -q -p no:cacheprovider`：**414 passed**（無警告） |
| 乾淨 HEAD 匯出：Node | `node --test tests/*.js`：**119 passed**，0 failed，0 skipped |
| 已推送 | 本機 `origin/main` 追蹤 ref 與 HEAD 相同（`cd92f65`），`git status -sb` 顯示 `main...origin/main` 無領先或落後；我**未 fetch**，因此只確認本機追蹤狀態，未連線核對遠端本身 |
| 工作區 | 只剩 10 份未追蹤 `docs/*.md`（含 6 份 Claude 審查報告），無已追蹤檔案修改 |

## 3. 前次發現的修正，逐項實測

### P2-1 全站 `NaN`／`Infinity` 處理 — 已修正

`app.router.route_class = FiniteJSONRoute` 設在 `main.py:98`（`FastAPI(...)` 建立之後、路由宣告之前），並加入 `RequestValidationError` handler。

- **覆蓋範圍**：35 條路由中，除 FastAPI 內建的 `/openapi.json`、`/docs`、`/docs/oauth2-redirect`、`/redoc` 外全部使用 `FiniteJSONRoute`。
- **逐路由實測**：對全部 23 條 POST 路徑（`/simulate`、`/compare`、`/monte-carlo`、`/optimize`、`/auth/*`、`/ai/*`、`/scenarios/*`、`/decisions/vehicle/*`、`/financial-profile`…）各送 `{"a": NaN}`、`{"a": Infinity}`、`{"a": [-Infinity]}`、`{"a": {"b": 1e9999}}`、截斷 JSON，**全部回 422**，無一回 500 或拋出例外。
- **字串不誤殺**：`{"a": "NaN"}`（合法字串）不被守衛攔截，由各路由自己的 schema 回 422；`/financial-profile` 回 401（守衛在認證依賴之前，但合法 JSON 不被它擋）。
- **邊界**：空 body 無 Content-Type → 422（欄位缺漏）；表單送 JSON 路由 → 422；10 萬層深度巢狀陣列 → 422（`RecursionError` 被攔截）。
- **回應格式**：`{"detail":[{"type":"json_invalid","loc":["body"],"msg":"..."}]}`，不含原始輸入。
- **不回顯輸入**：對 `/auth/register` 送密碼型別錯誤與多餘欄位 `TOPSECRET`，回應只含 `type／loc／msg`，不含 `TOPSECRET` 或密碼值；對 `/decisions/vehicle` 送不存在的 `scenario_type`，回應訊息為固定文字（`Input should be 'vehicle_purchase' or 'housing_change'`），沒有回顯使用者字串。
- **業務 ValueError 不被吞**：`try` 只包住 `request.body()`／`request.json()`；`await handler(request)` 在 `try` 之外，後端程式的 `ValueError` 不會被偽裝成輸入問題。
- **前端相容**：各前端對 `detail` 一律先判斷是否為字串，否則顯示通用訊息；422 驗證錯誤原本就是陣列格式，因此移除 `input／ctx` 不影響現有前端。

### P2-2 座位數不再預設 5 — 已修正

直接呼叫 `recommendation_catalog.record()` 實測：

- 省略 `seats` → `TypeError`（必填 keyword）。
- `seats=0`、`10`、`5.0`、`True` → 皆 `ValueError`；`seats=5` 但沒有來源 → `ValueError`。
- 以合成車款驗證 7 人座需求：5 人座 → `excluded`（座位數不足）、7 人座 → `ranked`、座位未知（`None`）→ `incomplete`，未知**不**被當成 5。
- 目錄逐欄記錄 `sources.seats`、`source_types`（official／government／third_party）、`verification`（verified／indexed_only／unverified）與 `verification_notes`：FIT 兩款為官方 `verified`，Corolla Cross 三款為第三方 `indexed_only`，Altis 為政府索引 `indexed_only`，Model 3 為官方 `indexed_only`；`model_year` 一律 `unverified`，年式維持 `null`。

### P2-3 起算日期採台北時間 — 已修正

- `recommend_cars(needs, *, reference_date=None)` 預設走 `resolve_reference_date(..., 'Asia/Taipei')`；回應新增 `reference_date`、`timezone`。
- 注入固定日期：`2026-12-31` → 起算 `2026-12`、購車 `2027-01`；`2028-02-29`（閏日）→ `2028-02`／`2028-03`；`2027-01-01` → `2027-01`／`2027-02`。三者的 6 款排名與五年現金支出與基準日 `2026-10-27` **完全相同**（成本口徑未因基準月份改變）。
- 偽造時鐘（UTC `2026-10-31 15:59:59` 與 `16:00:00`）：前者得到台北 `2026-10-31` → 購車 `2026-11`；後者得到台北 `2026-11-01` → 購車 `2026-12`，正確跨月。

## 4. 發現

### 無 P0／P1／新增 P2 阻擋項

以下為低風險備註：

- **JSON 解析兩次**：守衛先 `await request.json()` 解析並檢查，FastAPI 之後再用自己的方式解析同一份 body；實務上只是微小的重複運算，目前請求體都很小，可忽略。若日後有大型請求體再考慮合併。
- **Model 3 價格用於硬條件**：Model 3 的 1,749,900 在報告中標為「保留快照，現行未確認」（`price: indexed_only`），但仍用於「超過車價預算」排除判斷。目前 Model 3 不論是否排除都不會進入排名（缺電耗，永遠 `incomplete` 或 `excluded`），所以不影響排名，只是排除理由可能引用過期價格。UI 已逐欄標示核對狀態，建議 P3 前補上確認或在排除理由中提示。
- **`static/app.js:60`**：舊頁面的 API 錯誤處理 `throw new Error(data.detail || ...)` 在 `detail` 為陣列時會顯示 `[object Object]`。這是既有行為（422 本來就是陣列），並非本次引入，只是順便標記。

## 5. 未驗證項目

- **官方價格、油耗、座位數與來源網址的真實性**：我沒有逐一開啟 Toyota、Honda、Tesla、U-CAR、環境部頁面核對。報告本身也誠實揭露第三方／索引／未確認狀態，且資料已逐欄標示 `verified／indexed_only／unverified`；但「`verified`」是否真的已讀取官網，我無法獨立證實。
- **桌面與手機瀏覽器流程**：報告自述以 CUA 控制 Chrome 完成桌面流程、內建瀏覽器曾出現 `Failed to fetch`，且 `tests/browser/p2_final_desktop.pw.js` **並未實際執行**；我也沒有重跑 Playwright 或 Chrome。截圖、桌面寬度與 console 結果我無法驗證。
- **遠端 push 實際內容**：僅確認本機追蹤 ref，未連線核對遠端。
- **P3 介面盤點的正確性**：我只對照了報告列出的函式名稱（`createExtractionClient`、`applyCandidate`、`ExtractionMetadata.provider` 僅允許 `mock`），這些與我先前讀到的程式碼一致（`applyCandidate` 會用 mock 規則重新驗證候選；`ExtractionMetadata.provider: Literal['mock']`、`is_real_ai: Literal[False]`）；`app/services/ai_provider.py` 與 `prompt_loader` 我沒有逐行檢視。

## 6. 對 P3 條件式開工的意見

同意報告的 CONDITIONAL GO：

1. 後端目前**會拒絕**真實 AI 的 metadata（`provider` 只能是 `mock`，`is_real_ai` 只能是 `False`），P3 必須先做向後相容的契約版本化，不能只替換 transport。
2. `applyCandidate` 目前以 mock 規則重新驗證候選，因此 LLM 候選需要獨立的受限驗證流程（欄位白名單、原文證據、revision 比對），並保留使用者逐項確認。
3. 本次 `FiniteJSONRoute` 與「驗證錯誤不回顯輸入」對 P3 有直接幫助：LLM 輸出與自由文字不會經由 422 回應被反射出去。
4. 兩個已知 Mock 限制（「不喜歡休旅車但是常載長輩」漏判、「後座舒服不重要」誤判）請延續保留為 P3 的回歸測試案例。

## 7. 建議下一步

1. 人工或另一個有網路驗證的流程核對 7 筆車款資料與來源連結後，再對外宣稱數據來源狀態。
2. P3 先處理契約版本化與受限候選驗證，再接 LLM。
3. 把 Model 3 價格的核對與其他 `indexed_only` 欄位列為資料維護待辦。
