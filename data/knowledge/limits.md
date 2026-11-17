# 工具的界線

## 不提供投資商品推薦
id: no-investment-advice
source: README.md：deterministic backend engine；app/prompts/plan_qa.md：商品限制
tags: 投資建議,推薦股票,基金,保險商品,財務建議
aliases: 為什麼不推薦股票,可以推薦基金嗎,能不能給投資建議

這個工具用來理解生活決策的現金流與風險，不提供特定股票、基金或保險商品的推薦，也不代替專業財務建議。問答只能說明專案整理的知識與已計算的計畫事實，不能因為使用者要求就替商品背書，或把模擬結果變成買賣指示。實際決策仍要確認自己的條件與資料限制。

## 為什麼不能承諾報酬
id: no-guaranteed-return
source: app/core/monte_carlo.py：PAST_PERFORMANCE_WARNING；README.md：platform purpose
tags: 保證報酬,不能保證,一定賺,承諾,投資風險
aliases: 一定賺嗎,會不會賺錢,能保證獲利嗎

工具不能保證報酬，因為計算只是根據已整理的歷史資料與模型假設推演，未來條件可能超出這些資料。看到較好的模擬結果不代表投入後就一定賺，較差情況也不是損失的下限。可以問指標怎麼定義、假設從哪來與目前計畫的計算結果，但無法要求系統承諾收益。

## 不含個人稅務規劃
id: no-tax-planning
source: app/core/simulation.py：income、total_expense；data/salary/SOURCES.md：稅前與實領差異
tags: 稅務規劃,所得稅,扣稅,稅後薪水
aliases: 要扣稅嗎,稅後薪水,所得稅怎麼算,實領多少

模擬以使用者輸入的收入與支出進行計算，沒有依個人申報條件自動處理所得稅或扣除額，也沒有把行業的稅前參考薪資轉成稅後實領。車輛稅費的級距參考不等於完整個人稅務規劃；需要反映自己的實際稅負時，應先確認數字，再調整對應收入與支出輸入。

## 職業不會調整貸款利率
id: occupation-and-rate
source: data/salary/SOURCES.md：職業與行業不調整貸款利率；static/planner-model.js：vehicleDetails
tags: 職業,行業,貸款利率,信用評分,銀行
aliases: 職業影響利率嗎,行業會影響貸款嗎,工作會影響利率

選擇職業或行業只影響資料紀錄與可查看的薪資參考，不會改變車貸利率，也不是銀行信用評分。貸款計算使用輸入的利率、頭期款與期數，沒有向銀行取得個人審核結果。因此顯示的月付與總利息是試算，不能視為金融機構已同意提供的貸款條件。


## 隨機取樣次數與結果誤差
id: mc-sampling-error
source: app/core/mc_uncertainty.py：Wilson 區間與分位數區間；app/core/monte_carlo.py：隨機取樣結果
tags: 隨機取樣誤差,模擬次數,亂數種子,信賴區間
aliases: 結果準不準,換種子結果會變嗎,模擬次數有影響嗎

Monte Carlo 只抽取有限次試驗，同一個方案換一個亂數種子重新計算，結果可能有小幅差異；增加試驗次數通常能讓估計更穩定。顯示的區間只反映有限隨機取樣帶來的誤差，並不涵蓋模型假設、歷史資料或未來環境與過去不同所造成的不確定性。區間不能保證實際結果一定落在其中。

## 歷史資料的長度與限制
id: history-length
source: app/core/market_data.py：load_market_history；app/core/monte_carlo.py：歷史表現警語
tags: 歷史資料,資料長度,樣本有限,歷史報酬
aliases: 歷史資料有多久,歷史樣本夠嗎,過去表現可以代表未來嗎

配對後可供隨機取樣的歷史月資料為 2003-02 至 2026-09，共 284 個月，約有 23 個互不重疊的 12 個月區塊。雖然區塊隨機取樣可重複組合，原始資料仍然有限，無法包含所有可能的未來情境。這段期間台股表現偏好，過去的報酬不代表未來，也不應把模擬範圍視為實際風險的上下限。

## 意外事件與市場的獨立假設
id: independence-assumption
source: app/core/monte_carlo.py：歷史區塊隨機取樣；app/core/simulation.py：意外事件模擬
tags: 獨立假設,通膨報酬,意外事件,風險連動
aliases: 景氣差會更容易失業嗎,市場與意外會連動嗎,風險會不會被低估

模型將同一歷史月份的通膨與市場報酬成對隨機取樣，但醫療、車禍或收入中斷等意外事件與市場隨機取樣各自獨立。它沒有模擬景氣差時更容易失業等連動關係，也沒有涵蓋所有事件同時發生的方式；如果真實世界中的風險彼此相關，模型可能低估不利情況。
