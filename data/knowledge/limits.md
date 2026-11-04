# 工具的界線

## 不提供投資商品推薦
id: no-investment-advice
source: README.md：deterministic backend engine；app/prompts/plan_qa.md：商品限制
tags: 投資建議,推薦股票,基金,保險商品,財務建議

這個工具用來理解生活決策的現金流與風險，不提供特定股票、基金或保險商品的推薦，也不代替專業財務建議。問答只能說明專案整理的知識與已計算的計畫事實，不能因為使用者要求就替商品背書，或把模擬結果變成買賣指示。實際決策仍要確認自己的條件與資料限制。

## 為什麼不能承諾報酬
id: no-guaranteed-return
source: app/core/monte_carlo.py：PAST_PERFORMANCE_WARNING；README.md：platform purpose
tags: 保證報酬,不能保證,一定賺,承諾,投資風險

工具不能保證報酬，因為計算只是根據已整理的歷史資料與模型假設推演，未來條件可能超出這些資料。看到較好的模擬結果不代表投入後就一定賺，較差情況也不是損失的下限。可以問指標怎麼定義、假設從哪來與目前計畫的計算結果，但無法要求系統承諾收益。

## 不含個人稅務規劃
id: no-tax-planning
source: app/core/simulation.py：income、total_expense；data/salary/SOURCES.md：稅前與實領差異
tags: 稅務規劃,所得稅,扣稅,稅後薪水

模擬以使用者輸入的收入與支出進行計算，沒有依個人申報條件自動處理所得稅或扣除額，也沒有把行業的稅前參考薪資轉成稅後實領。車輛稅費的級距參考不等於完整個人稅務規劃；需要反映自己的實際稅負時，應先確認數字，再調整對應收入與支出輸入。

## 職業不會調整貸款利率
id: occupation-and-rate
source: data/salary/SOURCES.md：職業與行業不調整貸款利率；static/planner-model.js：vehicleDetails
tags: 職業,行業,貸款利率,信用評分,銀行

選擇職業或行業只影響資料紀錄與可查看的薪資參考，不會改變車貸利率，也不是銀行信用評分。貸款計算使用輸入的利率、頭期款與期數，沒有向銀行取得個人審核結果。因此顯示的月付與總利息是試算，不能視為金融機構已同意提供的貸款條件。
