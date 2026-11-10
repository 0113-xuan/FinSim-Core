# Codex 任務（後端）：意外風險

日期：2026-11-10。分支 `feat/life-shocks-be`（從 `feat/life-shocks` 的 HEAD 開出）。期限：11/12。

## 背景

蒙地卡羅目前只有通膨與台股報酬會變，買車現金流是確定的，結果的變動對使用者沒意義。要讓引擎能模擬「重大醫療支出」「車禍與車損自付」「收入中斷」三種意外，並提供一個端點回傳「有意外」的結果。前端另一份任務負責畫面。

## 契約

`docs/contracts/life_shocks_2026-11-10.md`（唯一依據，不要複製第二份）。第 3 節的數字是示範假設，照寫進 Python 常數並加註解「示範假設，不是統計」，不要自己改數字，也不要補任何出處。

## 你可以改的檔案

`app/**`、`main.py`、`data/knowledge/**`、`tests/*.py`、`tests/fixtures/**`。

不可以改：`static/**`、`tests/*.js`、`tests/browser/**`、`docs/**`、`.env*`、`PRODUCT.md`、`README.md`。

## 要做的事

1. `app/schemas.py`：`RandomShockInput` 加 `income_multiplier`（`Optional[float]`，0 到 1，預設 None）。完成的樣子：既有請求不受影響，超出範圍回 422。
2. `app/core/shocks.py` 與 `app/core/simulation.py`：支援收入中斷型。觸發後 `duration_months` 個月內收入乘 `income_multiplier`，重疊取較小倍數、不延長。完成的樣子：契約測試 1 通過；`shock_details` 仍能列出這類意外。
3. 意外改用自己的 `random.Random`（由 `seed` 衍生），不再消耗變動支出的亂數。完成的樣子：契約測試 2 通過。
4. 新增預設情境常數（建議放 `app/core/life_shocks.py`）與 `POST /monte-carlo/life-shocks`，請求、回應、錯誤照契約第 4 節。`chance_in_horizon` 在後端算。完成的樣子：契約測試 3 到 6 通過。
5. 知識庫補一段，並在 `tests/test_plan_qa.py` 補黃金測試。完成的樣子：契約測試 8 通過，`tests/test_knowledge_base.py` 仍通過；文字用繁中白話，不寫診斷或存活字眼、不寫任何機率來源或統計數字。

## 必要的測試

契約第 6 節「後端」8 條，逐條對應；另外：`tests/test_core.py:108` 與 `tests/test_monte_carlo_sampling_metadata.py` 若因改用獨立亂數而失敗，改成檢查性質（可重現、有無意外的差異方向），不可刪測試，並在回報寫明改了哪幾個。

## 不在範圍

契約第 7 節全部。不改 `/monte-carlo`、`/simulate` 的回應格式。不動資料庫。

## 紅線

- Python 負責計算，AI 只解釋；不產生任何數字，測試一律用 `MockAIProvider`，不呼叫真的 AI。
- 不 push、不 `git add .`（只 add 自己改的檔案）、不讀或輸出 `.env` 與任何 key。
- commit 前 `python -m pytest -q` 與 `node --test tests/*.js` 全過。基準：pytest 974 passed、node 273 pass。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 契約沒寫、規則互相矛盾的地方不要自己選，寫進回報。

## 回報格式

commit hash；改了哪些檔案；兩套測試指令與通過數量；沒做的與原因；發現的矛盾；改過的既有測試清單。
