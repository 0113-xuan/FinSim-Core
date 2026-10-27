# P3 收尾與 P4 桌面整合驗收報告

## 結論

**CONDITIONAL GO**：P3 三項安全修正與桌面整合完成；核心推薦、單車及雙車功能正常。
但目前 Gemini latest alias 在 20 秒限制下，28 筆真實呼叫有 17 筆逾時，不能宣稱 AI 品質或穩定性全面通過，也不建議把 AI 設成必經流程。

- 基準 HEAD：`9837f322674e371f6d4b8b17c40a4877dae258e9`。
- 保留所有原有未追蹤文件，包含 Claude P3 審查報告；不納入本次提交。
- 不修改財務公式、推薦演算法、車款資料或正式環境設定；不新增手機功能。

## 三項修正

### Provider 例外

- 只在 `generate_structured` 呼叫邊界攔截未知例外，轉為既有 503 中文降級回應。
- 日誌保留例外類別與 traceback 的檔名／行號／函式名稱，不記錄例外訊息、source line、locals、完整需求、API Key 或簽章金鑰。
- Prompt Loader／後處理等呼叫邊界外的未知程式錯誤不被新保護吞掉；另有 RuntimeError 測試驗證。
- 測試確認 Provider RuntimeError 後仍可送手動契約 1.0 至原推薦 API。

### AI 來源

- `user_confirmed_ai` 僅能標記六個白名單欄位，且該欄位確實對應已接受候選。
- 接受排除車型會連帶移除相反偏好時，相反欄位可標 AI 來源；僅在原 context 確實存在該值時允許。
- 拒絕候選、財務欄位、任意欄位不能冒充 AI 來源。
- 不強制舊契約補上新的來源資料；保留 1.0／1.1 相容性。
- 新增部分接受、偽造來源、連帶衝突移除測試。

### 簽章設定

- 啟動警告列出缺少固定金鑰及不足 32 UTF-8 bytes 的問題，但不輸出金鑰內容。
- 缺少設定仍使用強隨機程序金鑰，明確警告跨 worker／重啟失效；不是弱固定預設。
- 短金鑰繼續 fail closed，不自動退回任何較弱金鑰。
- 兩個獨立 Python 程序用相同測試固定金鑰產生／驗證 receipt 成功。

## 真實 Gemini 28 案例

- 可重跑程式：`scripts/evaluate_car_needs_live.py`；只有明確 `--live` 才呼叫模型。
- 輸入：既有 `tests/fixtures/car_needs_p3_cases.json`，28 筆合成標註資料。
- 使用設定：`gemini-flash-lite-latest`，實際回應版本 `gemini-3.5-flash-lite`。
- 沿用目前 20 秒服務 deadline、Provider 設定及 Schema，不為取得好成績偷偷放寬逾時或換模型。
- 輸出保存逐筆預期、原始已驗證模型輸出、安全後處理結果、誤判／漏判、證據、衝突、usage、延遲與模型版本；不保存 receipt 或金鑰。
- [逐筆 Markdown](P4_GEMINI_LIVE_2026-10-27.md)、[完整 JSON](P4_GEMINI_LIVE_2026-10-27.json)。

| 結果 | 數量 |
|---|---:|
| 與完整標註一致 | 10 |
| 額外／錯誤候選 | 0（限收到回應者） |
| 漏掉候選 | 0（限收到回應者） |
| 無法確認／分類不一致 | 1 |
| 服務逾時，無可用輸出 | 17 |

- 11 筆收到回應：格式驗證失敗 0、證據失敗 0、衝突檢查失敗 0。逾時的 17 筆不能評估語意或格式。
- p3-26「還不確定要什麼」：標註 `missing_information`，模型回 `uncertain`；兩者都沒有套用候選，但嚴格比對列為無法確認。
- 本輪原始模型分類與安全後處理分類相同；不能把 Mock 通過率或後端保護誤稱為模型準確率。
- 「不喜歡休旅車但是常載長輩」「後座舒服不重要」本輪批次皆逾時，不能沿用上一輪結果宣稱本輪已重新驗證其模型語意。
- 批次為擷取服務層測試：含 Gemini 網路呼叫與後端驗證，不含瀏覽器及 FinSim HTTP 外層開銷。
- 本輪只有一輪樣本，存在網路、時段、模型負載等混雜因素；不能斷定逾時都是某一因素造成。

## 延遲與費用

- 28 筆含逾時平均 16.904 秒，P95 20.017 秒，最高 20.019 秒；逾時結果被 20 秒截斷，不能用來估計模型完整耗時。
- 額外最小診斷請求成功：28.47 秒、HTTP 200、同為 Gemini 3.5 Flash-Lite，表示金鑰及 API 可用，但不能據此保證正常提取都能準時完成。
- 11 筆有 usage 的呼叫：輸入 7,669 tokens、輸出 537 tokens，按官方 Standard 費率推算約 **US$0.0036432**，每筆可觀測回應平均約 US$0.0003312。
- [Google 官方價格](https://ai.google.dev/gemini-api/docs/pricing)：Gemini 3.5 Flash-Lite 輸入 US$0.30／百萬 tokens、輸出含思考 US$2.50／百萬 tokens；查詢 2026-10-27。
- 這不是 28 筆的總實付金額：17 筆取消／逾時可能仍計費；免費額度、稅費、診斷與桌面重試須查 Google 帳務，未收到 usage 不能視為零費用。
- 未使用搜尋、RAG 或外部工具計費功能。

## 桌面實際驗收

Chrome，viewport 1745px，本機 `http://127.0.0.1:8017/vehicle.html`。

| 流程 | 結果／證據 |
|---|---|
| 頂部雙模式 | 兩頁新增「幫我選車／直接購車試算」導航，標示目前頁面；沿用既有頁面 |
| 三步問卷與財務資料 | 預算 150 萬、1,000km／月、3 人、持有 5 年、現金付款；收入 8 萬、存款 120 萬、固定 1.2 萬、變動 1 萬、還款 0 |
| 真實 AI 失敗降級 | 混合否定句真實呼叫逾時，輸入保留、按鈕恢復，可確認並完成非 AI 財務推薦 |
| 真實 AI 完整流程 | 重試「我只考慮轎車」成功，顯示原文與轎車偏好候選；使用者接受後再次確認，契約 1.1 成功進入推薦 |
| 五年財務分析 | 6 款可排名，顯示每月支出、五年現金支出、最低現金、預備金及限制結果 |
| 來源標記 | body_types 為 user_confirmed_ai；財務欄位仍為 user_provided |
| 返回修改與候選失效 | 預算改 200 萬、住家充電改有；舊候選清空，body_types 轉手動來源，重新確認輸出 1.0 |
| 不完整車款 | 重算顯示 6 款可排名、1 款資料不足，純電不因未知成本變成 0 而進排名 |
| 直接單車計算 | Corolla Cross 汽油豪華、現金付款，產生單車成本結果（每月養車約 NT$8,800） |
| 原雙車財務比較 | Corolla Cross 汽油／油電豪華，同一財務資料與現金付款，產生兩車每月結餘、最低及五年末存款 |
| Console／版面 | 無 error；只有 MetaMask 擴充套件 warnings。scrollWidth 1732 < viewport 1745，無橫向溢位 |

- 「只考慮轎車」目前映射既有 body_types **偏好**，不是新的硬性排除規則；沒有擴充推薦演算法。
- 畫面截圖保存在本機 Temp：`finsim-p4-financial.png`；非專案程式依賴。
- 逐項拒絕、部分接受及衝突取代另有自動化／既有 P3 驗收覆蓋；本輪成功的真實桌面案例為接受一個候選，未宣稱所有語意都已桌面重測。
- 未進行手機驗收或手機專屬優化。

## 測試

- Python 完整回歸：**492 passed**；兩個既有 JWT 測試用短金鑰警告。
- Node 完整回歸：**154 passed**。
- 新測試包含 Provider 未知例外與安全日誌、手動 fallback、保留程式錯誤、AI 來源偽造與部分接受、金鑰警告／弱金鑰拒絕、獨立 worker、評估分類及雙模式導航。
- 真實評估不在預設測試內；沒有 API Key 仍可跑完整單元／整合測試。

## 正式環境注意事項

1. 後端設定 `AI_PROVIDER=gemini`、`GEMINI_API_KEY`、`AI_ENABLED=true`；明確 `AI_ENABLED=false` 可停用 AI，保留手動流程。
2. 所有 worker 共用獨立隨機的 `CAR_NEEDS_SIGNING_KEY`（至少 32 bytes），不與 JWT Key 共用；金鑰輪替會使舊 receipt 失效。
3. 未設定固定金鑰時，重啟／切換 worker 會要求重新分析；固定金鑰只保障有效期內 receipt 可跨程序驗證，不延長 30 分鐘期限。
4. 前端靜態檔掃描未發現目前 Provider 或簽章金鑰；`.env` 不提交。
5. 尚未改動或讀取 Render 正式環境憑證；正式金鑰是否配置、worker 數量、正式網路延遲仍待維運者確認。
6. 本機 alias 實際模型為 3.5，不能假定 latest 永遠是 2.5。正式模型應固定版本，再依實際預算驗證延遲與品質。
7. 不建議直接放寬整個舊 onboarding 的逾時，應另審查 P3 服務與前端 deadline 的搭配，並保留降級功能。
8. OpenAI 未真實驗證混合 enum Structured Outputs 相容性，不列正式已驗證 Provider。

## 修改檔案與後續

- `app/services/car_needs_extraction.py`、`app/config.py`、`.env.example`。
- `static/vehicle.html`、`static/car-needs.html`、`static/style.css`、`static/car-needs.js`。
- `tests/test_car_needs_ai.py`、`tests/test_car_needs_evaluation.py`、`tests/test_car_needs_integration.py`。
- `scripts/evaluate_car_needs_live.py`、本報告與兩份真實評估輸出。
- 下一個審查重點：先處理或接受 17／28 的 deadline 失敗，再討論固定模型與逾時策略；不可直接標示正式 AI 已穩定上線。
- 本輪提交後停止，不 Push、不部署、不自行進入後續功能開發。
