# P4 測試版與 Gemini 逾時調查

## 已確認證據

- 基準：`6411888`，已包含 P3 `9837f32`；與 `origin/main` 相比原先僅多這兩個已審查提交。
- 既有 `.env` 選 `gemini-flash-lite-latest`；舊批次實際回應 `gemini-3.5-flash-lite`。
- 舊輪 28 筆：11 收到回應（39.29%），17 逾時（60.71%）；10 符合完整標註、1 unclear 分類不同。
- 整體耗時平均 16.904 秒、P95 20.017 秒；被取消案例是截斷觀察，不代表模型完整耗時。
- HTTP timeout=30 秒（httpx 為各階段閒置 timeout，不是整體總預算）；P3 `asyncio.wait_for`=20 秒，前端 AbortController=25 秒。
- Provider 原先最多 2 次 retry（共 3 attempts），沒有 backoff，連 400／401 等非暫時錯誤也可能重送。
- 對一直沒回應的初次請求，20 秒 deadline 會比 HTTP 30 秒先取消；不能把 17 筆逾時直接歸因於 retry。
- 舊批次只保存已回應的 HTTP 狀態，沒有 request hook；17 筆無法精確回溯是否曾送出多個實體請求。
- 舊輪 p3-23～25 僅 1.887／2.436／1.913 秒，而其他成功案例常 15～19 秒。可確認波動，不能證明時段／網路／模型負載何者是主因。
- 非串流 REST 沒有純模型生成時間；整體耗時含網路、排隊、生成、讀取及驗證，不能假稱已測出純推論時間。

## 本輪程式改善

1. 預設固定 `gemini-3.5-flash-lite`；既有 `gemini-flash-lite-latest` 相容解析為相同固定版，不改寫 `.env` 或正式憑證。
2. 明確指定其他固定模型仍保留；其他浮動 alias 顯示啟動警告。
3. Provider 僅對傳輸錯誤、429、5xx 重試；400／401／403 立即失敗，避免無效重送。
4. 暫時錯誤使用 .25／.5 秒有界 backoff，仍受原 20 秒 P3 deadline 控制；沒有放大 timeout。
5. 去敏感化日誌新增 attempts 與 http_ms，不記錄需求或 Key。
6. 評估版 v2 每筆只送一次、固定模型、最多 1,024 輸出 tokens；記錄 request 開始、headers 到達與 body 讀取時間。
7. 保留舊評估檔，不允許新 live run 覆蓋既有檔名；預設測試不打模型。

## 預先費用同意

本輪遵守「先估價、取得同意再付費」。使用者已明確同意兩輪共 56 筆、預算 US$0.17，取得回覆後才執行；瀏覽器降級測試使用 AI_ENABLED=false，不額外產生 Gemini 請求。

- 提案：分兩時段各 28 案，共 56 次實體請求；無自動 retry，原 20 秒 deadline，1,024 輸出 token 上限。
- 依舊輪每次約 697 輸入／49 輸出 tokens，56 次可觀測預估約 US$0.02。
- 若每次輸出接近上限，56 次 token 預算估約 US$0.17；單輪約 US$0.09。不是 Google 帳務硬上限，逾時仍可能計費，稅費與免費額度另計。
- [Google 官方價目](https://ai.google.dev/gemini-api/docs/pricing)，2026-10-28 核對 Standard：輸入 US$0.30/M、輸出（含思考）US$2.50/M。
- 若使用者只同意 28 次，只跑一次，不能聲稱已比較不同時段；兩輪同意後也不自行建立排程。

取得單輪同意後的命令：

```powershell
python -B scripts/evaluate_car_needs_live.py --live --model gemini-3.5-flash-lite --max-output-tokens 1024 --output docs/P4_GEMINI_FIXED_RUN1.json
```

第二時段用不同檔名 RUN2；需同一機器、Prompt hash、fixture hash、context、deadline、token cap 與單次請求設定。記錄本地時間與 UTC。

## 對照解讀與限制

- v2 相對舊輪除了固定 model，還將評估 retry 由 2 改 0，並加 1,024 輸出上限；不能將品質或延遲差異全歸因於模型固定。
- 兩個 v2 時段之間參數相同，可作時段對照；一個成功的單輪仍不能證明持續穩定。
- headers 到達時間仍含網路／排隊／生成，不代表模型純生成耗時；沒有串流首 token 指標。
- 兩輪固定模型已有新數據，仍各有 11／28 逾時，不能宣稱已修好；完整對照見本報告末段及發布報告。
- 保留 AI 可略過、後端 503 與前端 25 秒提示；不破壞手動推薦或財務計算。
- OpenAI 混合 enum Structured Outputs 仍未真實驗證，不列為已驗證正式 Provider。
- 建議僅作受控組員／口試測試環境，AI 必須為選用。正式金鑰、worker 及部署設定仍由維運者授權處理。

## 發布安全範圍

- 對將 Push 的 HEAD 可達歷史 426 個 blobs 掃描：目前已配置的 Provider／簽章秘密、Google／OpenAI Key 格式、PEM private key、歷史 `.env` 路徑，無命中。
- `.env` 為忽略檔，只有 `.env.example` 空白模板在版本庫。新文件只用已標示的合成測試數值；原個人／Claude 未追蹤文件不加入提交。
- 掃描是指定模式與已知秘密比對，不保證辨識所有私人資料或所有秘密格式；待 Push 的新提交也須再掃描。
- 分支 `test/p4-integration` 單獨 Push，不 force、不合併 main、不調整 Render 或憑證。
- 組員啟動與人工驗收：[P4_TEAM_TEST_GUIDE.md](P4_TEAM_TEST_GUIDE.md)。

## 第一輪實測

- 台北 2026-10-28 22:33:42～22:41:21；28 次實體 HTTP 請求，沒有 retry。
- 17／28 有可用結果（60.71%）；16 符合標註、1 誤判；11／28 逾時（39.29%）。
- 平均 15.396 秒、P95 20.025 秒；有效回應格式、原文證據、後端衝突檢查皆通過。
- 可觀測 token：11,848 輸入、774 輸出，估 US$0.0054894；逾時計費仍未知。
- p3-08「也許三年後換車」被產生 ownership_years=3，證據只截取「三年後換車」，另列「也許」為 uncertain。這是實際誤判，不能因數值與原問卷相同就算正確；人工確認僅避免自動套用，並未修復誤判。
- [逐筆結果](P4_GEMINI_FIXED_RUN1_2026-10-28.md)、[原始 JSON](P4_GEMINI_FIXED_RUN1_2026-10-28.json)。
- 兩輪執行期間不改 Prompt、Schema 或 Provider 程式，以免污染對照。兩輪起始至少相隔 15 分鐘，屬同一晚短時段比較，不代表尖峰／離峰。
- 第一輪部分時間重疊離線測試及桌面驗收，可能有本機負載干擾；不是嚴格受控實驗。

## 發布與非 AI 驗收

- 程式提交 `36bb928` 已推送至 `origin/test/p4-integration`，包含已審查 P3／P4 提交。沒有 force push、合併 main 或改動 Render 設定。
- 新增 deadline 取消不重送的回歸測試後，Python 500 passed、Node 154 passed；預設測試不使用真實模型。
- Chrome Desktop 使用本機 AI_ENABLED=false：按 AI 分析得到安全 503 提示，補充文字保留；仍可確認需求並完成 6 款推薦，沒有把 Mock 標為真實 AI。
- URL／標題正確、頁面非空白、無框架錯誤頁、無 Console error、無水平溢位；截圖在本機 Temp 的 `finsim-p4-release-fallback-20261028.png`。
- 此輪只重測降級路徑；直接購車、雙車與財務整合由完整回歸測試覆蓋，並提供組員逐項人工驗收清單，不冒稱本輪重跑所有真實 AI 桌面情境。

## 第二輪與最終判斷

- 台北 2026-10-28 22:48:57～22:57:31；與第一輪起始相隔 15 分 15 秒，兩輪間隔約 7 分 36 秒。
- 同一固定模型、機器、context、Prompt hash、fixture hash、20 秒 deadline、零 retry、1,024 輸出上限；兩輪都記錄 28 次 HTTP 嘗試，合計 56 次，沒有額外付費診斷或第三輪。
- 第二輪：15 符合標註、2 unclear 分類不同、11 逾時；17／28 可用回應（60.71%），逾時率 39.29%。
- 平均 17.360 秒、P95 20.019 秒，並未比第一輪更快。
- 第一輪 p3-08 誤判，第二輪改為正確；第二輪 p3-06 回 unsupported 而非 uncertain，p3-13 多列 uncertain，皆未新增候選但列為無法確認。格式有效不代表語意一定正確。
- 第二輪觀測費用 US$0.0058431；兩輪可觀測合計 US$0.0113325，22 次逾時的費用未知。依核准的單次 token 上限與這組輸入保守預留約 US$0.168，非帳務硬上限；實際須核對 Google 帳單。
- 相較舊輪 60.71% 逾時，兩個新輪都是 39.29%，但 retry／token cap／時段與負載條件不同，無法把差異完全歸因於固定模型。
- 成功案例的大部分等待發生在 response headers 之前；非串流資料不足以拆分網路、排隊及純模型生成，根因仍未確定。
- **CONDITIONAL GO**：可作組員與口試的受控測試環境，AI 必須為選用；不合併 main、不自動部署，也不宣稱正式 AI 穩定性通過。
- [第二輪逐筆報告](P4_GEMINI_FIXED_RUN2_2026-10-28.md)、[第二輪 JSON](P4_GEMINI_FIXED_RUN2_2026-10-28.json)、[完整發布報告](P4_TEST_RELEASE_REPORT_2026-10-28.md)。
