# Codex 任務（後端）：新增事件範本的知識庫說明

日期：2026-11-12。分支 `feat/event-templates-be`（從 `feat/event-templates` 的 HEAD 開出）。期限：11/13。

## 背景

前端新增「搬家」「醫療支出」「二手車」三個事件範本。後端引擎不用改；只需要讓計畫頁的問答能解釋這三個事件怎麼算。

## 契約

`docs/contracts/event_templates_moving_medical_usedcar_2026-11-12.md` 第 5 節與第 6 節的 10、11 條。

## 你可以改的檔案

`data/knowledge/**`、`tests/test_plan_qa.py`（與必要時 `tests/test_knowledge_base.py`）。

不可以改：`app/**`、`main.py`、`static/**`、`tests/*.js`、`docs/**`、`.env*`。

## 要做的事

1. 在 `data/knowledge/` 補三段，id 分別為 `event-moving`、`event-medical`、`event-used-car`，格式照 `assumptions.md` 現有段落（標題、`id:`、`source:`、`tags:`、內文）。內容照契約第 5 節。完成的樣子：`tests/test_knowledge_base.py` 通過。
2. 在 `tests/test_plan_qa.py` 補三條黃金測試，仿 `test_life_shocks_question_cites_assumptions`：問「搬家事件怎麼算」「醫療支出事件怎麼算」「二手車事件怎麼算」，引用對應 id，且回應不含「診斷」「存活」。完成的樣子：三條通過。
3. 「醫療支出」那段要寫明它與「加入意外風險」是兩件事（前者是使用者自己設定的已知支出，後者是隨機抽的假設，兩個都開會重複計入）。

## 必要的測試

契約第 6 節 10、11 條。

## 不在範圍

不改引擎與 API；不寫任何價格、機率、統計數字或出處；不寫診斷或存活字眼。

## 紅線

- Python 負責計算，AI 只解釋；測試一律用 `MockAIProvider`，不呼叫真的 AI。
- 不 push、不 `git add .`、不讀或輸出 `.env`。
- commit 前 `python -m pytest -q` 與 `node --test tests/*.js` 全過。基準：pytest 980 passed、node 278 pass。
- commit 結尾：`Co-Authored-By: Codex <noreply@openai.com>`。
- 契約沒寫的地方不要自己選，寫進回報。

## 回報格式

commit hash；改了哪些檔案；兩套測試指令與通過數量；沒做的與原因；發現的矛盾。
