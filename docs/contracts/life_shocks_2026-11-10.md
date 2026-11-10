# 契約：計畫頁「意外風險」

日期：2026-11-10。分支 `feat/life-shocks`（從 `1809719` 開出）。功能凍結 11/15。
交接背景見 `docs/HANDOFF_LIFE_SHOCKS_2026-11-10.md`。本檔是後端與前端唯一的共同依據。

## 1. 決定（已定，不再討論）

| 項目 | 決定 | 理由 |
| --- | --- | --- |
| 數字來源 | A：示範假設，畫面與知識庫都標「示範假設，不是統計或預測」 | 沒有查證過的官方數字，不能寫成統計 |
| 使用者可否改數字 | v1 不可改，只在畫面列出假設 | 開關加唯讀清單是最小可行版本；要改再擴充 |
| 畫面用語 | 「重大醫療支出」「車禍與車損自付」「收入中斷」；不出現診斷字眼、不出現「Monte Carlo」 | `PRODUCT.md` 與交接第 4 點 |
| 比較方式 | 「沒有意外」用現有 `/monte-carlo`（300 次、種子 42）的結果；「有意外」用新端點，請求內容完全相同 | 只多跑一次，且兩邊可逐項對照 |
| 數字由誰帶入 | 預設情境全部寫在 Python，前端不放任何機率或金額 | 紅線：AI 與前端都不產生數字 |

## 2. 引擎要補的兩件事（後端）

目前引擎有兩個缺口，不補就無法做出可信的比較：

1. **收入中斷表示不了。** `random_shocks` 只能加支出。需要讓一個意外在觸發後的 `duration_months` 個月內，把收入乘上 `income_multiplier`（0 = 完全沒收入）。
2. **意外與變動支出共用同一條亂數序列。** `simulate_finance` 裡意外每月多抽亂數，會讓之後每個月的變動支出跟著改變，「沒有意外」與「有意外」就不是只差意外本身。意外必須用自己的 `random.Random`，由 `seed` 衍生，不動原本的序列。

`RandomShockInput` 新增一個欄位：

| 欄位 | 型別 | 預設 | 說明 |
| --- | --- | --- | --- |
| `income_multiplier` | `float`，0 到 1，可為 null | null | 非 null 時是收入中斷型：不抽金額，觸發後 `duration_months` 個月內收入乘上此值；`min_amount`、`max_amount` 可為 0。重疊時取較小的倍數，不延長 |

既有行為不可變：沒有 `income_multiplier` 的意外，金額與觸發月份在同一個 `seed` 下要與現在相同的規則一致（但因改用獨立亂數，數值可以不同；既有測試若釘死數值，後端要改成檢查性質，並在回報說明）。

## 3. 預設情境（Python 常數，數字是示範假設）

> **待使用者確認**：下列數字是我暫訂的示範值，不是統計。確認或改掉之後才寫進程式。

| id | 畫面名稱 | 類型 | 每月機率 | 金額（元） | 持續 | 收入倍數 |
| --- | --- | --- | --- | --- | --- | --- |
| `medical` | 重大醫療支出 | 支出 | 0.005 | 50,000 到 300,000，uniform | 1 | — |
| `accident` | 車禍與車損自付 | 支出 | 0.004 | 20,000 到 150,000，uniform | 1 | — |
| `income_gap` | 收入中斷 | 收入中斷 | 0.004 | — | 6 個月 | 0 |

## 4. 新端點

`POST /monte-carlo/life-shocks`

**請求**：與 `POST /monte-carlo`（`MonteCarloRequest`）完全相同。計畫頁送的 `random_shocks` 一定是空的；若不是空的，回 422，訊息：`此端點會自行帶入意外情境，請不要傳 random_shocks`。

**行為**：用請求的 `profile`、`events`、`loans`、`assets`、`months`、`simulations`、`seed`，加上第 3 節三個情境，跑 `run_monte_carlo`。

**回應 200**：

```json
{
  "iterations": 300,
  "seed": 42,
  "probability_cash_shortfall": 0.1233,
  "net_worth_percentiles": { "p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0 },
  "real_net_worth_percentiles": { "p5": 0, "p50": 0, "p95": 0 },
  "assumptions": [
    {
      "id": "medical",
      "label": "重大醫療支出",
      "kind": "expense",
      "monthly_probability": 0.005,
      "min_amount": 50000,
      "max_amount": 300000,
      "duration_months": 1,
      "income_multiplier": null,
      "chance_in_horizon": 0.2594
    }
  ],
  "disclaimer": "機率與金額是示範假設，不是統計或預測；只用來看這份計畫撐不撐得住意外。"
}
```

- `net_worth_percentiles`、`real_net_worth_percentiles`、`probability_cash_shortfall` 的欄位名稱、型別、定義與 `/monte-carlo` 回應相同，前端可共用同一套顯示函式。
- `assumptions` 固定三筆，順序為 `medical`、`accident`、`income_gap`。`kind` 只有 `expense` 與 `income_gap` 兩種值（收入中斷型用 `income_gap`）。`income_multiplier` 在支出型為 null。
- `chance_in_horizon = 1 - (1 - monthly_probability) ** months`，四捨五入到 4 位，由後端算。
- `disclaimer` 由後端給，前端原樣顯示，不改字。

**錯誤**：請求格式錯誤沿用 FastAPI 的 422；其他錯誤沿用既有端點的繁中錯誤格式。

## 5. 前端行為

- 模擬表單加一個「加入意外風險」開關，預設關，不存進計畫。
- 關：畫面與現在完全一樣，不呼叫新端點。
- 開：照原本流程算出結果後，用同一份請求（`seed: 42`、`simulations: 300`）再呼叫新端點。結果區多一張「意外風險」卡片：
  - 並排兩欄：「沒有意外」「有意外」。每欄顯示現金不足機率、期末淨資產範圍（p5 到 p95）與中位數。
  - 卡片下方列出三個假設（名稱、這段期間遇到的機會 `chance_in_horizon`、金額或收入中斷月數），以及 `disclaimer`。
- 降級：新端點失敗時，原本的結果照常顯示，卡片位置顯示錯誤訊息與重試入口；不可讓整個結果消失。
- 修改表單任何欄位會讓結果失效（既有 `invalidate` 行為），卡片一併清掉。

## 6. 測試

**後端（pytest）**
1. 收入中斷型意外觸發後，在 `duration_months` 內收入等於原收入乘 `income_multiplier`，期滿後恢復；重疊時不延長。
2. 意外使用獨立亂數：同一個 `seed`，沒有意外與有意外的 `variable_expense` 逐月相同。
3. 同一個請求（同種子），新端點的 `probability_cash_shortfall` 不低於 `/monte-carlo` 的值。
4. 同一個請求呼叫兩次，回應完全相同（可重現）。
5. 傳非空 `random_shocks` 回 422。
6. `chance_in_horizon` 與公式一致；`assumptions` 固定三筆、順序正確。
7. 既有測試全過（數量不得減少）。
8. 知識庫：新增一段說明（意外的機率與金額是假設，不是預測；說明三個情境、收入中斷怎麼算），寫進 `data/knowledge/assumptions.md` 或新檔，並在 `tests/test_plan_qa.py` 補黃金測試（問「意外風險的機率是怎麼來的」要引用該段；不可出現診斷或存活字眼）。

**前端（node）**
1. 關閉時不呼叫新端點、不出現卡片。
2. 開啟時用同一份請求加上相同種子呼叫新端點。
3. 兩欄數字來自回應，前端沒有任何寫死的機率或金額。
4. 新端點失敗時原結果仍在、卡片顯示錯誤。
5. 不使用 `innerHTML` 插入回應文字。
6. 375px 寬度無水平捲動（Playwright 截圖由 Claude 驗收）。

## 7. 不在範圍

診斷、存活率、對話歷史、新的事件範本、使用者自訂機率與金額、其他情境、把開關狀態存進計畫、官方統計來源（B 方案，有時間再補）。
