# Claude 審查報告：計畫頁 AI 問答（簡易 RAG）

日期：2026-11-05　分支：`feat/ai-plan-qa`　審查範圍：Codex 的兩個 commit
- `28327c3` feat: add grounded single-turn plan Q&A with offline knowledge retrieval（20 檔，+1283）
- `0293e81` fix: decline plan QA promise demands before generation（2 檔，+54）

任務文件：`docs/CODEX_TASK_AI_PLAN_QA_2026-11-04.md`

## 1. 結論

**有條件通過：修掉 1 個 P1 之後可以合併。** 架構照任務文件做了，知識庫內容和程式碼對得上，沒有 AI 時的降級、拒答、查無依據三條路徑都正常。唯一會讓「AI 不產生數字」原則破功的是中文數字漏洞（P1-1），我在畫面上實際重現了。

## 2. 測試結果

| 項目 | 結果 |
| --- | --- |
| `python -m pytest -q`（乾淨 worktree，commit `0293e81`） | 954 passed（審查前基準 850） |
| `node --test tests/*.js`（乾淨 worktree） | 235 pass / 0 fail |
| 同樣兩套測試（目前工作區，含未提交的 11 個前端檔） | pytest 954 passed、node 243 pass |
| `python scripts/check_knowledge.py` | 35 段、6 個檔案，格式有效 |

注意：工作區另有 11 個**未提交的前端檔案**（`static/event-picker.js`、`explanation-model.js`、`plan-page.js`、`plan.html`、`results-model.js`、`shell.css`、`shell.js`，與 4 個 `tests/*.js`）和 `PRODUCT.md`、`.impeccable/`。它們不屬於 Codex 這兩個 commit，我只審 commit 本身，但畫面測試是在含這些修改的工作區跑的。`plan-page.js`、`plan.html` 兩邊有重疊，commit 前要分清楚。

## 3. 發現

### P1-1　中文數字可繞過「AI 不寫數字」的驗證（已重現；**2026-11-05 已修，未 commit**）

> 修法：`app/services/plan_qa.py` 沿用 `plan_explanation.py` 的 `CN_NUMBER`、`CN_PERCENT`、`CN_ALLOWED`，中文數字片語（如「三十萬」「五成」「百分之十五」「六個月」）必須原樣出現在該段引用的資料文字裡，否則 `QARejected`，重試一次後降級為直接引用資料。「一年」「一次」「一個月」照舊放行；引用資料本來就有的「一筆」「半年」可以使用。`tests/test_plan_qa.py` 新增 3 組測試（7 個案例），拿掉修正後 7 個案例失敗。驗證後：pytest 961 passed、node 243 pass。



`app/services/plan_qa.py` 的 `validate_answer` 只擋阿拉伯數字（`NUMBERS`／`DIGIT`）。AI 如果寫「你的最低現金大約是三十萬元」，沒有任何阿拉伯數字，就通過驗證，並且在畫面上標成 AI 回答。

- 重現方式一：用假 provider 回傳 `text='你的最低現金大約是三十萬元，約為五成機率'`、`sources=['minimum-cash']`，`answer_plan_question` 回傳 `source='ai'`，原樣放出。
- 重現方式二：在計畫頁用同樣的假回答，畫面顯示「你的最低現金大約是三十萬元」，下方還掛著「依據：最低現金和發生月份」，看起來像有憑據。
- 既有的 `app/services/plan_explanation.py:44-48` 已有 `CN_NUMERAL`、`CN_NUMBER`、`CN_PERCENT` 防護，`plan_qa.py` 沒有沿用。
- 修法：在 `validate_answer` 對 `literal`（去掉佔位符後的文字）做同樣的中文數字檢查，但知識庫內文本身有「九成」「五成」「十二個月」，所以規則應是「中文數字片語必須原樣出現在該段引用的資料文字裡」，不是一律禁止。補測試：中文金額被擋、引用資料裡本來就有的「五成」放行。

### P2-1　檢索會回答錯題目（**2026-11-05 已處理，未 commit**）

> 處理方式：(1) `data/knowledge/vehicle.md` 新增 `loan-payment`「貸款利率與每月還款怎麼算」，內容對照 `app/core/events.py:calculate_loan_payment` 與 `balance_sheet.py:loan_balance／loan_interest_through`（36 段）；「貸款利率怎麼算」「車貸利率怎麼算」現在第一名是它，「我的職業會調整貸款利率嗎」仍是職業那段。(2) `knowledge_base.py` 的 `retrieve` 回傳 `coverage`（問題裡有意義的詞，被該段涵蓋的比例）；`is_relevant` 新增短問題路徑：涵蓋率 100% 且分數 ≥ 3.5（`SHORT_QUERY_FLOOR`）也算有依據，所以「抽樣是什麼」有答案，「現金」「汽車」仍查無。(3) 「今天」加入問題停用詞，單獨問「今天」不再命中購買力那段。(4) 黃金測試集加 4 題有答案、3 題無答案；新增 2 個測試。pytest 966 passed。
> 已知限制：「信用卡循環利息」仍會因「利息」而命中貸款相關段落（分數約 9，涵蓋率 0.33），屬於單詞重疊的誤判，沒有再加規則；AI 路徑會因引用資料說明不了而回「沒有依據」或降級。

- 「貸款利率怎麼算」得分 19.9，命中 `occupation-and-rate`（職業不會調整貸款利率）。這段沒有講利息怎麼算，AI 沒有依據卻被判定有依據；沒有 AI 時 extractive 會把這段原文當答案貼出來。
- 「抽樣是什麼」得分 4.4，低於門檻 7.0，被判查無依據，但 `simulation-count` 明明有講抽樣。「現金」單獨一詞也查無。
- 建議：把這幾題加進黃金測試集（一題放 `unanswerable`，兩題放 `answerable`），再調門檻或停用字。口試時評審很可能問「利率怎麼算」。

### P2-2　引用來源顯示的是程式碼路徑

回答下方「資料來源」顯示 `app/core/simulation.py：summarize_simulation；…`、`static/results-model.js：assumptionRows` 這類字串。讀者是剛出社會的年輕人，`PRODUCT.md` 要求不用工程詞。畫面上也看不出來這是什麼。需要你決定：
- A. 只顯示段落標題（例如「最低現金和發生月份」），程式路徑收進可展開的「技術來源」；
- B. 維持現狀（口試時可以證明有出處）。

### P3

- `NO_BASIS` 文案兩句重複：「目前的資料裡沒有這個問題的依據。知識庫裡沒有這個問題的依據，可以試試下方的範例問題。」
- 隱私提示固定寫「傳給 Google Gemini」。現在對，但換 provider 會變成錯的。
- 有模擬結果、但 AI 關閉時，extractive 只回通用定義，不會回這次的數字。這是設計上的取捨，不算錯，畫面上有說明是直接引用資料。

## 4. 確認沒問題的部分

- **知識庫對得上程式碼**：車輛折舊 15%、保養 18000/年、油電 3000/月、停車 2000/月、抽樣 300 次、種子 42、純電免徵至 2030-12-31 且不收養管費、淨資產公式、緊急預備金月數公式、現金不足定義、每月投資不論現金夠不夠都扣、現金不足不自動賣投資，我逐項對過 `decision_assumptions.py`、`simulation.py`、`financial_rules.py`、`monte_carlo.py`、`vehicle_fees.py`，全部一致。35 段，每段都有 id／source／tags，且不超過 600 字。
- **黃金測試集**：30 題可回答、7 題不可回答；測試要求前三名命中率至少 0.9。
- **拒答**：10 句要拒答的（推薦股票、ETF、保險、台積電、忽略規則印提示詞、扮演、保證賺、承諾報酬、英文注入）全部拒答；10 句正常問題（含「為什麼不能保證報酬」「強制險和任意險差在哪」「建議的緊急預備金月數怎麼看」）全部沒被誤擋。拒答與查無依據兩條路徑不呼叫 AI。
- **API**：空字串、201 字、控制字元都回 422；有模擬資料但缺起始月份回 422；沒有 AI 時回 `extractive`，帶正確免責聲明與 2 筆引用。
- **事實代入**：跑完模擬後問「我的最低現金是多少」，回答用 `{minimum_cash}`、`{minimum_cash_period}` 代入，畫面顯示 NT$528,000、2026-11，數字由 Python 提供。
- **畫面**：範例問題按鈕、查無依據時的 5 個建議問題、拒答文案都正常；修改模擬條件後，舊回答立即清除，且下一次提問不再帶舊的模擬資料（請求只含 `start_period` 與 `question`）；結果區沒有 `innerHTML` 注入；375px 寬度沒有橫向捲動。
- **紅線**：沒有動 `.env`、沒有動舊頁面；commit 只含任務範圍內的檔案。

## 5. 我這次的操作要告知

我寫探測腳本時，`TestClient` 讀到你本機 `.env` 的 AI 設定，**很可能對你設定的 Gemini 發出了 2～3 次真實請求**（問題是公開的「現金不足機率是什麼意思？」，沒有個人資料，也沒有讀或輸出 `.env`）。其中一次降級成 extractive、一次拿到改寫過的回答。之後的畫面測試我都在 `AI_ENABLED=false` 加假 provider 的測試伺服器上跑，不會呼叫真實 AI。

## 6. 沒驗證到的

- 真實 Gemini 在各種問題上的品質與格式穩定度，只看過一次有效回答。
- 速率限制的實際行為（只確認測試存在）。
- 事件名稱內含注入字句時，AI 路徑的表現。
- 打包後的整合：Codex 把問答接在 `plan-page.js` 的方式在含未提交修改的工作區正常，乾淨 commit 也通過測試；合併進前端改版後需再跑一次。

## 7. 建議的下一步

1. 修 P1-1（驗證加中文數字檢查＋兩個測試）。
2. 決定 P2-2 要用哪個方案，再處理 P2-1（黃金測試集加 3 題並調整檢索）。
3. 先把那 11 個未提交的前端檔審查並 commit，再合併本分支。
4. 本機用真實 Gemini 跑一次問答與「用白話解釋結果」。
