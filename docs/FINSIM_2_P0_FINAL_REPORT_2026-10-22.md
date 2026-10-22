# FinSim 2.0 P0 最終工作報告

日期：2026-10-22（Asia/Taipei）；基準 HEAD：`d3483f4`。

本機工作區驗收通過。財務公式、API 欄位及代表案例的完整 JSON 均未改變。未開發 AI 問卷或其他下一階段功能，未推送或部署。

## 修改與原因

| 檔案 | 本輪修改 |
|---|---|
| `static/vehicle.js` | 壓力摘要以後端 `s.passed` 判斷；constraint 明確區分 false、null/undefined 與 `applicable=false`；不適用顯示文字且不計失敗；等待上限恢復 30 秒 |
| `app/services/vehicle_decision.py` | 僅壓縮 `run_timeline` 的持有成本事件；維持模擬第 1–12、13–24 等年度區間與所有原金額、購車生效月份 |
| `app/services/vehicle_cost_comparison.py` | financial 分支改用 resolve、run_timeline、evaluate、constraints、ownership_cost_summary；不再計算回應未使用的壓力測試與價格上限 |
| `tests/test_vehicle_stress_ui.js` | 新增 6 項前端判定回歸，包含真實失敗、N/A、null、undefined、其他壓力情境 |
| `tests/test_vehicle_p0_regression.py` | 9 組完整 API 快照回歸及 Claude 高存款案例的正式路由整合測試 |
| `tests/test_vehicle_timeline_events.py` | 12 項年度切點與逐月參考驗證，涵蓋未取整數值、失業、交通抵減及購買月 1/12/13/24/25/58 |
| `tests/test_vehicle_comparison_performance.py` | 防止雙車比較再呼叫完整服務或價格搜尋 |
| `tests/test_vehicle_ui.js` | 原有未提交的 timeout 測試改驗證 30 秒，保留進度、重試、資料與錯誤提示測試 |
| `scripts/benchmark_vehicle_p0.py` | 可重跑的正式 API 快照、完整 JSON 比對及計時工具 |
| `tests/fixtures/p0/vehicle_api_snapshots.json` | 修改財務服務前產生的完整請求與回應；全部為固定合成資料 |
| `docs/p0-final-before.json`、`docs/p0-final-after.json` | 原始樣本、SHA-256、環境、median/max 與 JSON 一致性證據 |

指定補丁未在已檢查路徑及 Git 歷史中找到。使用者後續明確授權停止搜尋，改依實際 profiler 結果實作等效優化。

## Profiler 證據與計算語意

標準單車執行 39 次 timeline，其中價格搜尋 33 次。原本 6 項持有成本每項可拆成 60 個月事件，所有支出類別每月重掃事件；主要熱點為 `calculate_variable_expenses` 與兩個 category event 掃描函式。

最小修正將相同年度金額合併為最多 30 個持有成本區間事件，仍使用原有 `inflation_factor()`、財務引擎及取整規則。第 12 月購車只使用一個月第一年度金額，第 13 月即切換；未從購車月重新起算通膨。

同一案例 cProfile 總函式呼叫由 67,210,502 降至 6,982,022；dict.get 呼叫由 62,413,266 降至 5,970,726。Profiler 本身有額外負擔，以下正常計時不含 profiler。

## 單車 6 組完整 JSON 與效能

Windows / Python 3.12.10；正式 FastAPI TestClient 路由，每例一次不計時 warm-up，另測 3 次，下表為中位數。包含回應序列化，未包含雲端冷啟動或網路延遲。

| 案例 | 修改前（秒） | 修改後（秒） | 完整 JSON |
|---|---:|---:|---|
| 一般貸款與預設成本 | 3.595220 | 0.534072 | 完全一致 |
| 現金購車、第 13 月、通膨與交通抵減 | 3.061599 | 0.476045 | 完全一致 |
| 零預算、零利率、12 期貸款 | 3.561234 | 0.510467 | 完全一致 |
| 第 58 月、84 期貸款、既有債務到期 | 0.358899 | 0.250779 | 完全一致 |
| Claude 高存款失業案例 | 4.275528 | 0.619733 | 完全一致 |
| 無可行車價 | 0.577507 | 0.091635 | 完全一致 |

標準單車改善 85.14%；修改後單車所有計時樣本最大值 0.620398 秒。

## 雙車完整 JSON 與效能

financial 契約維持 `baseline`、`metrics`、`constraints`、`ownership_costs`、`source`；根層差值與養車費欄位也保持一致。

| 案例 | 修改前（秒） | 修改後（秒） | 完整 JSON |
|---|---:|---:|---|
| 車型庫雙車貸款財務比較 | 7.486669 | 0.043864 | 完全一致 |
| 自訂現金車＋長期貸款車、第 12 月購買 | 6.243505 | 0.041825 | 完全一致 |
| 只有養車費、無個人財務 | 0.002528 | 0.002664 | 完全一致 |

前兩項改善 99.41% / 99.33%。原有純養車分支未修改；最後一列約 0.14 毫秒差異不宣稱改善。

## API 案例與測試

Claude 案例的完整實際請求記錄於快照中的 `claude_wealthy_unemployment`：存款 5,000,000、薪資 200,000、車價 500,000；固定生活費 15,000、變動生活費 10,000、既有月付 2,000；基準 2026-09、購車 2026-10；頭期 150,000、貸款 60 期、年利率 3%。其餘成本、通膨與門檻沿用既有 API 預設，完整來源與實際採用值保存在回應快照。

- `POST /decisions/vehicle`：失業 `passed=true`；月結餘 `applicable=false`、`passed=null`；最低現金及預備金仍正常通過；其他三項壓力結果與修改前一致。
- 全 Python：**337 passed，2 個既有 JWT 測試短金鑰警告，18.60 秒**。
- 全 Node：**78 passed**。相對前輪已驗證的 314 / 72，新增 Python 23、Node 6，沒有刪除測試來湊數。
- 新增 P0 Python 專項：23 passed；前端壓力專項：6 passed。
- `git diff --check` 通過。
- 瀏覽器：`http://127.0.0.1:8766/vehicle.html`，Playwright / Chromium，1365×900 與 390×844。Browser plugin 不可用，使用本機既有 Playwright，未安裝依賴。
- 操作：填寫財務資料 → 勾選確認 → 真實 API → 開啟壓力表；充足案例摘要為「4 種適用情況，0 種未符合限制」，失業列顯示月結餘不適用；低存款案例正確顯示現金／預備金失敗。
- 頁面身分、非空白、無錯誤 overlay、console/pageerror、實際互動與截圖均通過；手機頁面無整頁水平溢出，表格沿用內部水平捲動。
- 截圖保存在本機 Temp：`finsim-p0-desktop.png`、`finsim-p0-mobile.png`。
- 30 秒上限已恢復；Node 測試驗證 abort、提示、表單資料與重試控制。效能樣本與真實瀏覽器請求均遠低於 30 秒。

重跑：

```powershell
python -m pytest -q
node --test tests/*.js
python scripts/benchmark_vehicle_p0.py --output <新的結果檔路徑.json>
```

## 版本控制與既有修改保護

本輪僅提交可區分的變更，沒有 reset、discard、切換 branch 或推送：

- `a1de21d`：前端壓力結果與 Node 回歸。
- `e921c9f`：單車事件壓縮、完整 API 快照、benchmark 與回歸。
- `c14d95c`：雙車 financial 重複運算移除。
- `c5da977`：30 秒 timeout 提示。
- 本報告另以文件 commit 保存。

開始時已有 5 個修改檔：`app/services/vehicle_decision.py`、`static/vehicle.html`、`static/vehicle.js`、`tests/test_vehicle_decision.py`、`tests/test_vehicle_ui.js`；另有 AI 規劃、教授會議與前輪工作報告 3 份未追蹤文件。原有 cent 搜尋、失業後端判定、其他 UI 修改及文件未夾帶提交。原始檔副本保存在 `.git/p0-final-start-20261022/`。

`tests/test_vehicle_ui.js` 的 30 秒斷言位於原有未提交測試區塊，因此保留為未提交修改，避免將整段舊修改混入本輪 commit。數值 timeout 原 HEAD 已為 30 秒，本輪撤回的是工作區先前改成 90 秒的設定。

**驗收對象是保留既有修改的完整工作區。上述 commits 依賴原有未提交的失業後端與 cent 搜尋修正；單獨 checkout HEAD 不能視為相同已驗收版本。** Claude Review 與後續版本整合必須保留這個差異。

## P0 與下一階段

本輪範圍內未發現尚未解決的功能 P0；可交 Claude Review。核可並整合原有未提交修改後，可進入 AI 選車問卷開發。

正式環境冷啟動、並發與 p95 未驗收，本機數據不作部署效能保證。JWT 測試警告維持原狀。本輪到此停止。
