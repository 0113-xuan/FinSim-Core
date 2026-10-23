# FinSim 2.0 P0 最終整合報告

日期：2026-10-23（Asia/Taipei）。本輪只整合既有 P0 相依修改及 unknown 樣式，沒有新增 AI 功能、修改財務引擎或推送遠端。

## P1 修正與 commits

原 HEAD `d1ca696` 的前端與 API 回歸測試已使用 `stress.passed`，但提供此欄位的後端、失業不適用判定及 cent 搜尋仍在工作區。這是提交內容不完整，不是需要重新設計財務模型。

| Commit | 檔案 | 修改 |
|---|---|---|
| `746b532` | `app/services/vehicle_decision.py`、`tests/test_vehicle_decision.py` | 提交既有 stress_constraints、壓力層級 passed、cent-boundary 搜尋及 6 項原有回歸案例 |
| `b746b6a` | `static/vehicle.js`、`tests/test_vehicle_ui.js` | 提交上一輪已驗證的等待／錯誤處理與 3 項原有 Node 測試；維持 30 秒 timeout |
| `d8441e8` | `static/vehicle.css` | unknown 使用深琥珀文字、淡黃底及左側線條，與通過／失敗區分；不改判定邏輯 |

本報告及本輪量測 JSON 另以文件 commit 保存。只加入以上明確屬於 P0 的檔案，沒有將所有未提交內容一次提交。

## HEAD 與工作區驗證

程式碼驗證版本：`d8441e8f3dd1dc4804289064811672b3dc952bda`。以 `git archive --format=zip HEAD` 匯出到 repo 外新目錄，未複製工作區 `.env`、未追蹤文件或 `.git`；文件 commit 不含程式碼變更。

| 驗證對象 | 完整 Python | 完整 Node |
|---|---:|---:|
| 獨立乾淨 HEAD 匯出 | 337 passed | 78 passed |
| 原工作區 | 337 passed | 78 passed |

測試數量維持預期基準。相對舊 HEAD 的 331 項 Python／75 項 Node，提交的是原有 6 項 Python 與 3 項 Node 測試，沒有刪除或修改案例來湊數。舊 HEAD 的 7 項失敗已消除。

兩邊均在程序內設定 `AI_ENABLED=false`、清空 AI／Supabase 憑證及 URL，使用相同的固定長測試 JWT key；因此本輪沒有前次短 JWT key 警告，沒有更動產品設定或 `.env`。同一 Windows Python 安裝提供依賴；沒有安裝新套件。最終文件提交後再以新 HEAD 匯出執行完整套件，確保交付 HEAD 本身可獨立通過。

正式 `POST /decisions/vehicle` 的高存款案例：存款 5,000,000、月薪 200,000、車價 500,000；失業 `passed=true`，月結餘 constraint 保持 `applicable=false`、`passed=null`。最低現金與預備金限制仍正常評估，低存款案例仍判定失敗。完整輸入沿用 `tests/fixtures/p0/vehicle_api_snapshots.json`。

比對 87 個 Python／JS／CSS／HTML 檔案、正規化 LF/CRLF 後，工作區與乾淨版本只剩 `static/vehicle.html` 的既有 script 快取版本差異，不影響執行的程式內容。

## 效能與 JSON 回歸

環境：Windows 11 `10.0.26200`、Python 3.12.10；正式 FastAPI TestClient API，逐例一次不計時 warm-up 與 3 次計時，以下為中位數。前後 benchmark 分開執行，沒有與測試／瀏覽器運算同時量測。

整合前以獨立匯出的 `d1ca696` 量測，整合後使用乾淨的 `d8441e8`，同一組固定請求；未改動財務程式來取得更快數據。

| 案例 | 整合前（秒） | 整合後（秒） |
|---|---:|---:|
| 一般單車貸款 | 0.715813 | 0.551250 |
| 現金、第 13 月、通膨／交通抵減 | 0.612237 | 0.467396 |
| 零預算、零利率、短期貸款 | 0.682596 | 0.502836 |
| 第 58 月、長期貸款／債務到期 | 0.337730 | 0.248005 |
| Claude 高存款案例 | 0.785771 | 0.634645 |
| 無可行車價 | 0.090829 | 0.104909 |
| 雙車貸款財務比較 | 0.043195 | 0.047579 |
| 自訂現金車＋長期貸款車 | 0.044022 | 0.043198 |
| 純養車費比較 | 0.002455 | 0.004631 |

本輪目標為提交完整性，並非全面加速。部分毫秒差異不宣稱改善；最慢的整合後單車樣本為 0.647107 秒，遠低於 30 秒。

- **6 組單車及 3 組雙車：整合後完整 JSON 全部符合既有 P0 快照，SHA-256 也一致。**
- 舊 HEAD 的六組單車完整 JSON 原本不符快照；原因是缺少 passed／失業適用性契約，不能把舊 HEAD 的計時當成正確性通過。
- 同時比較整合前後所有非壓力欄位及各壓力情境財務 metrics，九組全部一致；回復契約之外，沒有意外的財務數值或欄位變動。
- 前一輪真正優化前的歷史基準仍保留在 `docs/p0-final-before.json`（一般單車 3.595 秒、雙車 7.487 秒）；本輪重新量到約 0.551／0.048 秒。這個歷史基準不是本輪重新量測的原始慢版。

原始數據：`docs/p0-integration-before-2026-10-23.json`、`docs/p0-integration-head-2026-10-23.json`。目前腳本可直接重跑：

```powershell
python scripts/benchmark_vehicle_p0.py --output <新的結果檔.json>
python -m pytest -q
node --test tests/*.js
```

## 前端驗證

沿用 frontend-testing-debugging／Playwright 流程；Browser plugin 不可用，使用本機既有 Playwright，未安裝依賴。由乾淨匯出的 HEAD 啟動 `http://127.0.0.1:8767/vehicle.html`，以 Chromium、1365×900 與 390×844 驗證：

- 實際填表、確認並呼叫正式 API；充足案例顯示全部符合及失業月結餘不適用，低存款案例顯示現金／預備金失敗。
- 另外以測試攔截回應注入 null／缺少 passed，僅驗證 unknown 的呈現，不改動後端。摘要為 0 種未符合、4 種尚未判定。
- Computed style 確認 unknown 為 `#854d0e` 文字、`#fef9c3` 底色、4px 左線，與通過的灰綠及失敗的淡紅底不同。
- 頁面身分、非空白、無錯誤 overlay、console/pageerror、實際互動與桌面／手機截圖均通過；手機無整頁水平溢出。

機器可讀證據：`docs/p0-integration-ui-2026-10-23.json`。乾淨匯出、舊版基準計時工具與截圖位於本機 Temp 的 `finsim-p0-integration-1311fe82673b43408d8ee7e69bc7af93/`，不影響 Git HEAD。

## 剩餘工作區內容與結論

保留未提交的 `static/vehicle.html`（僅 script 快取版本 17→18）以及 4 份未追蹤文件：AI 選車計畫、Claude 2026-10-23 Review、前輪工作報告、教授會議記錄。沒有 reset、discard 或覆蓋這些內容；既有 `.git` 備份目錄也未更動。

P1 的 HEAD 相依缺漏已解除，P2 unknown 樣式已補齊。未發現阻礙進入 AI 問卷開發的程式整合問題，可交 Claude 最終 Review；本輪到此停止。正式環境冷啟動、並發與 p95 仍未驗收。
