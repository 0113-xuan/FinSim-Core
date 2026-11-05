# FinSim 2.0 AI 個人化選車升級：Audit 與實作規劃

- 日期：2026-10-20（Asia/Taipei）
- 狀態：待 Claude Review；本輪只新增本規劃文件，沒有實作新功能。
- 檢查位置：`D:\project\FinSim-Core`。
- 基準 commit：`d3483f48e100ff94fcc71ee919472ba486bc0f23`，另包含目前工作目錄的未提交逾時修正。
- 時程：11/01 核心功能截止、11/02–11/08 使用者測試、11/09–11/18 展示準備、11/19 口試。
- 證據標記：**確認**＝本輪讀到程式或執行測試；**推論**＝架構判斷；**待驗證**＝尚未實作、量測或核對。
- 「完成」只代表下表限定範圍的程式與整合存在，不代表已完成市場校準、真實雲端驗收或研究效度驗證。

## 1. Executive Summary

**結論：CONDITIONAL GO。** 沿用 FastAPI、原生 JavaScript、既有 Gemini 抽象與財務引擎，新增一條「需求確認 → 規則推薦 → 既有購車評估」流程。現有購車工作區繼續可獨立使用。

口試版應做到：

1. 四步短問卷，職業與品牌偏好可跳過，必填只限目前計算或篩選真正需要的資料。
2. 自由文字解析成候選需求，衝突由使用者決定；一次只追問一件事。
3. 6–8 個可靠規格版本，至少包含汽油、HEV、BEV，且含不同車身型式；不要把同車系多個配備版本宣稱為多樣化資料庫。
4. 可重現的硬性篩選與偏好排序，明示缺資料、權重、估算與未符合的財務限制。
5. 最多三款推薦，選一至兩款重用既有單車／雙車分析。
6. 能源計算、可追溯保養資料、可選的殘值情境；沒有充分資料時不產生完整 TCO 排名。
7. AI 失效仍可填問卷、推薦與計算；解釋以後端事實及固定模板兜底。

不應把跨品牌完整保養價格庫、真實二手殘值預測、全自由對話、多代理、帳號雲端同步與新版機率模型都塞進本次口試版。

## 2. Repository Audit Report

### 2.1 架構與整合盤點

以下路徑相對於 repository root，函式名稱是主要定位證據。

| 功能 | 分類 | 程式證據與限定範圍 |
|---|---|---|
| FastAPI、首頁導向購車工作區 | 已完整實作並整合 | `main.py:527` `workspace_entrypoint()`；`StaticFiles`；`static/vehicle.html` 載入四個 vehicle 腳本 |
| 車款選擇、套用、自訂 | 已完整實作並整合 | `app/vehicle_catalog.py:17` `catalog_list()`、`:32` `vehicle_preset()`；`main.py:391`/`:396`；`static/vehicle-catalog.js` |
| 車款資料內容 | 部分實作 | `app/vehicle_catalog.py:8` `CATALOG`：5 個版本，Corolla Cross/HR-V；只有車價、km/L、粗粒度來源日期。無明確 powertrain、座位數、車身分類、電耗與保養計畫 |
| 無個人資料單車成本 | 已完整實作並整合 | `app/services/vehicle_costs.py:20` `estimate_vehicle_costs()`；`main.py:412`；`static/vehicle.js:36`/`:168`。支援 1/3/5 年，強制零通膨、無交通抵減 |
| 個人購車 60 月模擬 | 已完整實作並整合 | `app/services/vehicle_decision.py` `simulate_vehicle_decision()`、`run_timeline()`；`main.py:425`；`static/vehicle.js` `buildRequest()`、`render()` |
| 雙車養車與個人財務比較 | 已完整實作並整合 | `app/services/vehicle_cost_comparison.py` `compare_running_costs()`；`static/vehicle-costs.js:145` 呼叫 `/decisions/vehicle/cost-comparison`，渲染 `financial`。不是只有 API |
| 通用 A/B 車輛 API | 後端已有，但目前前端未使用此入口 | `app/services/vehicle_analysis.py` `compare_vehicles()`；`/decisions/vehicle/compare`。現有 UI 使用上一列直接雙車 API，勿再開發另一套 |
| 四種壓力測試、可負擔上限 | 已完整實作並整合 | `vehicle_decision.py` `find_limit()`、`simulate_vehicle_decision()`；`vehicle.js` 的 `stresses`/`boundaryChecks`。屬條件式情境，不是發生機率 |
| 七因素敏感度 | 已完整實作並整合 | `vehicle_analysis.py` `FACTORS`、`sensitivity_analysis()`；`vehicle-analysis.js` `renderSensitivity()`；Chart.js 與文字解釋 |
| What-if | 部分實作 | `VehicleWhatIfRequest` 只接受 `salary/monthly_parking/purchase_price`；UI 已串接，尚不接受「油價上升 20%」自然語言 |
| 調薪、通膨、既有債務到期 | 已完整實作並整合 | `app/core/simulation.py:95` 起；`DecisionProfile`；vehicle 頁有假設與債務明細。調薪、通膨為每滿 12 月階梯調整 |
| 電車能源模型 | 尚未實作 | 現有能源金額欄可人工填入，但 `vehicle_preset()` 固定使用 km/L 與油價；沒有 kWh、充電損耗或充電比例 |
| 車型專屬保養、殘值與折舊 | 尚未實作 | `_vehicle()` 使用年度維護預算按月提列；兩個成本 API 明確 excludes depreciation/resale；不能當成完整 TCO |
| Gemini/OpenAI provider 抽象 | 已實作基礎，可重用 | `app/services/ai_provider.py` `AIProvider.generate_structured()`、`get_ai_provider()`；`gemini_provider.py`、`mock_ai_provider.py` |
| Prompt loader、財務抽取與確認 | 部分實作，屬舊財務建檔流程 | `prompt_loader.py`；`financial_answer_extraction.py:460`；`profile_onboarding.py`；`main.py:162`；`static/profile-onboarding.js` 在舊工作區。購車新頁未載入此流程 |
| AI 選車需求抽取、推薦、問卷 | 尚未實作 | 現有 schema 是財務欄位／債務／未來計畫；沒有 occupation、usage、充電條件、需求推薦服務或對應 route |
| AI 財務解釋 | 尚未實作新流程 | `/ai/generate-report` 呼叫 `report_generator.generate_report()`，實際是舊格式固定文字，讀取舊 summary/FSI/Monte Carlo；不是選車解釋 LLM |
| 60 月現金曲線資料 | 後端已有，前端刻意不顯示 | `vehicle_decision.py` 回傳 timeline；vehicle 頁已依先前需求移除現金圖與月明細。不要自動恢復大量圖表 |
| 假設來源與計算定義 | 後端已有；前端僅部分顯示 | `decision_assumptions.py`、`effective_assumptions()`、response definitions/provenance；UI 保留成本與車款來源，整區假設表已移除 |
| 保存／Supabase | 部分實作 | `main.py:105` 的 `PROFILES/PROFILE_DRAFTS/CONFIRMED_DEMO_PROFILES` 是 process 記憶體；`config.py` 有設定、requirements 有套件；未找到實際 client/CRUD |
| SQL | 參考設計，非部署證據 | `docs/supabase_schema.sql` 有 7 表與 enable RLS；ownership policy 只是註解範例。未查詢遠端資料庫，不能宣稱已遷移或授權完整 |
| 自動化測試 | 已有基礎 | `tests/test_vehicle_*`、`test_standalone_vehicle_costs.py`、`test_gemini_provider.py`、`test_financial_answer_extraction.py` 等；見第 10 節本輪執行結果 |

### 2.2 現有資料流

`vehicle.html → vehicle-catalog.js → /catalog、/preset → vehicle.js 或 vehicle-costs.js → Pydantic → resolve() → build_scenario() → simulate_finance() → evaluate()/constraints()/ownership_cost_summary() → UI`

單車純成本路徑只重用 builder 與 cost summary，不計算個人限制。雙車成本部分使用固定價格與 1/3/5 年；其 `financial_context` 分支另跑固定 60 月個人模擬。兩個時間範圍和成本口徑不能混用。

### 2.3 應先處理或隔離的風險

- **確認：推薦效能。** `simulate_vehicle_decision()` 每次包含 baseline、scenario、4 種壓力與多輪上限搜尋；`compare_running_costs()` 在有個人資料時呼叫兩次完整服務，卻只取部分輸出。推薦十款不可照搬十次完整服務。規劃中的候選評估只用 `run_timeline/evaluate/constraints`，完整搜尋留到使用者選定車款。
- **確認：來源粒度不足。** `catalog_list()` 所有車款使用固定 `checked_on='2026-10-11'`；這不是每個欄位都有重新核驗。未來必須欄位層級來源，不可複製這個日期作為新資料驗證證明。
- **確認：保養價格不是車型專屬。** `annual_maintenance_budget` 仍從共同假設取得，不能支撐「電車保養比油電車便宜多少」的實證結論。
- **確認：不同口徑。** standalone 強制 inflation=0；個人模擬使用 profile 通膨；比較 response 根層 `excludes` 是成本分支的定義，不能誤解成 financial 分支也沒有車貸。
- **確認：月結餘限制。** `evaluate()` 取購車生效月，而非全期最差月。新結果要說「購車月經常性結餘」；若承諾全期每月都符合，需新增另一個指標與限制，不能偷偷改舊欄位意義。
- **推論：What-if 舊回應覆蓋。** `vehicle-analysis.js:110` input listener 只隱藏結果，沒有更新 `analysisRequest()` 用的 revision 或取消請求；需在 Phase 0 用延遲回應測試重現並修補。本輪未操作瀏覽器重現。
- **確認：LLM schema 模式不同。** `gemini_provider.py` 超過 8,000 bytes 改用 JSON MIME＋prompt schema＋後端驗證；8,000 是本專案閾值，不是 Gemini 官方容量上限。不能將所有呼叫都描述為原生 strict structured output。
- **確認：Mock 的使用方式。** `MockAIProvider` 可依賴注入；`get_ai_provider()` 目前只選 openai/gemini，沒有 `AI_PROVIDER=mock` 分支。計畫採測試注入，不宣稱環境切換已支援 mock。
- **確認：價格搜尋精度修正尚未 commit。** 工作目錄已有 cent search 和單車 90 秒 timeout；部署版本是否包含它，須另查部署版本。本輪不推送。
- **待驗證：正式站效能與真實 Gemini。** 本輪不傳送財務內容至外部 AI，測試通過不代表 provider 配額、模型可用性與雲端冷啟動已驗收。

## 3. Existing vs Planned Gap Analysis

| 新能力 | 重用 | 最小新增 | MVP 邊界 |
|---|---|---|---|
| 分步問卷 | 現有 input、金額格式、錯誤提示及確認模式 | `car-needs.html/js`、需求 schema、條件式問題表 | 4 步，返回不丟資料；選車必填與財務評估必填分開 |
| AI 理解 | provider、loader、mock、timeout 模式 | 專用 prompt、candidate parser、conflict resolver | 不把需求塞進 FinancialExtractionResult；必要追問最多兩輪 |
| 推薦 | catalog 與現有數值 engine | 三態 filter、共同評分尺度、理由 codes | 最多 8 個候選、3 個結果，職業不參與分數 |
| 真實資料 | 目前 Toyota/Honda 來源 | 版本化 typed catalog、BEV 樣本、來源欄位 | 先可靠再擴量；舒適度不自創分數 |
| 能源與保養 | `monthly_fuel_or_energy`、年度預算 adapter | 純函式 cost breakdown、週期計算、缺值狀態 | 保養預算按月提列；實際到廠付款時間後續 |
| 折舊 | 現有現金流不需改 | 殘值區間與成本 sidecar | 有殘值假設才計完整 TCO；不從現金再扣折舊 |
| 解釋／自然語言調整 | `evaluate_variant()` 及 financial outputs | evidence-only explanation、白名單變更候選 | 不開放 LLM 任意 URL、SQL 或 Python 執行 |
| 保存 | 舊草稿機制可參考 | 本機明確保存與 JSON 匯出，確認快照 | 無登入、無跨裝置同步，避免導入新 DB 工作阻塞 |

## 4. AI System Architecture

1. 前端收集結構化答案，後端驗證，產生缺漏與條件式問題。
2. 有自由文字時才呼叫 LLM。輸入只有當前文字、相關答案、pending question ID；不傳姓名、公司、完整紀錄或整份財務資料。
3. LLM 回傳候選 facts/conflicts/ambiguities，不更新草稿、不推薦車款、不計算金額。
4. 後端檢查 evidence、值域、衝突與缺漏，產生可修改的確認摘要。
5. 使用者確認；後端綁定需求版本、財務資料 hash、用車與付款條件。
6. Rule engine 在版本化 catalog 上篩選，再以相同條件計算並排序。
7. 選定車款後交給既有財務服務；結果保存 engine/catalog/assumption/scoring 版本。
8. 解釋只引用後端已產生的 metric ID、reason code 與 source ID，前端代入真實數字。
9. 自然語言調整先轉成允許的參數變更，顯示「原值 → 新值」並確認，後端重新運算。

後端控制狀態：`editing → needs_clarification → awaiting_confirmation → confirmed → evaluated`。任何影響推薦的修改使確認失效；拒絕過期 revision，前端取消／丟棄舊回應。

AI 只可建議「問哪個允許欄位」，後端再判斷必要性與優先順序；問題文字以簡短模板為預設。職業可影響提問，例如是否載客，但不能替使用者回答載客、收入或里程。

### 安全、隱私與成本

- User text、catalog descriptions 都是資料。LLM 不持有 DB、shell、任意網路工具或寫入權限；prompt injection 即使產生候選也須過 schema、證據、確認與白名單。
- 可由使用者輸入的數值證據需指向原文字片段；單靠合法 JSON 不能證明語意正確。衝突值不自動覆蓋。
- 新抽取 schema 以小型 enum/nullable object 設計並量測 native schema bytes；真實 provider smoke test 後鎖定可用 model ID，不在未測試時自動追隨 latest alias。
- 建議自由文字上限 1,000 字、每次一個問題、最多兩輪 AI 追問；之後直接顯示缺漏表單。一次完整流程目標 1–3 次抽取呼叫，解釋最多一次；變更條件後按需重算。
- 成本以「實際 input/output token × 當期模型單價」計，不在此文件猜固定費用。記錄 provider/model/schema mode/耗時/成功/token，不記原始財務對話或 key。
- 外層 total deadline 20 秒；429/5xx 最多一次、且在剩餘期限內重試；格式錯誤不反覆付費重試。前端 deadline 要大於後端 deadline 並恢復可操作狀態。
- AI unavailable/no_match/invalid_output/timeout 分別回傳；固定問卷與計算不依賴 AI 成功。
- 現有 IP rate limiter 僅單 process，不能當跨 worker 配額管理；MVP 限制輸入、候選數與單次耗時，正式多人服務再加入共享配額。
- 財務問卷預設僅本頁記憶體；「儲存到此裝置」由使用者選擇，可清除。避免把薪資、存款放 URL 或 analytics。

## 5. API / Pydantic Schema 設計

以下是待實作契約，非現存 API。新 routes 建議放 `app/api/car_recommendation.py`，由 `main.py` 掛載；保留現有 API。

| Endpoint | 輸入 → 輸出 | 規則 |
|---|---|---|
| `POST /car-needs/validate` | `NeedsDraft` → missing fields、衝突、next_question | 不呼叫 AI，可跳過 optional |
| `POST /car-needs/extract` | `NeedsExtractionRequest` → `NeedsExtractionResult` | 候選值＋evidence，無合併／排名 |
| `POST /car-needs/confirm` | edited needs、resolved conflicts、revision → `ConfirmedNeedsEnvelope` | 確認當下完整驗證；必要缺漏不簽發 |
| `POST /car-recommendations` | confirmed envelope、usage/payment/profile → `RecommendationResult` | 無法確認硬條件列 needs_verification，不能靜默放寬 |
| `POST /car-recommendations/explain` | 已確認請求及車款 ID → `ExplanationResult` | 後端重新取得／計算結果，不信任客戶端傳入金額 |
| `POST /car-recommendations/adjust` | 原已確認請求、文字 → `AdjustmentCandidate` | 只產生變更候選；確認後重新推薦／模擬 |

### 5.1 共用驗證

所有新模型 `extra='forbid'`、禁止 NaN/Infinity；enum 未知值拒絕。整數 strict，布林不能當金額。API 金額採有界 Decimal 字串契約、最多兩位小數；向既有 float profile 的轉換集中在 adapter，禁止 frontend 重新計算。

里程非負、充電與路段比例介於 0–1、比例合計容許誤差不超過 1e-6；年限 MVP 1/3/5、個人引擎維持 60 月。零代表明確沒有，null 代表未知；不得互換。

### 5.2 主要模型

| 模型 | 欄位與限制 |
|---|---|
| `NeedsDraft` | schema_version、revision、background、usage、constraints、preferences、financial_profile?、free_text；required/optional 由用途判斷 |
| `Background` | occupation enum?（student/employee/sales/self_employed/other/unspecified）、household_size?；職業無數值推論 |
| `UsageProfile` | monthly_distance_km?、city_share?、highway_share?、purposes[]、usual_passengers?、cargo_requirement?、parking_type?、home_charging?、reliable_public_charging?、home_charging_share?、ownership_years |
| `HardConstraints` | budget_max?、budget_basis=`vehicle_price`、allowed/avoid body_types、min_seats?、required_features[]、allowed_powertrains[]；月支出上限另欄位，不混車價預算 |
| `Preferences` | criterion、importance=0..5、desired_value、strength=hard/soft；同一項不得同時要求與排除 |
| `NeedsExtractionRequest` | latest_text≤1000、related_answers、pending_question_id?、revision；不接受任意 prompt 檔名 |
| `NeedsExtractionResult` | typed candidates[]、conflicts[]、ambiguities[]、suggested_question_field?；不含 recommendation、score、price、engine_result |
| `ExtractedNeed` | discriminated union；field enum 決定 value 型別、source=user_statement、evidence quote/span、confidence 0..1。confidence 只標示抽取，不作推薦分數 |
| `NeedConflict` | field、existing_value、candidate_value、evidence；兩個值皆顯示，user resolution 才能通過 |
| `ConfirmedNeedsEnvelope` | canonical payload、revision、content_hash、confirmation_token、expires_at；後端 HMAC 簽署及驗證 |
| `CandidateEvaluation` | vehicle_version_id、eligibility=eligible/ineligible/needs_verification、checks[]、missing_fields[]、score_components[]、score?、cost_status、financial_status |
| `RecommendationResult` | candidates≤3、verification_candidates、excluded_counts_by_reason、weights、normalization_bounds、catalog/engine/scoring/assumption_version、input_hash、limitations |
| `AdjustmentCandidate` | field enum、operation=set/relative_change、value、unit、original_value、proposed_value、evidence；計算 proposed_value 在後端 |
| `ExplanationResult` | statements[]（reason_code、metric_refs[]、source_refs[]、qualifier）、status=ai/template；數字由 renderer 依 metric refs 代入 |

MVP 的 confirmation token 綁定完整會影響結果的資料，包括 profile/usage/付款條件。修改任一欄要重新確認。使用專用 backend secret，未設定時明確失敗，不沿用開發預設 JWT secret。token 不是登入或資料擁有權憑證；端點仍要限流。無 DB 的 stateless 方案可重放有效 token 進行相同計算，但不能變更輸入後沿用確認。

financial_profile 為空仍可做「需求與用車成本推薦」，`financial_status=not_evaluated`；不顯示負擔得起。要求個人財務排名時才需完整 `DecisionProfile`。

## 6. Database / Vehicle Data Schema 設計

### 6.1 MVP：版本化資料檔優先

新增 `data/vehicles/` JSON 與 Pydantic 載入驗證，保留原有 5 個 catalog ID。既有 `/catalog` 欄位與順序契約保留，新增 richer endpoint 或 adapter 供新問卷使用。不要把現有 HEV 的效率欄位改名而破壞舊 JS。

| 模型 | 核心欄位 |
|---|---|
| `VehicleVersion` | id、brand、model、trim、model_year、market=TW、valid_from/to、powertrain=ICE/HEV/BEV、body_type、seats、spec_revision、catalog_version |
| `SourcedValue[T]` | value nullable、unit、source_type=official/third_party/model_assumption/user、source_url?、source_title、published_at?、checked_at、applicable_trim、notes、verification_status |
| `VehicleEnergySpec` | combined/city/highway km_per_l 或 kwh_per_100km、test_cycle、measurement_basis=battery/grid/unknown；不得混用不同測試週期當完全公平實測 |
| `MaintenanceItem` | item_id、description、interval_km?、interval_months?、trigger=either_first、first_due?、parts/labor/total_cost nullable、price_basis、來源、是否例行／視情況 |
| `FeatureEvidence` | feature code、known true/false/unknown、spec source；行李廂容積是容積，不能自動轉成乘坐舒適分數 |
| `ResidualAssumption` | horizon、low/expected/high residual_value、source type、方法、里程及車況假設；未知保持 null |

資料發布前兩人核對車型版本、單位、日期、來源。保養項目的官方週期與價格可來自不同來源，必須各自標籤。沒有官方價格時，可使用已確認的使用者預算，但結果必須標「預算估算」。

資料庫不是 MVP 前提。日後有多管理者更新需求再遷移：`vehicle_versions`、`vehicle_facts`、`maintenance_items`、`data_sources`；版本不可原地覆蓋，已保存分析引用固定版本。

若後續支援帳號保存，再新增 `car_needs_snapshots`、`recommendation_runs`（user_id、input_snapshot、version hashes、result_snapshot、created_at）。先完成 Auth 與逐表 RLS policy/測試，再允許使用者資料寫入；僅 enable RLS 不等於功能可用。公開車款只讀，管理更新只限後端授權角色。本輪不套用 SQL、不接觸遠端 DB。

### 6.2 資料來源可行性查核

- [Toyota 台灣 Corolla Cross 規格比較](https://www.toyota.com.tw/showroom/COROLLA_CROSS/compare.aspx)：可取得版本規配與測試油耗資訊；官網提醒測試值有適用條件。本輪確認來源頁可讀，未逐筆重新認證 repository 的所有價格。
- [Tesla 台灣車輛保養](https://www.tesla.com/zh_tw/support/vehicle-maintenance)：可作電車保養項目／週期來源；不能由「不需換機油」推定總保養價格為零，亦不能由此推估所有品牌 BEV 費用。
- [Gemini structured output 文件](https://ai.google.dev/gemini-api/docs/structured-output)：支援 JSON Schema 子集與 Pydantic；合法結構仍需業務驗證。正式 model 的支援模式須 smoke test。
- [Supabase RLS 文件](https://supabase.com/docs/guides/database/postgres/row-level-security)：作為日後資料存取設計依據；不是本專案已部署 RLS 的證據。

以上核對日期 2026-10-20。未取得的官方 BEV 車價／電耗、各車型保養金額仍列 Phase 1 資料工作；不在規劃文件捏造價格。MVP 不做即時爬蟲、背景自動換價或 AI 搜尋補價格。

## 7. Recommendation Algorithm Design

### 7.1 硬條件與資料缺漏

每個條件回傳 `pass/fail/unknown` 與證據：

- 已知價格高於預算 → fail；價格未知 → unknown，列「資料待補」。
- 使用者排除 SUV 且 catalog 證實是 SUV → fail；body_type 未知 → unknown。
- 座位數不足 → fail；空間主觀期待無量測資料 → 保留未評估偏好。
- 無家充不是自動排除 BEV；若使用者明確要求家充或完全沒有可接受充電方式才依條件判定。充電狀態未知要追問。
- 職業、性別、年齡不產生收入／里程／舒適度推定，不進排名。
- 沒有符合車款時顯示造成空集合的條件與修改入口；不偷偷增加預算或取消車型限制。

`unknown` 車款不混入「已符合」榜單，也不標成不符合；獨立可見，提供需確認資料。

### 7.2 可解釋評分

先判斷 eligible，再評分。MVP 預設：成本 60%、可量化偏好符合度 40%；這是可修改的設計權重，不是經研究證明的最優值。財務門檻是獨立 pass/fail，不再用收入與成本重複加分。

`score = 100 × Σ(w_k × s_k)`，所有候選使用同一組 weights、尺度與有效 criteria。

- 成本採同期間、同用途、同付款假設的模型指標；成本越低得分越高。MVP 五年、立即購買、共同貸款年限≤60月，避免靠不同觀察窗或延長貸款營造便宜。
- 若各車均有可比較的殘值與完整成本資料，使用五年 TCO。否則只能切換成明示的「五年現金支出」排序，貸款須在觀察期內結清、共同付款政策；無法滿足則不提供單一成本總排名。
- 使用候選集合共同 min/max 作尺度並回傳 bounds；全部相等時同分，無差異。清單改變可能改分，UI 不宣稱跨版本 80 分具有相同意義。
- 能源已包含在 TCO/現金支出，不再額外加一個能源成本權重。偏好分只包含有證據且由使用者選擇的規格匹配，例如指定品牌／車身型式／配備。
- 缺資料的 criterion 不可對各車各自重分配權重。使用全體候選的共同可評項目；若重要項目缺漏，取消該項總排名並顯示缺口，而非獎勵缺資料車款。
- 主觀舒適度、實際安全性沒有資料時只列「待試乘／待查證」，不編造星等。具某安全配備不等於碰撞測試安全分數。
- ties 以固定 vehicle_version_id 決定穩定順序並明示同分。把每項 contribution、規格證據、成本來源一起回傳。
- 財務限制不符合的車可列「符合用車需求，但未通過你的財務條件」，不得用總分掩蓋。

推薦可信度用「資料完整性、假設項目、版本」表達，不用 LLM confidence 冒充購車成功機率。

### 7.3 效能策略

MVP 先篩至最多 8 款，純成本與輕量財務評估共用 baseline。完整四壓測及 find_limit 只對使用者選定的最多兩款執行，沿用既有 API 結果。

不建議立即加背景 job queue 或平行開多個 Python CPU 任務。先量測 warm p95、同時兩名使用者、Render 冷啟動；如不達標，降低候選數與延後昂貴分析。不能只增加瀏覽器 timeout。

## 8. Financial Calculation Change Analysis

### 8.1 沿用的計算

- 車貸 PMT、本金與頭期關係：`app/core/events.py:7`、`scenario_engine.py:69`。
- 月現金：上月現金＋收入－生活支出－既有／新貸款＋事件淨額。
- 年薪資調整：`salary × (1 + raise_rate)^floor((month-1)/12)`。
- 通膨：`inflation_factor()`；變動支出、持有成本與交通抵減逐年調整，固定支出可選、固定名目車貸不調整。
- 既有貸款明細到期後停止；未提供明細時總額全期扣款。
- 預備金：現金 ÷（模型中的生活支出＋還款），零分母回 null。模型目前未區分所有必要與可裁減支出，不應過度宣稱為精準生活保障。

### 8.2 只補缺少的純計算模組

`vehicle_energy.py`：

- ICE/HEV：`liters = distance / km_per_l`。
- 有同一測試規範的 city/highway 數據才用 `D × city_share / e_city + D × highway_share / e_highway`。不能對 km/L 直接做算術平均。
- BEV：若電耗定義為電池端，`grid_kwh = D × kwh_per_100km / 100 / charging_efficiency`；若已是電網端則不再加損耗。basis 未知需標示或要求使用者確認假設。
- 電費：`grid_kwh × (home_share × home_price + public_share × public_price)`，share 合計1。按度費與按次／占位費分開；後者缺資料時列未涵蓋。
- 城市／高速比例無對應分項規格時不製造效果，採 combined 數據並明示限制。

`vehicle_maintenance.py`：

- 對每個已核實 item 用「時間／里程先到」計次；達界限當月計一次、同次不重複；第一次保養與後續週期可不同。
- 以固定月里程、從新車里程0開始為 MVP；中古車現有里程與不規則使用延後。
- 需要檢查才決定的更換件不能無條件當必發，列預備預算或可選情境。
- 任一必要價格未知時，不得當0。回傳 missing price；使用者確認整體預算後切換 `budget_estimate` 模式。
- `schedule_estimate` 與 `budget_estimate` 互斥，不能同時加總。MVP 將期間估計換成規劃月預算接到既有 engine；UI 說明非實際保養月付款。
- 引擎只對已確認的 base budget 做一次通膨，保養估算器不要先通膨後又被引擎重複調整。

`vehicle_valuation.py`：

- `depreciation = purchase_price - residual_value`，殘值可以有 low/expected/high，由來源或明確使用者假設支撐；不自動給所有品牌固定百分比。
- `economic_TCO = depreciation + horizon_interest + gross_running_costs + included_one_time_fees`。
- 現金流已含頭期／全額付款與車貸，不再扣折舊。不把貸款本金與原車價同時計入 TCO。
- 尚未出售時殘值不加到現金；若選擇期末出售才新增售車入帳並清償剩餘本金及已知費用。
- 期末「現金＋車輛殘值－未償車貸本金」只稱已涵蓋資產範圍的淨值，不稱完整個人淨資產。
- 現有 API 只有 remaining_loan_months，沒有未償本金與期間利息拆分。要支援跨期 TCO／售車清償需補攤還明細純函式與獨立公式測試；不能用「剩餘月數×月付款」代替本金。

### 8.3 模型口徑與相容性

新推薦使用同一 baseline month、purchase month、觀察期、收入支出與通膨假設。成本與個人財務視圖分開標示；個人五年預測保持60月，1/3年純成本不可拿來直接排名五年財務。

規劃採 adapters 將新能源／維護結果轉成既有 payload。新增 TCO/valuation 欄位用新 response model，不重新定義 `net_cash_outlay`。現有 5 個 catalog ID、loan API、成本來源 enum 必須通過相容測試；新的 official 資料來源由 catalog provenance 保存，轉入舊 SourcedDecimal 使用既有允許的 derived/backend_normalized 並保留 evidence reference。

稅費、保險沒有逐車資料仍可用使用者明確預算。電車不能沿用油車固定稅額並稱為官方數字；若要自動稅額，另核對適用地區、年份、動力與法規。本次不承諾稅務引擎。

## 9. Frontend User Flow

新增「幫我選車」入口，既有「直接試算」可直接進入。沿用原生 HTML/JS/CSS，不引入新前端框架。

1. **需求**：預算、一般乘坐人數、車型限制；職業／家庭人數選填。家庭人數不直接等於最低座位數。
2. **使用方式**：月里程、用途、停車；考慮 BEV 才問充電，無市區分項數據時不多問無法使用的精細比例。
3. **偏好與補充**：最多三個重要偏好、自由文字；「後座舒服」保留為試乘提醒。
4. **確認**：顯示 AI 抽取的變更、衝突、未知值；可回上一頁，財務資料為可選展開步驟。
5. **結果**：最多三張車款卡，最顯眼是符合的需求、每月養車＋車貸、五年成本口徑、財務限制狀態。點「怎麼算」展開公式、來源與假設。
6. **比較**：勾選最多兩款，預填至既有比較表單；付款與財務資料帶入後仍顯示確認。不得一選車就觸發昂貴模擬。

範例需求「房仲、常載客、不喜歡 SUV、100萬內」應明確保留三個已知條件，下一題只問真正缺少的資料（例如每月里程）；不因職業預填高里程。若 catalog 沒有符合的非SUV，直接顯示無符合，提供資料不足與可修改條件。

前端使用 textContent 渲染 AI 字串，沒有任意 HTML；修改條件取消／丟棄舊推薦及舊 AI 解釋。保留輸入、錯誤就近顯示、鍵盤操作、390px 寬不橫向溢位。數值主摘要用易讀四捨五入，限制判斷仍用未顯示四捨五入的後端值。

## 10. Testing and Acceptance Criteria

### 10.1 本輪基線

- Node：已執行既有七個測試檔，共 **72 passed**。
- Python：執行 `D:\DingFeng_Agent\Python312\python.exe -B -m pytest -p no:cacheprovider -q`，**311 passed，79.97秒**。另有2則既有 JWT 測試用 HMAC key 長度警告，本輪未修改認證程式。
- Node 命令：`node --test tests/test_profile_onboarding.js tests/test_scenario_draft.js tests/test_transparency.js tests/test_vehicle_ui.js tests/test_vehicle_analysis_ui.js tests/test_vehicle_catalog_ui.js tests/test_vehicle_costs_ui.js`。
- 本輪未做真實 Gemini 呼叫、遠端 Supabase 查詢、正式站負載或全流程瀏覽器驗收。
- 不新增功能測試檔；下面是後續實作的驗收規格。

### 10.2 必要測試矩陣

| 範圍 | 必測案例與標準 |
|---|---|
| Schema | null≠0、未知欄位／enum、NaN/Infinity、非法比例、負金額、過長文字、來源不完整均有明確結果 |
| AI 抽取 | 多需求同句、排除SUV、否定品牌、缺里程、中文金額、原問卷衝突、prompt injection；mock 為自動化必備，職業不產生未知數值 |
| 確認 | 未確認不得推薦；修改 profile/usage/付款或 revision 後舊 token 無效；token 過期／被竄改被拒絕 |
| 篩選 | pass/fail/unknown；無車符合；沒家充但可公共充電；缺 seats 不等於座位不足；不偷偷放寬限制 |
| 排序 | 權重和1、固定尺度、所有成本相同、資料缺漏、穩定 tie、不能重複計入能源、硬條件優先、相同輸入與版本結果完全一致 |
| 能源 | km/L 換算、kWh/100km、家充比例0/1、比例加總、零里程、grid/battery basis、損耗不重複 |
| 保養 | 里程先到／時間先到／同月同時到、第一期、零里程仍到時間期限、未知價格不為0、預算與排程互斥 |
| 財務 | 0利率、現金／貸款、期限跨期、殘值不改現金、售車清償、調薪／通膨、既有債務到期、交通抵減不雙算 |
| 相容 | 原單車、雙車、自訂車款、舊catalog ID、60月模擬、find_limit 分位精度與既有回歸保持 |
| 解釋／調整 | 每個 metric_ref 真實存在、變更後重新算、油價＋20%不等於總成本＋20%、過期解釋不顯示、LLM無法任意執行工具 |
| UX | 返回修改、跳過選填、無AI仍完成、重複送出、慢回應、錯誤可重試、手機、鍵盤、空結果 |

量化驗收目標（待實測，不是已達成）：

- 用20–30組人工標註需求測 extraction；硬限制 precision 100%、recall至少95%，未知數值捏造0。固定小樣本只作展示驗證，不能泛化宣稱模型準確率。
- 以獨立 Decimal/Excel 對照 loan/energy/TCO 邊界；定義相同逐月 rounding policy 後金額差≤NT$0.01，不能使用同一 production helper 自我驗證。
- 可比較候選的已知硬條件違反0；版本固定時排名重跑100%一致。
- warm target：≤8款推薦 p95≤5秒；選定兩款完整模擬 p95≤15秒，於實際部署層級量測。超標先減少昂貴分析／候選，不宣稱90秒timeout就是效能改善。
- 冷啟動單獨記錄；失敗保留輸入且可退回表單。AI timeout不阻塞rule-based結果。
- 5–10位大學生／社會新鮮人，3個任務：完成選車、解釋成本差異、修改充電／里程條件；目標≥80%無協助完成、首次結果中位數≤5分鐘、≥80%能分辨每月現金與折舊，記錄原始人數而非只百分比。
- 與「只給成本表」版本比較理解題及完成時間，採交錯順序減少學習效應；小樣本報描述統計與限制，不宣稱統計顯著。

## 11. Development Phases and Estimated Hours

順序調整：先核對能取得哪些車款資料，才能決定問卷哪些偏好可評；不要先做舒適度權重再發現沒有資料。

工時為有效人時，不是曆時；假設四人可分工、熟悉現有專案、API key 已可用。每階段完成需通過該列驗收再合併；不把 Claude Review 當測試替代。

| 階段 | 工時 | 依賴／檔案（預定） | 交付與驗收 |
|---|---:|---|---|
| 0 契約與可靠性 | 4–6h | `vehicle-analysis.js`、相關測試；本計畫 | Claude通過成本口徑／缺值／確認設計；重現並處理舊What-if競態；記錄部署基線 |
| 1 資料可行性＋schema | 10–14h | `app/car_needs_schemas.py`、`app/vehicle_data_schemas.py`、`data/vehicles/`、catalog adapter | 6–8版本來源可追溯，至少ICE/HEV/BEV與兩種車身；缺值不偽裝0；舊5個ID相容 |
| 2 問卷＋確認 | 10–14h | `static/car-needs.html/js/css`、`app/api/car_recommendation.py`、`app/services/car_needs.py` | 無AI完整走完需求確認；可返回／跳過；token/revision驗證；財務選填 |
| 3 AI需求理解 | 8–12h | `app/prompts/car_needs_extraction.md`、`app/services/car_needs_extraction.py`、mock fixtures | 無捏造、衝突必確認、一題一問；schema失敗和斷線仍可手填；一次人工真實provider smoke |
| 4 成本adapter＋規則推薦 | 16–22h | `vehicle_energy.py`、`vehicle_maintenance.py`、`car_recommendation.py`、既有cost services的窄幅adapter | 有三態filter／權重／資料缺口；能源獨立驗算；最多3款；單／雙車結果口徑一致 |
| 5 解釋與調整整合 | 6–8h | `car_explanation.py`、`car_adjustment.py`、兩個prompt、新頁JS | 固定模板必備；AI引用metric refs；油價相對變更確認後後端重算；舊解釋失效 |
| 6 回歸、使用者測試與展示 | 12–18h | 新增tests、`docs/`、固定展示fixtures | 基線回歸通過、5–10人測試、問題修正、可離線AI展示、資料與模型限制頁 |

基本合計 **66–94人時**；加20%整合緩衝約 **80–113人時**。其中階段0–5為 **54–76人時**，含緩衝約65–92人時，才是11/01前的核心工作。

完整殘值/TCO/跨期貸款明細另外 **12–20h**；若尚需大量蒐集保養價格另外 **8–16h**。這兩項不應隱藏在核心估計內。完整主觀評分校準、跨裝置保存、更多車款另估，不能保證本時程交付。

四人分工：

- A：schema/API/確認狀態及推薦規則。
- B：官方資料核對、能源／保養與獨立計算對照。
- C：分步問卷、推薦結果與原購車頁交接。
- D：provider抽取／解釋、整合測試、使用者測試與展示。

每項仍需另一人review。四人不是每項工時除以4；schema與資料會阻塞推薦，整合至少預留連續2天。

### 11.1 日期與停止條件

| 日期 | 里程碑 | 未達標時處理 |
|---|---|---|
| 10/20–10/22 | Claude Review、API/schema凍結、代表車款來源確認 | 沒有BEV可用電耗時，先完成ICE/HEV，不拿估值偽裝官方 |
| 10/23–10/26 | 固定問卷→確認→mock推薦端到端 | 未完成就暫停AI解釋與TCO，優先打通基本流程 |
| 10/27–10/30 | 真實需求抽取、規則排序、能源與既有單／雙車整合 | 缺保養價格以明示預算模式；無法比較完整TCO則只顯示成本分項與現金口徑 |
| 10/31–11/01 | 核心回歸、部署、固定demo、功能凍結 | 禁止新增車種與新架構；留下可操作的降級流程 |
| 11/02–11/08 | 使用者測試、資料／UX修正、負載與失敗演練 | 只修影響理解／正確性／穩定性的問題 |
| 11/09–11/18 | 簡報、來源附錄、錄影備援、口試演練 | 不做資料庫遷移或模型大改版 |
| 11/19 | 展示 | 先show可重現計算，再show AI與失敗fallback |

10/20到11/01約12個曆日。每人每週約12–15有效小時、四人約82–103人時，才有機會容納核心與緩衝。若團隊實際合計不到65人時，縮為固定問卷＋ICE/HEV小目錄＋規則排序＋既有模擬；AI只留一次自由文字解析，電車、TCO與自由變更延後。

## 12. Risks and Trade-offs

| 優先級 | 風險 | 措施 |
|---|---|---|
| 高 | 問卷承諾能力超過資料能支持 | 先核資料；不能評的舒適／安全保留提醒與來源，不偽造分數 |
| 高 | 排名受缺值、不同年份／成本口徑誤導 | 三態filter、共同尺度、版本固定、缺完整成本不產生完整TCO排名 |
| 高 | 多候選完整模擬造成逾時 | 先輕量排序，選定後完整分析；實測雲端與並行請求 |
| 高 | 折舊與付款重複、長貸款看似便宜 | 現金與TCO獨立；MVP共同付款政策且期內結清；跨期功能需本金明細 |
| 中 | 模型合法JSON但錯解需求 | evidence、語意驗證、衝突確認、人工標註集與mock |
| 中 | 最新別名或schema支援變動 | 測試後固定model、prompt/schema版本；AI不可用可降級 |
| 中 | 記憶體保存被誤當資料庫 | MVP明確本機保存／匯出；日後DB需Auth/RLS，不直接公開草稿ID讀取 |
| 中 | UI一次出現太多問題 | 4步＋條件追問、預設不展開財務與計算細節、最多3結果 |
| 中 | 官方資料更新造成舊結果不可重現 | 保存資料快照與hash，更新新版本，不覆蓋舊run所用版本 |

**Must-have**：可靠少量車款、短問卷、需求確認、三態規則推薦、可追溯能源成本、既有財務串接、mock／回歸／降級。

**Should-have**：BEV充電習慣、保養週期與可確認價格／預算模式、數據引用式AI解釋、油價變更。

**Could-have**：有依據的殘值範圍與TCO、更多客觀配備比較、本機報告匯出。

**Out of Scope（本次口試版）**：多代理、即時全網爬價、全品牌維修報價、舒適度自創評分、真實殘值預測、投資建議、跨裝置帳號平台、新Monte Carlo、第二生活情境同步開發。

口試技術價值在於「LLM候選提取與確定性推薦／計算的責任分離」、「可追溯資料與缺值處理」、「同一財務引擎跨車款重用」、「實驗證明使用者理解成本差異」。不以串接AI或車款數量當唯一貢獻。

## 13. Claude Review Checklist

- [ ] Audit是否正確辨認雙車財務比較已整合，沒有重做同功能？
- [ ] 新需求schema是否獨立於財務抽取，provider/loader/mock可重用？
- [ ] 候選抽取是否無權合併、確認、排序或計算金額？
- [ ] 確認token是否綁定所有影響結果的輸入、revision與版本？
- [ ] 職業是否只觸發問題、不推測收入／里程／喜好？
- [ ] unknown條件是否獨立呈現，無資料是否不被當0或不符合？
- [ ] 評分是否共同尺度／權重、避免energy與TCO重複計分？
- [ ] 舒適／安全是否只用可證明指標，缺資料是否不產生虛構分數？
- [ ] 油耗分項加權、電耗單位、充電損耗與充電比例公式是否正確？
- [ ] 保養時間／里程先到及未知費用處理是否可實作且不重算？
- [ ] 現金、TCO、殘值與貸款本金是否分清，長貸款是否造成錯誤排序？
- [ ] 個人評估60月與1/3年成本口徑是否明確隔離？
- [ ] 敏感度／壓力結果是否避免稱為發生機率？
- [ ] 推薦是否避免為每款跑find_limit與完整壓測？
- [ ] AI解釋是否只能引用backend metric，客戶端偽造結果是否被拒絕？
- [ ] AI失敗、Render冷啟動、舊回應與資料返回修改是否有驗收？
- [ ] 資料庫實際狀態是否如實描述，未實作保存是否沒有誤導？
- [ ] 11/01前65–92核心人時是否符合團隊可用時間，資料缺口是否有裁切點？
- [ ] 完整TCO與殘值額外工時是否明確，不被算成免費附加功能？

請 Claude 依 P0/P1/P2 回報具體問題、對應段落、修正建議與是否阻擋實作。確認計畫後，再逐階段實作並提交可檢查差異；本文件不授權自動部署或改動正式功能。
