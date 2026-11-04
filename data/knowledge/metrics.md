# 計畫頁指標

## 最低現金和發生月份
id: minimum-cash
source: app/core/simulation.py：summarize_simulation；app/services/plan_explanation.py：build_facts
tags: 最低現金,最低存款,發生月份,現金下降

最低現金是模擬期間各個月底的現金餘額中最低的一筆，發生月份則是這筆餘額對應的月份。它不把投資市值或車輛估值當作現金。事件支出、生活費、還款與每月投資都可能影響現金；要問自己的最低金額與月份，須先執行計畫模擬，讓回答取得這次的事實表。

## 緊急預備金月數
id: emergency-months
source: app/core/financial_rules.py：emergency_fund_months；app/core/simulation.py：summarize_simulation
tags: 緊急預備金,必要支出,月數,預備金目標

緊急預備金月數用當月底現金，除以同月生活支出加上債務還款，表示現金大致能支應多久的必要支出。最低緊急預備金月數取整段模擬中最小的覆蓋月數。沒有必要支出時不適用，並不是無限充足；目標月數由使用者設定，也不代表達標後就沒有風險。

## 現金不足機率是什麼
id: cash-shortfall
source: app/core/monte_carlo.py：cash_shortfall_definition、cash_shortfall_count；static/results-model.js：assumptionRows
tags: 現金不足,現金小於零,機率,現金不夠

現金不足機率是在多次隨機模擬中，曾經有任一月底現金小於 0 的試驗比例。一條模擬路徑只要出現過現金不足，就算進這個比例，不是計算負數月份占全部月份的比例。現金不足和淨資產為負是不同的事，投資仍有市值時，手上也可能沒有足夠現金支付支出。

## 淨資產怎麼算
id: net-worth
source: app/core/simulation.py：net_worth = balance + investment + owned_assets - owed_loans - owed_debts
tags: 淨資產,剩餘貸款,投資市值,車輛估值,算法

淨資產等於現金加上投資市值、車輛估值，再扣除模擬內剩餘的新貸款與既有債務餘額。買車後現金會變少，但仍持有車輛，所以現金支出不等於淨資產減少。車輛估值是依折舊假設推算，不是可立即成交的價格；淨資產也不能全部視為可隨時動用的現金。

## 一般、較差和順利情況
id: percentile-cases
source: app/core/monte_carlo.py：percentile、net_worth_percentiles；app/services/plan_explanation.py：build_facts
tags: 一般情況,較差情況,順利情況,中位數,分位數

一般情況是模擬結果的中位數，一半結果較高、一半較低。較差情況約是 20 次裡有 1 次比這低的位置，順利情況約是 20 次裡有 1 次比這高的位置。這些是把抽樣結果排序後整理的位置，不是最壞或最好情況，也不表示你未來會走到其中某一條固定路徑。

## 圖中的淺色與深色範圍
id: percentile-bands
source: static/results-model.js：bandSummaryText；app/core/monte_carlo.py：monthly_bands
tags: 九成,五成,淺色,深色,範圍,圖表

圖上的淺色區域涵蓋中間 9 成的模擬結果，深色區域涵蓋中間最常見的 5 成，實線是正中間的一般情況。每個月的上下邊界是分別整理的，並非某一次模擬真的沿著邊界走過。區域外仍可能有結果，這個範圍也不能解讀成對未來的承諾。

## 今日購買力
id: purchasing-power
source: app/core/monte_carlo.py：price_multiplier、real_net_worths
tags: 今日購買力,實質淨資產,通膨,物價

以今日購買力計算的期末淨資產，是把每次模擬的期末淨資產除以該次累積物價倍數，再整理出結果。這是在說明未來帳面金額扣除物價變化後，相當於今天多少購買能力。它不是另外增加或扣除一筆現金，也不是預測未來實際能購買哪些商品。
