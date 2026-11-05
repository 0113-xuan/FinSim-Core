# FinSim 2.0 P3 收尾與 P4 桌面整合驗收 — Claude 獨立審查報告

審查日期：2026-10-27（Asia/Taipei）
審查對象：「P3 收尾與 P4 桌面整合驗收報告」，commit `6411888ba61e0aaf7ca05f0e7d6d653ccd729f21`（父 commit `9837f32`）
前次審查：`docs/CLAUDE_REVIEW_FINSIM2_P3_2026-10-27.md`（3 項低風險備註）
審查方式：唯讀。未修改、未提交、未 reset／checkout、未 push；HEAD 以 `git archive` 匯出到 repo 外暫存區測試；`AI_ENABLED=false`，AI／Gemini／OpenAI／Supabase／`CAR_NEEDS_SIGNING_KEY` 變數皆清空。**未呼叫任何真實 Gemini／OpenAI**，也未重跑 28 案例付費評估（只分析已提交的結果檔）；瀏覽器驗證使用我在暫存區寫的規則式假 Provider。

## 1. 結論

**CONDITIONAL GO 判斷合理：P3 三項備註皆已修正且實測有效；無 P0／P1，無新增阻擋性 P2。** 但真實 Gemini 評估 17／28 逾時，報告對此的限縮說法（不宣稱 AI 品質或穩定性通過、不建議把 AI 設為必經流程）我完全同意，並認為這是目前最大的待決事項（見第 4 節）。

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| HEAD 與範圍 | `6411888`，14 檔、+1701／−9；其中程式僅 `car_needs_extraction.py`、`config.py`、`car-needs.js`、兩頁 HTML 與 `style.css`；財務引擎、推薦演算法、車款目錄**未修改** |
| 乾淨 HEAD：Python | `python -m pytest -q -p no:cacheprovider`：**492 passed**（與報告相同） |
| 乾淨 HEAD：Node | `node --test tests/*.js`：**154 passed**，0 failed／skipped |
| 推送狀態 | `main...origin/main [ahead 2]`：P3、P4 兩個 commit **都尚未推送**（報告也說不 push） |
| 提交內容無機密 | 提交的評估 JSON／MD 內搜尋 receipt、`AIza`、api_key、secret 皆 0 筆；工作報告中的相關字樣僅為說明文字 |

## 3. P3 三項備註的修正，逐項檢視

### 3.1 Provider 未知例外 — 已修正
`generate_structured` 呼叫邊界新增內層 `try`：`AIProviderError`／`TimeoutError` 原樣上拋，其他 `Exception` 轉為 `AIProviderError`，只記錄「例外類別＋(檔名,行號,函式名)」，不記錄訊息、原始碼行或區域變數；`from None` 切斷例外鏈。新測試用含 `PRIVATE financial text secret API key` 的 `RuntimeError` 驗證：回應與 log 都不含該字串，且之後手動契約 1.0 仍可呼叫推薦 API。另一個測試確認邊界**外**的程式錯誤（如 `_key()` 的 `RuntimeError`）不被吞掉。`CancelledError` 屬 `BaseException`，不會被誤捕。符合報告。

### 3.2 `user_confirmed_ai` 來源 — 已修正（我另做了前端對後端的實測）
`validate_confirmed_ai` 現在要求：每個標為 `user_confirmed_ai` 的欄位必須在六個白名單內，且對應「已接受」候選；接受「加入／排除車型」時，只有相反欄位在**原 context 確實存在該值**才可連帶標記。
- 單元測試：`salary`／`budget_max`／`balance`／`receipt`、以及未被接受的 `ownership_years`／`priorities` 冒充皆 `ValidationError`；部分接受、連帶移除、偽造 `purposes` 皆符合預期。
- **前端對後端實測（避免新規則誤擋正常流程）**：在瀏覽器以假 Provider 走「接受全部 3 項候選（排除 SUV＋接送長輩＋移除乘坐舒適）」，問卷原選了 SUV 與乘坐舒適。產出契約 `1.1`，`field_sources` 的 AI 標記為 `purposes`、`priorities`、`body_types`、`avoid_body_types`（後兩者正是連帶移除的對）；送出推薦成功（3 款可排名、4 款不符合條件）。「五年後我要出國」同次被保守規則轉為待確認，未成為年限候選。無誤擋。
- 與舊契約相容：未強制 1.0 手動需求補來源資料。

### 3.3 簽章設定 — 已修正
`startup_warnings()` 新增：未設定 → 警告將使用強隨機程序金鑰並說明跨 worker／重啟失效；少於 32 UTF-8 bytes → 警告「將拒絕運作、不退回弱金鑰」。測試涵蓋空字串、`short`、32 個 ASCII、11 個中文字（33 bytes），且警告文字不含金鑰。另有兩個獨立 Python 程序以同一固定金鑰簽署／驗證 receipt 的測試。符合報告。（小提醒：未設定金鑰時每次啟動都會出現這則警告，開發環境會有些吵，但屬刻意設計。）

## 4. 真實 Gemini 28 案例：逐筆結果檢視（只分析已提交檔案，未重打 API）

| 檢查 | 結果 |
|---|---|
| 計數一致 | 28 筆：10 筆與標註一致、1 筆「無法確認」、17 筆逾時；報告與 JSON 完全吻合 |
| 延遲統計 | 平均 16.904 秒、最大 20.019 秒，與 JSON 重算相同 |
| 費用估算 | 11 筆有 usage：輸入 7,669、輸出 537 tokens；(7669×0.30＋537×2.50)／10⁶ ＝ **US$0.0036432**，與報告相同；報告也已註明這不是實付金額、逾時請求可能仍計費 |
| 輸出品質（僅收到回應的 11 筆） | 格式失敗 0、證據失敗 0、衝突標示失敗 0、誤判／漏判 0；p3-26 為 `uncertain` 對 `missing_information` 的分類差異（兩者都不套用候選） |

我另從逐筆資料看到報告沒有特別強調的現象：
- **逾時不是均勻分布**：前 4 筆、p3-06～p3-08 等連續逾時；而 p3-23～p3-25 三筆只花 1.9～2.4 秒。**成功的呼叫也常貼近上限**（18.6、18.8、17.1、15.2、19.5 秒）。代表 20 秒預算只是勉強，波動大，不是單純「少數失敗」。
- 20 秒是擷取服務的 deadline；前端另有 25 秒中止。若正式環境延遲與本機相似，大多數使用者會看到「分析逾時」而走降級流程——降級本身是正常的（我在 P3 審查已驗證），但「AI 為主要體驗」目前不成立。
- 證據只有一輪、一個時段、單一環境，報告自己也這麼寫；我同意不能斷言成因，也同意「先固定模型版本再評估逾時策略」的順序。

## 5. 桌面整合

- 兩頁新增並列導航：「幫我選車／直接購車試算」，各自以 `aria-current="page"` 標示目前頁；連結目標正確（`/car-needs.html`、`/vehicle.html`）。我在 `car-needs.html`、`vehicle.html` 實際載入，導航內容、目前頁標示、連結皆符合，Console 無錯誤。
- 失效候選時也會隱藏「略過這次 AI 分析」按鈕（`car-needs.js` 修正）。
- 我**未重做**報告中的 Chrome 桌面完整流程（真實 AI 成功／逾時降級、財務分析、單車、雙車比較）；以上 P3 審查與本次的假 Provider 流程涵蓋同一程式路徑，但「報告所述的真實 Gemini 接受轎車候選」與 viewport 1745px 的版面／無橫向溢位我無法獨立證實（我的內建瀏覽器窗格未顯示，無法量測版面）。

## 6. 發現

無新增缺陷。僅有三點提醒（非阻擋）：
1. **「只考慮轎車」目前映射為偏好車型而非硬性排除**：報告已揭露。使用者可能預期是限制條件，建議 UI 文案或候選標籤註明「偏好，非排除」。
2. **評估腳本限制**：`scripts/evaluate_car_needs_live.py` 只有明確 `--live` 才打 API，預設測試不會呼叫；分類以 field／operation／value 嚴格比對，證據長度不同不算錯，合理。評估資料僅單一固定 context（偏好 SUV、舒適…），未涵蓋空白 context。
3. 歷史提交已含真實評估原始輸出（合成案例文字，無使用者資料），可接受。

## 7. 未驗證項目

- 真實 Gemini 的語意品質（11／28 有回應、其餘逾時）；逾時案例無任何語意證據，依報告所述，兩個關鍵案例（混合否定句「不喜歡休旅車但是常載長輩」、「後座舒服不重要」）本輪也未得到結果。
- 逾時成因（網路、時段、模型負載或 `latest` alias 變更為 3.5 Flash-Lite 後的行為）。
- OpenAI 結構化輸出（混合字串／整數 enum）相容性。
- 多 worker 實際部署與 Render 環境設定（報告說明尚未讀取）。
- 桌面真實流程與版面；Playwright 腳本。

## 8. 建議下一步

1. 在決定任何對外宣稱前，先**固定 Gemini 模型版本**（不要用 `latest` alias），在相同 20／25 秒預算下重跑 28 筆並多輪、分時段取樣，再決定是否調整 deadline 或改成非同步／背景分析。
2. 在 UI 保持「AI 為選用、可略過」；逾時文案已存在，建議量測正式環境降級比例。
3. 正式環境務必設定獨立 `CAR_NEEDS_SIGNING_KEY`（≥32 bytes），並確認 worker 數量。
4. OpenAI 在完成真實驗證前不要列為支援的 Provider。
5. 兩個 commit 尚未推送；是否推送由你決定。
