# 資料從哪裡來

## 官方車價清單是快照
id: catalog-sources
source: data/vehicles/SOURCES.md；app/vehicle_catalog.py：catalog_list
tags: 官方車款,車價,售價,資料來源,查核日

計畫頁車款清單整理車廠台灣官網的建議售價與規格，每筆保留來源及自己的查核日期。這是離線快照，不是即時報價、優惠價或成交價；查核日也不代表所有欄位都在當天重新驗證。選車可以帶入參考車價，但仍能自行修改，不能把不同等級的售價當成同一款的價格變動。

## 行業薪資的統計對象
id: salary-population
source: data/salary/SOURCES.md：統計對象、統計項；data/salary/tw_regular_salary.json
tags: 行業薪資,主計總處,本國籍,全時,稅前,平均薪資

行業薪資參考來自主計總處受僱員工薪資調查，採本國籍全時受僱員工的稅前平均經常性薪資。不是全體員工、職缺或起薪調查，也不代表雇主或自由接案者收入。這張表沒有提供相同母體的中位數；平均值不能直接當成你的實領薪資，需依自己的實際收入確認。

## 薪資期間與帶入方式
id: salary-period
source: data/salary/SOURCES.md：資料期間、離線重建與欄位；static/salary-reference-form.js
tags: 薪資期間,半年累計,不是起薪,帶入參考值,實領

目前行業薪資快照採半年累計期間的每人每月平均，不是某一個月單月薪資，且屬可能修訂的初步統計。畫面只會在使用者按下帶入參考值後填入，不會自動扣稅或估算起薪。選擇職業或行業沒有對應資料時應顯示沒有參考值，不能把缺資料當成零收入。

## 停車場月租資料來源
id: parking-sources
source: static/parking-form.js；app/parking.py；scripts/fetch_tdx_parking.py
tags: TDX,月租來源,收費說明,解析,停車資料

停車場參考資料來自 TDX，專案從停車場收費說明解析月租方案，並不是每間停車場都提供可辨識的月租。沒有解析到月租不等於免費，也不表示沒有停車場。資料可能含多種方案與適用對象，工具會顯示來源與說明供核對，實際空位與價格仍應向營運單位確認。

## 保險資料不是個人報價
id: insurance-sources
source: app/vehicle_fees.py：COMPULSORY_SOURCE、VOLUNTARY_SOURCE、BODY_SOURCE；static/vehicle-fees-form.js
tags: 保險來源,保費範圍,公開資料,不是報價,車價和保險資料

保險參考混合官方強制險費率表與網路公開投保範例，車體險則依單一範例車款的比例估算。來源與假設會隨項目列出，不是全部都來自官方報價。系統沒有蒐集足以核保的個人條件，參考範圍不能用來宣稱任何人都能以同樣保費投保，實際金額要向保險公司確認。

## 通膨與台股報酬來源
id: market-sources
source: data/market/SOURCES.md；app/core/market_data.py：SOURCES、load_market_history
tags: 通膨資料,台股資料,股利,消費者物價指數,CPI,來源

通膨使用主計總處消費者物價指數，股市使用臺灣證券交易所發行量加權股價報酬指數，後者含股利再投入。執行模擬時只讀專案保存的月資料，取共同期間計算同月的通膨與報酬。資料更新日期不代表即時行情；歷史數值也不能當作未來收入或投資報酬的承諾。
