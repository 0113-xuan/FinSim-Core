# FinSim 2.0 P4 討論測試版推送檢查 — Claude 報告

日期：2026-10-29（Asia/Taipei）
分支：`test/p4-integration` → https://github.com/0113-xuan/FinSim-Core/tree/test/p4-integration
推送 Commit：`ccf33aeba7191fdfd96dbcde3ef2d6e915b428da`（`3d5f76a..ccf33ae`，fast-forward，未 force）

## 1. 結果
- 遠端先 `git fetch`：`origin/test/p4-integration` 為本機 HEAD 的祖先，因此是安全的 fast-forward；沒有 force push、reset 或覆蓋他人修改。
- 本次只推送 1 個 commit（3 檔 +206 行）：`docs/P4_TEAM_TEST_GUIDE.md`、`scripts/diagnose_car_needs_ai.py`（離線診斷，不連外）、`tests/test_ai_fast_fail_diagnostics.py`。
- 工作區無已追蹤檔案的未提交修改。16 個未追蹤文件（含我的審查報告、工作報告、規劃、教授會議紀錄、`FINSIM_PROJECT_MAP.html`、`P4_AI_FAST_FAIL_DIAGNOSIS_2026-10-29.md`）**未提交**。
- `main` 未動（`origin/main` 仍為 `cd92f65`）；未部署。

## 2. 測試（乾淨 `git archive HEAD` 匯出，AI／Supabase／簽章金鑰變數清空，`AI_ENABLED=false`）
- Python：**507 passed**
- Node：**154 passed**，0 failed／skipped

## 3. 機密檢查
- `.env` 已被 `.gitignore` 忽略，從未進入 Git；歷史中唯一的 env 類檔案是 `.env.example`（只有佔位值，`JWT_SECRET=change-me-in-production`）。
- 全部 refs 的歷史掃描：`AIza`、`sk-`、私鑰區塊、長值 `*_API_KEY`／`SIGNING_KEY` 指派皆無；測試檔中的 `test-only-worker-key-…` 為測試用假值。
- **既有歷史問題（非本次推送引入）**：2026-04 的舊 `main.py` 內有一個寫死的 Supabase JWT，payload 的 role 為 **`anon`**（公開用金鑰，非 `service_role`）。它已在 `origin/main` 與其他遠端分支的歷史中；目前 HEAD 沒有，本次推送範圍也沒有。風險取決於 Supabase 的 RLS／權限設定，我沒有連線檢查。若該專案資料表未啟用 RLS，建議輪替金鑰並檢查權限；改寫歷史不在本次範圍。
- 組員指南已如實寫明上述歷史提醒與「掃描不涵蓋所有格式」的限制。

## 4. 組員測試說明（重點）
1. `git clone` 後 `git checkout test/p4-integration`；詳細步驟見 `docs/P4_TEAM_TEST_GUIDE.md`。
2. 需要 Git、Python 3.12、Node 18+；`python -m venv venv`、安裝 requirements、`Copy-Item .env.example .env`。
3. 預設 `AI_ENABLED=false` 啟動：`uvicorn main:app --host 127.0.0.1 --port 8000`；每台電腦只開一個 8000 服務。
4. 頁面：`/vehicle.html`（購車試算）、`/car-needs.html`（幫我選車）。不要用 `file:///`。
5. 手動問卷與財務引擎不需要任何 Key；AI 為選用，需自備 Key 與額度，勿把 Key 放進 Git／截圖／聊天。
6. 只用指南中的合成案例，不要輸入真實財務或個資。
7. AI 秒回 503 時，先看 `/api` 的 `ai_enabled`，再執行 `python -B -m scripts.diagnose_car_needs_ai`。
8. 已知限制：真實 Gemini 仍有約 4 成逾時，可略過 AI 繼續推薦；Provider 在初始化階段直接拋例外時仍可能回 500。
9. 更新用 `git pull --ff-only`，不要 force push；回報請附 commit hash。

## 5. 未驗證
- 遠端 GitHub 儲存庫的可見性與四位組員的存取權（無法從本機確認）。
- Supabase 的 RLS／金鑰輪替狀態。
- 真實 Gemini 品質與穩定性（未呼叫）。
