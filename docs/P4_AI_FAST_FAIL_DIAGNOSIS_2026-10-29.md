# P4 AI extract 快速 503 調查

## 結論

本次可重現的快速 503 是**本機程序環境與重複服務問題**，不是已確認的 Gemini 逾時、金鑰失效或模型故障。
沒有修改財務引擎、問卷、推薦演算法、AI Provider、API 契約或 `.env`；沒有 Commit、Push 或部署。

## 根因證據

調查前同一個 8000 埠同時存在兩個不同綁定位址的 FinSim 程序：

| 程序 | 綁定 | 工作目錄 | 啟動環境 AI_ENABLED |
|---|---|---|---|
| PID 2644 | 127.0.0.1:8000 | 主專案 | false |
| PID 28920 | 0.0.0.0:8000 | 主專案 | true |

- 使用安全過濾的程序環境讀取確認上述狀態，只輸出布林、Provider 與模型名稱，不輸出任何 key。
- `.env` 存在且 `AI_ENABLED=true`、`AI_PROVIDER=gemini`、Gemini key 存在；這些是設定狀態，不等於外部供應商已接受金鑰。
- 調查前 `GET http://127.0.0.1:8000/api` 與 `GET http://localhost:8000/api` 均回 `ai_enabled=false`，顯示實際連到 AI 關閉的服務。
- 對該服務送出一筆合成文字與最小有效 context，重現 HTTP 503，耗時約 **15.19 ms**。時間與使用者 3–4ms 不必完全一致，但同樣是前置快速失敗，而非等待 20 秒。
- 舊 10/27、10/28 日誌有 extract 200/503 紀錄，但沒有對應本次兩個 PID；不能用舊日誌聲稱本次 Gemini 已被呼叫。沒有取得本次八筆逐筆外部 HTTP 日誌。

## 程式路徑

1. `app/config.py:11`：以專案根目錄 `.env` 執行 `load_dotenv(..., override=False)`。
2. `app/config.py:56`：環境變數 `AI_ENABLED` 非空時，只有字串 `true` 才啟用；未設定才依所選 Provider 的 key 推導。
3. 因 `override=False`，既有程序的 `AI_ENABLED=false` 優先於 `.env` 的 true。Settings 在 import 時建立，編輯 `.env` 不會即時更新已啟動程序。
4. `app/services/ai_provider.py:137`：AI 關閉時 `get_ai_provider()` 直接回 `None`。
5. `main.py:122`：實際路由是 `POST /ai/car-needs/extract`，不是單獨 `/extract`。
6. `app/services/car_needs_extraction.py:88`：Provider 為 None 或名稱不支援時，立即拋 `AIProviderError`。此檢查在 prompt 與 provider 呼叫之前，也在該函式的計時 finally 之前。
7. `main.py:128`：將服務層 `AIProviderError` 轉成安全、通用的 503。

因此，**本次重現沒有送出 Gemini／OpenAI HTTP 請求**。若使用者八筆均命中同一個 AI 關閉程序，也會走同一條不連外路徑；沒有把這項推論冒充逐筆封包觀測。

## 已排除與其他 503 分支

- Provider 選擇為 Gemini；Gemini 讀 `GEMINI_API_KEY`，OpenAI 讀 `AI_API_KEY`，不能混用環境變數名稱。
- `.env` 尚使用舊 `gemini-flash-lite-latest`，現有設定程式會解析為固定 `gemini-3.5-flash-lite`；本機初始化成功，沒有為此改 `.env`。這不代表本輪已向 Google 驗證可用性。
- Prompt `car_needs_extraction.md` 可載入。
- 未設固定 `CAR_NEEDS_SIGNING_KEY`，現行單程序使用強隨機程序金鑰，可執行；重啟後舊候選會失效，多 worker 需固定強金鑰。此缺省不是本次 503 原因。
- 簽章金鑰若非空但不足 32 bytes，會在結果簽章時失敗；不是本次目前的狀態。
- Gemini key 缺失在 `_headers()` 前置檢查失敗，不會送出外部請求。
- 空模型、Provider HTTP 錯誤、無效 JSON／Schema、原文證據不符、候選衝突、短簽章金鑰、20 秒外層 deadline 均可能導致服務層失敗並呈現同一類 503；不能單看狀態碼判原因。
- Provider.generate_structured 的未知例外會去敏感記錄例外類別與堆疊位置，再安全降級；不記完整需求或秘密。
- 請求 Schema 驗證失敗為 422；限流是 429，不是此次 503 分支。

## 本輪修正與現況

已停止 PID 2644 的 AI 關閉重複服務，保留 PID 28920 已啟用 AI 的原服務。

- 現在只有 `0.0.0.0:8000 / PID 28920` 監聽 8000。
- `127.0.0.1:8000/api` 與 `localhost:8000/api` 均回 `ai_enabled=true`。
- 真實本機推薦 API（不使用 AI）HTTP 200，得到 3 款排名結果。
- 獨立進度儀表板仍是另一專案、8019 埠，沒有重新混入 FinSim。
- 沒有發送真實 Gemini 或 OpenAI 模型請求；沒有使用新的付費模型預算。

## 安全診斷指令

```powershell
cd D:\project\FinSim-Core
D:\DingFeng_Agent\Python312\python.exe -B -m scripts.diagnose_car_needs_ai
```

輸出只包含狀態布林、Provider、模型與錯誤類別，不列 key、簽章內容、全文需求或資料庫資料。
診斷可初始化 Provider、載入 prompt，但**不呼叫 generate_structured、不連外**。
`configuration_ready=true` 不等於 API key 有效、配額足夠或模型延遲合格。
這是新診斷程序，不能代替查詢正在服務的程序；其中 process_ai_enabled_present 指目前載入 `.env` 後的 Python 環境，不足以單獨證明父程序設定來源。本次另以實際服務狀態與程序環境確認根因。

當前安全診斷結果：AI 啟用、Gemini 支援、固定模型已解析、key 存在、Provider 初始化成功、prompt 載入成功、無初始化錯誤、未嘗試外部 HTTP。

本次為讀取活動程序狀態，僅在系統暫存目錄安裝 psutil；它不是專案依賴，也未加入 requirements 或 Git。日常診斷指令不需要 psutil。

## 正確本機設定與重啟

保持 `.env` 中已有的秘密，不要貼到終端輸出或報告。
必要設定名稱：`AI_ENABLED=true`、`AI_PROVIDER=gemini`、`GEMINI_API_KEY` 存於後端、`GEMINI_MODEL=gemini-3.5-flash-lite`。

先用 Ctrl+C 停止既有服務；若是背景程序，先核對 PID、啟動命令與工作目錄，再停止指定程序。不要批次停止所有 Python。
確認 8000 沒有重複服務後，在專案目錄啟動一次：

```powershell
cd D:\project\FinSim-Core
$env:AI_ENABLED = 'true'
$env:AI_PROVIDER = 'gemini'
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
D:\DingFeng_Agent\Python312\python.exe -B -m uvicorn main:app --host 127.0.0.1 --port 8000
```

不必在指令列重貼 GEMINI_API_KEY；現有 `.env` 可提供。也不要同時再跑 `python main.py`。
另一個終端執行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api | Select-Object ai_enabled
```

重啟後重新分析並確認需求，不要沿用舊程序簽出的候選。

## 回歸結果與明確限制

- **Python 507 passed**：原有 500 項＋7 項診斷／快速失敗測試；另有兩則既有 JWT 測試金鑰長度警告。
- **Node 154 passed**；沒有修改前端。
- AI Disabled：API 503，無外部 async HTTP。
- Key 缺失：API 503，無外部 async HTTP。
- Provider 初始化失敗：安全診斷回 `provider_initialization_failed` 與 `ValueError` 類別，不輸出例外內容。
- **另確認既有缺口**：若依賴注入階段的 Provider factory 直接拋例外，發生在路由的 try 之前，目前 API 是通用 **500**，不是 503。已用故障注入測試記錄。這不等於初始化失敗已能正確降級，亦非本次真實 503 根因。依本輪「環境問題不改核心」限制，未修改 main.py 或 Provider。可另開小修將已知配置初始化例外轉為受控降級。
- 正常假 Provider：候選 API 200 → 使用者確認 → 推薦 API 200；不以 Mock 通過率宣稱真實 AI 準確率。
- Provider 執行錯誤：API 503、不洩漏錯誤內容；仍可略過 AI，推薦 200。
- 所有新增回歸封鎖 async 外部 HTTP，不需要真實 key。

## 修改檔案

1. `scripts/diagnose_car_needs_ai.py`：離線、安全狀態診斷。
2. `tests/test_ai_fast_fail_diagnostics.py`：7 項測試，包含初始化例外既有 500 邊界的明確記錄。
3. 本文件。

沒有修改 `.env`、main.py、設定優先順序、Provider、問卷、推薦或任何財務公式。保留既有未追蹤文件。

## 是否能開始八筆真實語意測試

**本機設定與快速 503 阻礙已排除，可進入真實測試準備。**
尚未證明新八筆可成功：金鑰／模型遠端接受度、配額及原有 20 秒逾時問題，仍須實際模型觀測。
本輪未收到新的付費呼叫授權，因此不自行執行八筆。先前 56 筆授權已用完，不沿用。
若由代理執行，建議先提案八次單一嘗試、零 retry、20 秒 deadline、每筆最多 1,024 輸出 tokens；依 10/28 已核對費率與每筆約 800 輸入 tokens 保守預留約 US$0.03，須取得本輪同意並核對實際請求 token 預算後才執行。這不是供應商帳單硬上限，逾時也可能計費。
