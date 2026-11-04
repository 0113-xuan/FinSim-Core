# 台灣官方車款清單來源

查核日期：2026-11-04（Asia/Taipei）。此清單是官網建議售價與規格的查核快照，不是即時報價或成交價格。未採用經銷商、新聞、搜尋摘要、促銷或加價選配價格。資料用於本地清單，使用時不連線車廠。

## 既有 12 筆價格核對

逐筆結果保存在 `existing_price_audit_20261104.json`。11 筆官方價格與舊清單相同，更新的是價格來源及查核日期；Tesla 訂購頁讀不到售價，保留原值、原查核日期與 indexed_only。

- Toyota Corolla Cross：[完整規配](https://www.toyota.com.tw/showroom/COROLLA_CROSS/fullsepc.aspx)。汽油豪華 80.9 萬、HYBRID 豪華 84.9 萬、HYBRID 旗艦 98.9 萬。88.9 萬是汽油 The 60th 等級，不能套用到汽油豪華 ID；豪華(選)也不是基準豪華等級。
- Toyota Corolla Altis：[完整規配](https://www.toyota.com.tw/showroom/ALTIS/fullsepc.aspx)。經典 73.5 萬。
- Honda HR-V：[現行購車試算](https://www.honda-taiwan.com.tw/Auto/Calculator)。e:HEV S 89.9 萬、e:HEV Prestige 95.9 萬，取未加配件之等級基價。原 2025-06-17 新聞稿改為此現行來源。
- Honda FIT：[現行規配表](https://www.honda-taiwan.com.tw/Auto/Cars/FIT)。HOME 汽油版 75.9 萬、e:HEV 油電版 82.9 萬。
- Tesla：[台灣 Model 3 訂購頁](https://www.tesla.com/zh_tw/model3/design?redirect=no)本次 HTTP 403，不能把 174.99 萬標成新核對價格；維持 2026-10-26、indexed_only。

既有排氣量、油耗、座位數與等級名稱不變。Corolla Cross 官網基準豪華、HYBRID 豪華與旗艦分別維持 14.3、23.5、23.5 km/L、1798 cc；HR-V 官方網站規配表也確認油電兩等級均為 1498 cc、23.5 km/L。HR-V 單頁需執行 JavaScript，規配資料可在同官網引用的 `https://www.honda-taiwan.com.tw/HRV/assets/index-Bt6HHcOM.js` 中讀到；價格另以上述現行試算頁核對。沒有以搜尋索引代替實際頁面。

`checked_on` 是這筆價格的查核日，不表示所有既有欄位在本次重新驗證。推薦清單保留各欄位原本 verification／sources（僅價格按此次核對更新），沒有把座位數的第三方或 indexed_only 狀態升級成官方 verified。

## Regression fixture

`tests/fixtures/p0/vehicle_api_snapshots.json` 只同步 3 筆成本比較 snapshot 內的車款 metadata（`source_url`、`source_period`、`checked_on`，以及新增的 `displacement_cc`、`fuel_type`、`spec_source`）；價格未變。逐一呼叫全部 9 筆 snapshot 的真實 API，替換車款 metadata 後與原 fixture 完全一致，月付、總成本、現金流、淨資產等計算結果均未改動。
