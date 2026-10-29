# P4 組員桌面測試版

## 版本與定位

- 分支：`test/p4-integration`，不是 `main`；僅供口試前組員測試。
- 包含已審查的 `9837f32`（P3）、`6411888`（P4），以及本輪模型固定／診斷改善。
- 不需要登入。AI 為選用；先用非 AI 模式測通核心功能。
- 請使用下方合成案例，不要輸入自己的真實財務或個資。
- 原始批次 28 筆有 17 筆逾時；本輪固定模型的兩批各 28 筆仍各有 11 筆逾時，尚不能宣稱 AI 穩定性通過。詳見 [測試發布報告](P4_TEST_RELEASE_REPORT_2026-10-28.md)。

### 2026-10-29 討論測試版更新

- 新增安全離線診斷：`python -B -m scripts.diagnose_car_needs_ai`；只回報設定狀態與錯誤類別，不連外、不驗證真實模型品質。
- 修復本機快速 503 的方法是停止帶有 `AI_ENABLED=false` 的重複服務，並非修改財務／AI 核心程式。每台電腦只啟動一個 8000 服務。
- 程式完整回歸：Python **507 passed**、Node **154 passed**；新增測試使用假 Provider，不需要真實 API Key。
- 已知限制仍保留：真實 Gemini 可能逾時；Provider 在依賴初始化階段直接拋例外時仍可能回 500，執行階段失敗則回受控 503。可以略過 AI 繼續推薦，不代表所有 AI 問題已修正。
- 進度儀表板已拆成獨立專案，不包含在此 Repository 或測試服務。

## 首次啟動（Windows PowerShell）

需要 Git、Python 3.12、Node.js 18 以上（Node 供測試使用）。

```powershell
git clone --branch test/p4-integration --single-branch https://github.com/0113-xuan/FinSim-Core.git FinSim-P4-test
cd FinSim-P4-test
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:AI_ENABLED = 'false'
$env:CAR_NEEDS_SIGNING_KEY = & .\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:JWT_SECRET = & .\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
& .\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- 開啟 `http://127.0.0.1:8000/vehicle.html`，問卷為 `/car-needs.html`；不要用 `file:///...`。
- 若 8000 被占用，改成 8018 並開啟對應網址。不需要停止其他人的程式。
- Ctrl+C 停止。上述金鑰只存在此 shell，不寫入 Git；新 shell／新金鑰會使舊 AI 候選失效。
- `.env.example` 的 JWT 值只是公開範例，不可當實際祕密沿用；每位測試者使用上方隨機值。不需共享金鑰或帳號。
- 更新時在此分支執行 `git pull --ff-only`；若有本機修改先保存，不用 reset 或 force push。

## 測試 AI（選用，需自己的 API 額度）

1. 在本機編輯被 Git 忽略的 `.env`：`AI_PROVIDER=gemini`、`GEMINI_MODEL=gemini-3.5-flash-lite`、`GEMINI_API_KEY`。
2. 啟動前在 shell 設 `$env:AI_ENABLED = 'true'`，再重啟 uvicorn。環境變數優先於 `.env`。
3. `gemini-flash-lite-latest` 舊設定在此分支會解析為固定的 3.5 版本；不改寫 `.env`。
4. 不把 Key 放前端、截圖、聊天、Bug 單或 Git。不要在 `.env.example` 填真實值。
5. `AI_ENABLED=false` 可隨時停用，不影響手動推薦與財務引擎。
6. 一般 UI 點擊也會使用 AI 額度。28 筆批次評估必須另獲費用同意，勿全組各自反覆執行。
7. 若 AI 分析幾毫秒就回 503，先看 `/api` 的 `ai_enabled`，再執行離線診斷。注意：診斷是新程序，不能取代檢查正在服務的程序；`.env` 變更要重啟才生效。勿同時執行 `python main.py` 與 uvicorn 競用同一個埠。

## 合成測試資料

| 欄位 | 數值 |
|---|---:|
| 車價預算 | 1,500,000 |
| 每月里程 | 1,000 km |
| 乘車人數（含駕駛） | 3 |
| 持有年限 | 5 年 |
| 月收入 | 80,000 |
| 現金存款 | 1,200,000 |
| 固定／變動支出 | 12,000／10,000 |
| 每月既有還款 | 0 |
| 付款 | 現金；貸款附加測試用頭期 200,000、利率 2.5%、84 期 |
| 停車 | 自有，預算明確填 0 |

## 桌面人工驗收清單

每筆記錄日期時間、commit（`git rev-parse --short HEAD`）、瀏覽器版本、實際結果、截圖及通過／失敗。不記錄 Key 或完整真實需求。

### A. 直接購車

- [ ] `/vehicle.html` 頂部「直接購車試算」是目前模式。
- [ ] 選 Corolla Cross 汽油豪華，按「帶入車價與油費」，選現金付款，勾確認，計算單車成本。
- [ ] 不提供財務資料仍有養車成本；月養車不等於含車貸的總現金負擔。
- [ ] 改貸款條件重新計算，月貸款、全期利息與付款口徑可見。
- [ ] 自訂車款仍能輸入，不需要 AI。

### B. 三步問卷與推薦

- [ ] 點頂部「幫我選車」，輸入合成預算、里程與通勤用途。
- [ ] 第二步輸入人數、年限、付款及合成財務資料；住家充電選有，以便看到純電資料不足狀態。
- [ ] 上一步／下一步保留答案；貸款未填完整不能通過。
- [ ] 第三步直接略過 AI，檢查需求、勾最終確認、查看符合車款。
- [ ] 按五年車輛現金支出遞增排序；個人負擔不是排名分數，也不代表一定買得起。
- [ ] 有五年末現金、最低現金、預備金及限制狀態；不完整純電車款不以零成本排名。
- [ ] 回去把預算改 100,000，重新確認與計算，應沒有可完整排名的車款且有原因。

### C. 真實 AI（另有 API 額度時）

- [ ] 啟用 Gemini，輸入「不喜歡休旅車但是常載長輩，後座舒服不重要」。
- [ ] 看見原文證據及候選；不應把否定舒適解析成新增舒適偏好。
- [ ] 有未處理候選時不能最終確認；逐項接受或拒絕後才進推薦。
- [ ] 第二步先偏好 SUV，再輸入排除 SUV，需明確接受取代衝突答案。
- [ ] 修改問卷後舊候選失效；重新確認仍能手動推薦。
- [ ] 「五年後出國」不能直接成為持有五年；注入價格修改指令不能改車價。
- [ ] 「偏好轎車」不是硬性排除其他車型；只有明確排除條件才影響硬篩選。
- [ ] 收合的「本機規則示範」標示非 AI，不可把它當 Gemini 測試成功。

### D. AI 失敗降級

- [ ] 用新的瀏覽器分頁，停止伺服器，設 `$env:AI_ENABLED='false'` 後重啟；不用故意填錯 Key。
- [ ] 同樣填完問卷，按 AI 分析會有未完成提示，文字不清除。
- [ ] 不必一直重試 AI，可直接檢查需求、確認並完成推薦與財務分析。
- [ ] 真實逾時若發生，約 20 秒後後端失敗、前端最多 25 秒中止；按鈕恢復且答案保留。

### E. 雙車財務與導航

- [ ] 切「直接購車試算 → 雙車比較」，輸入共同合成財務資料。
- [ ] 選 Corolla Cross 汽油豪華／HYBRID 豪華，兩車都選現金，確認後比較。
- [ ] 顯示兩車每月結餘、五年現金與財務門檻；兩方案共用起始條件。
- [ ] 頂部兩模式互相可達；跨頁不保證保存未確認問卷，不應誤認成帳號雲端保存。
- [ ] 桌面無橫向溢位、Console 無網站錯誤。MetaMask 等擴充套件警告另列，不混為網站錯誤。

## 自動化測試

```powershell
& .\venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q
node --test tests/*.js
```

不需要真實 API Key，不會自動跑付費評估。完整測試需先安裝 requirements。

## Bug 回報格式

```text
Commit／分支：
測試時間與瀏覽器：
模式（AI 開啟／關閉，模型名稱；不可附 Key）：
合成輸入與操作步驟：
預期／實際結果：
是否能略過 AI 繼續：
截圖、HTTP 狀態或 Console 錯誤（移除敏感資料）：
```

## 部署條件

可作為「AI 選用」的受控組員測試環境；尚不能宣稱 AI 穩定性通過。
正式測試環境需固定模型、共用 32 bytes 以上獨立簽章金鑰、限制測試者與 API 額度，並取得部署設定授權。此分支 Push 不等於已部署，也不會自動合併 main。

## 發布前檢查範圍與歷史提醒

2026-10-29 發布前檢查涵蓋所有本機 refs 可達 Git blob、待提交檔案、敏感檔名與目前後端秘密值的精確比對，搭配常見 key／私鑰格式掃描及人工判讀；不是完整滲透測試，也不保證偵測所有秘密格式或個資。

- 沒有納入 `.env`、實際 Gemini/OpenAI 金鑰、私鑰檔或本機簽章金鑰。既有未確認的規劃、審查文件與個人文件不加入此輪提交。
- 歷史舊 main.py 有一個 Supabase `anon` 類型公開用 JWT；目前 main.py 已移除。其類型不同於高權限 `service_role`，但資料保護仍取決於權限與 RLS。[官方金鑰說明](https://supabase.com/docs/guides/getting-started/api-keys)。本輪未連線查核資料庫權限、未輪替金鑰，也未改寫歷史，因此不能宣稱歷史完全沒有 credential。
- 本機 JWT 設定與 `.env.example` 公開範例相同；本次不更動本機或正式憑證，請依上方指令在測試 shell 產生獨立隨機值。
- 本次只發布組員討論測試分支，不修改 main、不執行部署、不跑付費模型評估。
