# 名詞解釋

## 蒙地卡羅模擬是什麼
id: monte-carlo-term
source: app/core/monte_carlo.py：run_monte_carlo；app/core/simulation.py：simulate_finance
tags: 蒙地卡羅,蒙特卡羅,Monte Carlo,隨機模擬,模擬路徑,抽樣,名詞解釋

蒙地卡羅模擬是把同一份計畫重複算很多次，每一次都用不同的通膨與投資報酬走法，再把全部結果整理成一個分布來看。一次從第一個月走到最後一個月的結果叫一條模擬路徑。計畫頁抽 300 條路徑，再整理出現金不足的比例與淨資產的範圍。它回答的是「可能落在哪個範圍」，不是「未來會是多少」；每條路徑的通膨與報酬取自台灣歷史資料。

## 區塊抽樣是什麼
id: block-bootstrap
source: app/core/market_data.py：BLOCK_MONTHS、block_bootstrap_indices
tags: 區塊抽樣,bootstrap,歷史資料,連續月份,名詞解釋

區塊抽樣是把歷史月資料切成連續 12 個月的區塊，再隨機挑區塊接成一條模擬期間的路徑，而不是把每個月打散亂抽。這樣一段時間內通膨與股市一起變動的關係會被保留下來。限制是只能重組歷史上出現過的情況，歷史沒有發生過的變化不會出現在結果裡。

## 通貨膨脹（通膨）是什麼
id: inflation-term
source: app/core/monte_carlo.py：inflation_path、real_net_worths；app/core/market_data.py：load_market_history
tags: 通貨膨脹,通膨,物價上漲,消費者物價指數,CPI,名詞解釋

通貨膨脹是整體物價上漲，同樣的金額能買到的東西變少。這個工具用主計總處消費者物價指數的歷史月資料推算通膨；使用者自己填固定通膨率時，通膨就不再抽樣。沒有指定年調薪率時，薪資會跟著通膨調整，部分支出分類也會跟著物價變動。

## 年化報酬率是什麼
id: annualized-return
source: app/core/market_data.py：_annualized、load_market_history
tags: 年化報酬率,年化,平均報酬,複合,每年成長,名詞解釋

年化報酬率是把一段期間的總成長換算成「平均每年成長多少」。這個工具把共同歷史期間指數的頭尾相比，再換算成每年的複利成長率，用在沒有自行指定時的確定性模擬。它是長期平均，不代表每一年都會是這個數字，也不代表未來會重複。

## 複利是什麼
id: compound-term
source: app/core/simulation.py：investment；app/core/events.py：calculate_loan_payment
tags: 複利,利滾利,投資市值,滾動,月利率,名詞解釋

複利是上一期的報酬併入本金，下一期連同報酬一起再計算。模擬裡投資市值每個月先乘上當月報酬，再加入當月投入，所以早期的投入會被後續報酬重複放大，市值下跌時同樣會被放大。貸款則是用月利率對剩餘本金逐期計息，這是複利在貸款上的樣子。

## 現金流是什麼
id: cash-flow-term
source: app/core/simulation.py：net_cashflow
tags: 現金流,收支,每月結餘,現金餘額,進出,名詞解釋

現金流是每個月實際進出的現金。進來的有收入與事件收入，出去的有生活費、債務還款、事件支出與每月投資，相減後就是當月現金流。每個月的現金流累積起來，就是現金餘額。現金流為負不等於資產變少：每月投資是把現金轉進投資帳戶，現金會減少，淨資產不一定減少。

## 頭期款與貸款本金
id: down-payment-term
source: app/services/scenario_engine.py：貸款本金；app/core/events.py：calculate_loan_payment
tags: 頭期款,貸款本金,車價,自備款,貸款金額,名詞解釋

頭期款是購車時先付的現金；車價扣掉頭期款後的餘額，才是向銀行借的貸款本金。月付與利息都是依貸款本金、年利率和期數計算，所以頭期款付得越多，借的本金越少，每月還款與總利息也越少，但購車當月的現金支出會越大。

## 折舊是什麼
id: depreciation-term
source: app/core/balance_sheet.py：asset_value；app/decision_assumptions.py：VEHICLE_DEPRECIATION
tags: 折舊,資產價值減少,遞減,車價下降,名詞解釋

折舊是資產的價值隨時間減少。這個工具用固定的年折舊率逐期遞減：每經過一年，價值變成上一期的固定比例，所以前面幾年掉得多，之後金額逐漸變小。購買當月還沒持有，價值是原價。折舊不是現金支出，它只讓車輛估值下降，進而影響淨資產。

## 既有債務怎麼算
id: existing-debt-term
source: app/core/balance_sheet.py：existing_debt_balance
tags: 既有債務,學貸,每月還款,剩餘月數,負債,名詞解釋

既有債務是計畫開始前就已經有的負債，例如學貸。填入每月還款金額與剩餘月數後，模擬會逐月扣款，直到還完。淨資產扣掉的債務餘額，是把「剩餘月數乘以每月還款」加總的未折現金額，並不是銀行帳上的剩餘本金，利息已包含在內但不另外顯示。

## 報酬指數是什麼
id: total-return-index
source: data/market/SOURCES.md：發行量加權股價報酬指數；app/core/market_data.py：SOURCES
tags: 報酬指數,股價指數,股利再投入,總報酬,台股,名詞解釋

報酬指數是假設領到的現金股利會再投入的指數，一般的股價指數則只反映價格變動。這個工具的台股資料使用含股利再投入的報酬指數，因此比較接近長期持有的成果。它是整個市場的歷史表現，不是任何單一股票、基金的報酬，也不代表未來。
