# 購車事件

## 現金購買與貸款
id: vehicle-payment
source: app/services/planner_vehicle.py：convert_vehicle_events；static/plan-page.js：購車摘要
tags: 現金購買,車貸,頭期款,貸款,購車當月

現金購買會在購車當月安排車價的一次支出；貸款購買則先支付頭期款，後續按期還車貸，並計入持有成本。計畫頁會顯示購車當月一次支出、每月車貸與總利息。應同時查看購車月份的現金和之後的每月負擔，不能只憑月付較低就判斷整個計畫沒有壓力。

## 現金負擔和經濟成本
id: cash-vs-economic
source: static/plan.html：購車說明；app/services/planner_vehicle.py：NOTE
tags: 現金負擔,經濟成本,折舊,重複計算

購車一次支出、車貸與持有費用是要實際安排的現金負擔；經濟成本則用價值減少與相關費用理解用車的耗用。車輛折舊不是另一筆現金支出，不能把經濟成本再加進現金流扣一次。看支付能力時重點是現金何時需要支出，看資產變化時則要把車輛估值與剩餘貸款一起考慮。

## 車輛估值怎麼算
id: vehicle-value
source: app/core/balance_sheet.py：asset_value；app/services/planner_vehicle.py：assets
tags: 車輛估值,車齡,價值減少,中古車

車輛估值依購買價格、購車後經過時間與設定的年折舊率推算，車輛尚未買入時不算持有資產。估值納入淨資產，但不會變成現金，也不會因為估值降低就自動賣車。這是規劃用的資產模型，沒有根據個別中古車車況、里程或成交資訊提供報價。

## 強制險與任意險
id: vehicle-insurance
source: app/vehicle_fees.py：insurance_reference、COMPULSORY_SOURCE、VOLUNTARY_SOURCE、BODY_SOURCE
tags: 強制險,任意險,車體險,保險,第三人

強制汽車責任保險依法必保，其他項目由使用者依需求勾選。工具提供強制險費率參考、第三人與超額責任等公開投保範例，以及按單一車款比例估算的車體險預算。這些內容用途是安排費用，不會替你挑保險商品，也不能取代保險公司依個人條件給的報價與承保說明。

## 牌照稅與公路養管費
id: vehicle-tax
source: app/vehicle_fees.py：annual_vehicle_tax、LICENSE_TAX_BANDS、ROAD_FEE_BANDS
tags: 牌照稅,公路養管費,汽燃費,排氣量,柴油

燃油自用小客車的全年牌照稅與公路養管費，依排氣量與燃料種類查對專案整理的級距。油電混合與汽油車適用相同級距，柴油的公路養管費另有欄位。查不到官方費額時需要手動填寫，不能當作免收；畫面上的預算或自訂金額，也不能取代主管機關的實際核定。

## 純電車免徵的限制
id: ev-exemption
source: app/vehicle_fees.py：annual_vehicle_tax 的純電車 notes（查核快照 2026-11-02）
tags: 電動車,純電,免徵,免稅期限,養管費

依專案目前的查核快照，純電車使用牌照稅免徵至 2030-12-31，期限之後需要重新確認，並非永久免稅。純電車目前不收公路養管費；程式註記未來徵收仍屬規劃，沒有已生效的費額。現有計算不會自動按免徵到期切換稅額，長期模擬要注意這個限制並自行確認當時規定。

## 停車費參考怎麼用
id: parking-budget
source: app/decision_assumptions.py：ASSUMPTIONS.monthly_parking；static/parking-form.js
tags: 停車費,停車預算,月租,停車場

停車費可以自己填，也可以查看附近停車場月租參考，再決定是否帶入。未自行指定時，系統有每月 2000 元的規劃預算，這不是所在地的平均行情。月租方案可能有限制、額滿或不是適合汽車的方案；應先看收費說明，再向停車場確認能否實際申租與目前價格。
