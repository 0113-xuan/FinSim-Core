# FinSim 2.0 P0 最終整合報告 — Claude 獨立覆審報告

審查日期：2026-10-23（Asia/Taipei）
審查對象：「FinSim 2.0 P0 最終整合報告」（針對前次審查 P1：HEAD 單獨不可用）
審查 HEAD：`35b7a52`（程式碼最後變更 commit 為 `d8441e8`）
審查方式：唯讀。未修改、未提交、未 reset／checkout；HEAD 以 `git archive` 匯出到 repo 外暫存區測試；測試時 `AI_ENABLED=false`，Gemini／OpenAI／Supabase 變數皆清空。

## 1. 結論

**前次 P1 已解除，可進入 AI 問卷開發；另有 1 項 P2（快取版本號未提交）建議先補。**

## 2. 已驗證且與報告一致

| 項目 | 結果 |
|---|---|
| Commit 內容 | `746b532`（`vehicle_decision.py`＋`test_vehicle_decision.py`）、`b746b6a`（`vehicle.js`＋`test_vehicle_ui.js`）、`d8441e8`（`vehicle.css` 僅新增 1 行）、`35b7a52`（文件）；檔案與報告相符 |
| 35b7a52 是否只含文件 | 是。`git diff d8441e8 HEAD -- app static scripts tests` 無輸出 |
| 乾淨 HEAD 匯出測試（不含 `.env`、未追蹤文件、`.git`） | Python **337 passed**（無警告）；Node **78 passed**，0 failed，0 skipped |
| 前次 7 項失敗 | 已消除（先前 HEAD 為 331 項、7 failed） |
| `.env` 是否被追蹤 | 否（`git ls-files` 無 `.env`） |
| 30 秒 timeout | `static/vehicle.js:172` `setTimeout(() => controller.abort(), 30000)`，10 秒顯示「仍在計算」提示 |
| unknown 樣式 | `.vehicle-page .risk-headline[data-state="unknown"] { color:#854d0e; background:#fef9c3; border-left:4px solid #a16207; }`，與 failed（紅）區分；未改判定邏輯 |
| 效能表 | `docs/p0-integration-before-2026-10-23.json` 與 `docs/p0-integration-head-2026-10-23.json` 的 median 與報告表格 9 列全部一致 |
| 整合後 JSON 回歸 | head 檔 9 個案例 `json_identical` 全為 `True` |
| 整合前基準的誠實標註 | before 檔 `source_revision=d1ca696`，`validation_note` 明示「舊 HEAD 缺 `stress.passed`，計時不代表通過完整回歸」，且無 `json_identical` 欄位；報告對此說明一致 |
| 工作區保護 | 僅剩 `static/vehicle.html` 修改與 4 份未追蹤文件（含本次與前次審查報告），無檔案被覆蓋 |

## 3. 發現

### P2 — `vehicle.js` 已改但快取版本號未提交（會讓使用者拿到舊 JS）

- `b746b6a` 修改了 `static/vehicle.js`（stress `passed` 判斷、等待／錯誤處理）。
- 但 `static/vehicle.html` 在 HEAD 仍是 `vehicle.js?v=20261012-17`；`-18` 只存在於**未提交**的工作區修改。
- 後果：已有舊版 `vehicle.js?v=...-17` 快取的瀏覽器，部署 HEAD 後可能繼續執行舊前端，而舊前端不讀 `stress.passed`，會得到與修正前相同的錯誤判定。
- 建議：將 `vehicle.html` 的 17→18 作為獨立小 commit 提交（報告已知此差異並說「不影響執行的程式內容」，但對有快取的使用者是有影響的）。

### P2 — 效能表中三列並非改善

整合後「無可行車價」、「雙車貸款比較」、「純養車費」比整合前略慢（0.091→0.105、0.0432→0.0476、0.0025→0.0046 秒）。報告已自述「不宣稱改善」，屬毫秒級量測雜訊，不構成問題；列出僅供對照。

## 4. 未驗證項目

- **Playwright 瀏覽器驗收與截圖**：僅確認 `docs/p0-integration-ui-2026-10-23.json` 存在且含 `passedState`／`failedState`／`unknownState` 等欄位；未重跑瀏覽器、未檢視 Temp 內截圖與 computed style。
- **87 個檔案的 LF/CRLF 正規化比對**：未重現。
- **我自己的效能重跑**：未重跑 `scripts/benchmark_vehicle_p0.py`，只交叉核對報告與 JSON。
- 正式環境冷啟動、並發與 p95：報告本身亦聲明未驗收。

## 5. 建議下一步

1. 提交 `vehicle.html` 的 `?v=20261012-18`（P2）。
2. 之後即可進入 AI 選車問卷開發；下一階段請避免再把相依後端修改留在工作區未提交。
