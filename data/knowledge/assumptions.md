# 規劃假設

## 沒填年調薪率會怎樣
id: salary-growth
source: app/core/simulation.py：requested_raise_rate、salary_growth；static/results-model.js：assumptionRows
tags: 年調薪率,薪水成長,沒填,跟著通膨

沒有填年調薪率時，模擬讓薪資跟著通膨，每年調整一次；若有自行指定，就依指定的固定年率處理。這是模型為了規劃而採用的假設，不代表雇主會依物價調薪。進階支出分類也可以有各自的通膨設定，因此不是所有支出都必然和薪水以同樣幅度變動。

## 車輛折舊預設值
id: depreciation-default
source: app/decision_assumptions.py：VEHICLE_DEPRECIATION；app/core/simulation.py：owned_assets
tags: 折舊率,預設折舊,車輛價值,百分之十五

計畫頁的車輛年折舊率預設為 15%，這是可修改的規劃假設，不是從中古車成交資料校準的價格。折舊用來推算持有車輛的估值變化，會影響淨資產與經濟成本；它本身不是每月額外扣款。實際出售價格仍會受車況與市場條件影響，工具不提供成交價預測。

## 保養與油電預算
id: running-cost-defaults
source: app/decision_assumptions.py：ASSUMPTIONS.annual_maintenance_budget、monthly_fuel_or_energy
tags: 保養,油電,預設值,持有成本,預算

未自行填入持有成本時，保養預算預設每年 18000 元，油電預算預設每月 3000 元。這些是讓計算能開始的規劃預算，不是實際保養單或加油、充電報價，也不會因為選了純電車就自動估出充電費。使用者可以依自己的里程、車況與實際費用修改。

## 現金不足不會自動賣投資
id: no-auto-sell
source: app/core/simulation.py：investment、net_cashflow；static/results-model.js：assumptionRows
tags: 自動賣出,現金不足,投資變現,負數

目前模擬把現金和投資分開計算，現金不足時不會自動賣出投資，也不會自動替你借款。因此現金可能變成負數，而投資帳戶仍保有市值。這是在提醒現金流的缺口，並不表示現實中可以無限制透支；若想觀察不同支出或投入安排，需要修改輸入後重新模擬。

## 每月投資從哪裡扣
id: monthly-investment
source: app/core/simulation.py：investment、monthly_investment、net_cashflow
tags: 每月投資,從現金轉入,投資金額,支出

每月投資是把設定的金額從現金轉進投資帳戶，現金流會減少同一筆金額，投資市值則加上投入並受報酬變化影響。它不是憑空增加資產，也不等於生活消費。即使收入扣除生活費與還款後不夠，模型仍照設定投入，所以應一起查看最低現金與現金不足情況。
