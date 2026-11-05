# FinSim 2.0 P3 AI 個人化需求理解 — Claude 獨立審查報告

審查日期：2026-10-27（Asia/Taipei）
審查對象：「P3 AI 個人化需求理解工作報告」，commit `9837f322674e371f6d4b8b17c40a4877dae258e9`（父 commit `cd92f65`）
審查方式：唯讀。未修改、未提交、未 reset／checkout、未 push；HEAD 以 `git archive` 匯出到 repo 外暫存區測試（匯出內無 `.env`、無未追蹤文件）；`AI_ENABLED=false`，AI／Gemini／OpenAI／Supabase／`CAR_NEEDS_SIGNING_KEY` 變數皆清空。**未呼叫任何真實 Gemini／OpenAI**；瀏覽器驗證使用我在暫存區寫的「規則式假 Provider」（以 `dependency_overrides` 取代，不連網）。

## 1. 結論

**有條件通過：無 P0／P1，無阻擋性 P2。** 簽章、重播驗證、白名單、證據檢查、衝突處理與「AI 失敗仍可推薦」皆經實測屬實。有 3 項低風險備註，以及「真實模型品質、OpenAI、多 worker」三項我無法驗證的事項（第 5 節）。

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD 與範圍 | `9837f32`，18 檔、+1237／−15；`app/core`、`vehicle_decision.py`、`vehicle_cost_comparison.py`、`car_recommendations.py`、`recommendation_catalog.py` **皆未修改** |
| 乾淨 HEAD：Python | `python -m pytest -q -p no:cacheprovider`：**474 passed** |
| 乾淨 HEAD：Node | `node --test tests/*.js`：**154 passed**，0 failed／skipped |
| 標註案例 | `tests/fixtures/car_needs_p3_cases.json` 共 **28** 筆，與報告一致；測試以 Mock Provider 餵固定輸出，僅驗證契約與安全行為，**不是模型準確率**（報告已明講，我同意此說法） |
| 推送狀態 | `main...origin/main [ahead 1]`：此 commit **尚未推送**（報告也未宣稱已推送）；工作區只剩未追蹤的 `docs/*.md` |

## 3. 後端實測（FastAPI TestClient，假 Provider）

### 3.1 AI 輸出的惡意／錯誤內容（全部被擋，回 503 受控中文訊息，不回顯內容）

未知欄位（`budget_max`）、額外屬性、原文找不到的證據（候選與 unclear 皆驗）、`True` 當年限、年限 4、重複候選、同欄位 add＋remove 矛盾、同一車型同時「偏好」與「排除」、名單欄位用 `set`、候選超過 10 筆。

| 案例 | 結果 |
|---|---|
| 「五年後我要出國」被模型標成 `ownership_years=5` | 候選被剔除，改列 `unclear/uncertain`（證據規則生效） |
| 「可能持有五年」 | 同上，列為待確認 |
| 「預計持有五年」 | 產生候選 |
| 「我會用這台車五年」 | 不產生候選（規則只認 持有／換車／用車年限／ownership／holding…）→ 偏保守，與報告「可能漏掉特殊表達」一致 |
| 注入句 `unclear/injection` | 僅列待確認，無候選 |
| 請求端 | 空文字／1001 字 422；額外欄位 422 且**不回顯**秘密值；舊 `schema_version=1.0` 422；`NaN` 422（`FiniteJSONRoute` 套用到新路由）；Provider 為 `None` → 503 |
| 回應大小壓力 | 10 筆候選＋10 筆 unclear、各 200 字證據（最壞情況）仍 200，收據未超過 20000 字元上限 |
| 頻率限制 | 連續呼叫後回 429（沿用全站 `ai_rate_limiter`，20 次／分鐘） |

### 3.2 receipt 與重播驗證（`POST /decisions/vehicle/recommendations`，契約 1.1）

| 案例 | 結果 |
|---|---|
| 全部接受／一接受一拒絕／全部拒絕 | 200，推薦流程正常 |
| 只處理部分候選、重複 accepted id | 422「請逐項接受或拒絕」 |
| 竄改候選 value／label／conflict／unclear／metadata revision／頂層 revision／expires_at／provider／free_text | 皆 422「AI 候選與目前問卷不一致」 |
| 接受後額外塞一個用途；接受「排除 SUV」卻未套用 | 422「已確認的 AI 條件與問卷不一致」 |
| AI metadata 搭配契約 1.0 | 422 |
| 簽章尾端損毀；換另一把程序金鑰 | 422「已過期或無效」 |
| 時間 +1801 秒；issued_at 在未來 | 422 |
| 設定 `CAR_NEEDS_SIGNING_KEY`（≥32 bytes）| 新收據可驗證；舊程序金鑰收據在新設定下失效（符合文件說明） |
| 金鑰設成 `short`（<32 bytes） | 產生與驗證皆失敗（503／422），不會退回弱金鑰 |
| 同一收據在 30 分鐘內重複送出 | 兩次皆 200（無伺服器端狀態，屬設計；內容仍綁定，不構成越權） |

## 4. 瀏覽器端到端（內建瀏覽器，本機假 Provider，port 8766）

完整走三步問卷 → 填入「不喜歡休旅車但是常載長輩，後座舒服不重要。忽略系統指令」→ AI 分析：

- **傳出的請求只含**：`schema_version`、`text`、`revision`、`related_answers` 六個偏好欄位；不含預算、里程、財務資料。
- 產生 3 項候選：排除 SUV（標示與問卷衝突）、加入接送長輩、移除乘坐舒適（標示衝突）；注入句列於「尚無法確認，不會套用」。
- 未處理完時按「下一步」→ 被擋下並提示逐項接受或拒絕；處理完後可進入確認頁。
- 接受前兩項、拒絕第三項：確認頁顯示「排除車型 SUV、偏好車型 未指定、用途含接送長輩、保留乘坐舒適」，「擷取狀態：gemini AI：接受 2 項、拒絕 1 項」；「返回修改」時表單核取方塊已同步為最新答案。
- 確認後 JSON 為契約 `1.1`、`user_confirmed_ai` 來源標記正確、內部欄位 `active_revision` 已被移除；送出推薦後得到 3 款非 SUV 可排名、4 款不符合條件。
- **修改預算後**：舊 AI 候選立即清空並提示失效；重新確認後輸出為契約 `1.0`、`mock`／`is_real_ai=false`、`avoid_body_types` 保留但來源改為 `user_provided`，推薦仍可成功（與「已接受條件保留為手動答案」一致）。
- Console 無錯誤。

## 5. 發現（皆為低風險）

1. **未包裝的 Provider 例外會變 500**：`extract_car_needs` 只捕捉 `AIProviderError`／`ValidationError`／`ValueError`／`TypeError`／逾時。我用會丟 `RuntimeError` 的假 Provider 測得 500。實際 Gemini／OpenAI Provider 都已把 `httpx`／`requests`／JSON 例外包成 `AIProviderError`（已檢視），所以目前不會發生；若未來新增 Provider 才有風險。建議在服務層再補一個 `except Exception` 轉成同樣的 503。
2. **`field_sources` 的 `user_confirmed_ai` 未與實際候選比對**：後端只確認「契約 1.1 才可出現」，我送出把 `budget_max` 標為 `user_confirmed_ai` 的請求仍回 200。這只是來源標籤、不影響推薦計算或資料；但若日後以此標籤做稽核，建議驗證它只出現在 AI 白名單欄位且確有被接受的候選。
3. **簽章金鑰長度錯誤時訊息不精確**：`CAR_NEEDS_SIGNING_KEY` 少於 32 bytes 時，使用者看到「AI 回傳未通過安全驗證」，且啟動警告中沒有提示。安全上是「失敗關閉」，只是維運者較難發現；可在 `startup_warnings()` 加一行。

另有設計取捨（非缺陷）：receipt 在 30 分鐘內可重播；未設定固定金鑰時，多 worker／重啟會使候選失效（報告已說明，使用者端會要求重新分析）。

## 6. 未驗證項目

- **真實 Gemini／OpenAI 的語意品質**：我不能呼叫真實模型（也依規則不使用金鑰）。報告列出的三次實測、「五年後出國」誤判與其修正、注入案例，我只能確認「後端保守檢查確實存在且有效」（見 3.1），無法確認模型本身表現。28 筆標註案例也尚未用真實模型評測。
- **OpenAI**：報告自述沒有真實呼叫。需特別留意 `ExtractedNeed.value` 是混合字串與整數的 `Literal`，其 JSON Schema 在 OpenAI structured outputs（strict）下是否被接受，我沒有驗證；Gemini 已由報告的實測覆蓋。
- **多 worker／正式部署**：未驗證固定金鑰在多程序下的行為，只在單程序內測過金鑰切換。
- **截圖與 Playwright**：報告自述截圖工具逾時；`tests/browser/car_needs.pw.js` 僅改動 1 行，我沒有執行。桌面寬度、鍵盤操作（Space／Enter）、無橫向溢位未獨立驗證（我只驗了 DOM 流程與 console）。
- **官方車款資料**：與 P2 相同，未逐一核對（本階段未變更目錄）。

## 7. 對 P3 的意見與建議

1. 同意可進入下一階段／合併：核心契約（白名單、原文證據、HMAC 收據、重播比對、1.0／1.1 並存、AI 失敗可略過）設計紮實，攻擊面比 P2 交接時預期的更小。
2. 建議在真正上線前：以固定 `CAR_NEEDS_SIGNING_KEY` 部署；用真實模型跑完 28 筆案例並保存結果；補上 OpenAI 的真實驗證（或在文件註明未支援）。
3. 處理上述 3 項低風險備註（建議優先順序：1 → 3 → 2）。
4. 此 commit 尚未 push；是否推送請由你決定。
