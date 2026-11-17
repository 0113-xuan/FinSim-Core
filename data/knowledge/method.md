# 模擬方法

## 為什麼要用模擬
id: why-simulate
source: README.md：backend engine；app/core/simulation.py：simulate_finance；app/core/monte_carlo.py：run_monte_carlo
tags: 模擬用途,未來,風險,現金流
aliases: 模擬原因,模擬用途,不直接算,做模擬用途

計畫把收入、生活費、還款、投資與事件逐月放進同一套現金流計算，觀察現金何時較吃緊。隨機模擬再加入歷史資料抽樣，看看不同通膨與股市變化下結果有多分散。用途是比較自己填入的條件與風險，不是由系統替你決定是否購車，或判斷未來一定會發生什麼。

## 計畫頁抽樣幾次
id: simulation-count
source: static/plan-page.js：/monte-carlo 請求；app/services/plan_explanation.py：MONTE_CARLO_SIMULATIONS
tags: 抽樣,幾次,次數,三百,Monte Carlo
aliases: 跑幾次,模擬幾次,要跑幾次才夠,跑五百次

計畫頁會抽樣 500 種可能的未來，逐次計算現金流，再整理現金不足比例與淨資產範圍。這個次數是目前計畫頁與白話解釋使用的設定，不是所有後端呼叫的通用預設值。抽樣更多也不會讓模擬變成預測；結果仍受資料期間、輸入與模型假設限制。

## 台灣歷史資料怎麼抽樣
id: historical-sampling
source: app/core/market_data.py：BLOCK_MONTHS、block_bootstrap_indices；app/core/monte_carlo.py：_sampling_metadata
tags: 歷史抽樣,通膨,台股報酬,區塊,十二個月
aliases: 抽歷史資料,通膨報酬配對,歷史資料多久

隨機模擬以台灣歷史月資料為基礎，每次取連續 12 個月為一個區塊，同月份的通膨與台股報酬成對抽取，接成模擬期間。若自己填固定通膨率，通膨就不抽樣；投資報酬仍依歷史資料抽樣。這是在保留部分歷史連動的規劃方法，不能涵蓋所有未來可能出現的市場情境。

## 確定性模擬和隨機模擬
id: deterministic-vs-mc
source: app/core/simulation.py：simulate_finance；app/core/monte_carlo.py：run_monte_carlo；static/results-model.js：assumptionRows
tags: 確定性,Monte Carlo,固定值,差別,隨機
aliases: 固定和隨機差在哪,兩種模擬差別,固定值模擬

確定性模擬的通膨與投資報酬使用固定值，方便看資金如何逐月移動；沒有自行指定時，相關值取自共同歷史期間的年化平均。Monte Carlo 則用歷史區塊抽樣產生多種路徑。自行設定的預期年報酬率只影響確定性模擬，不會取代 Monte Carlo 的歷史報酬抽樣。

## 為什麼每次結果相同
id: fixed-seed
source: static/plan-page.js：seed；app/services/plan_explanation.py：SIMULATE_SEED、MONTE_CARLO_SEED
tags: 固定種子,亂數,重跑,相同,四十二
aliases: 結果一樣,每次都一樣,結果不會變,重跑結果相同,重新整理,數字沒變

計畫頁與白話解釋把亂數種子固定為 42，讓相同輸入、資料與程式版本重跑時取得相同結果，便於比較與查核。固定種子只是讓抽樣過程可以重現，沒有挑出比較有利的未來。修改收入、事件、模擬期間或資料版本後，結果仍可能不同。

## 模擬不是預測
id: not-prediction
source: app/core/monte_carlo.py：PAST_PERFORMANCE_WARNING；README.md：deterministic backend engine
tags: 不是預測,預測未來,過去報酬,可靠性,風險
aliases: 準不準,可不可靠,可以相信嗎,是預測嗎,準確嗎,模擬準確,數字可信嗎

模擬結果是把目前輸入放進既定模型與歷史抽樣方法後算出的可能情況，不是在預測實際未來。歷史期間台股表現特別好，過去報酬不代表未來；未來也可能遇到歷史資料沒有包含的變化。因此結果適合用來理解條件與風險，不能當成未來資產或報酬的承諾。
