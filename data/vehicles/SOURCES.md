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

## 新增 26 筆（總數 31 筆）

逐筆價格、排氣量、燃料、油耗及兩種來源網址保存在 `new_vehicle_audit_20261104.json`；均於 2026-11-04 實際讀取官方資料。分類為大眾品牌 15 筆（含既有 5 筆）、入門小車 5 筆、純電 5 筆、豪華 6 筆。豪華品牌另有 2 筆放在純電分類，不重複計數。新車型最多兩等級；既有 Corolla Cross 三等級因 ID 相容性保留。

- Toyota：YARiS CROSS、ALTIS、RAV4、CAMRY、VIOS、bZ4X、URBAN CRUISER 各車型官網的完整規配表（逐筆網址見 JSON），價格與規格同表。RAV4 只取非插電油電版，不取 PHEV；Camry 取汽油最低等級與油電最低等級。
- Honda：FIT 價格與規格同頁；CR-V、Civic、ZR-V 價格來自現行購車試算，規格取該車型官網連出的官方 PDF。PDF 為圖片，實際轉成圖片閱讀末頁規格，未使用搜尋摘要。CR-V VTi-S 為 1498 cc／15.0 km/L；e:HEV S 為 1993 cc／20.5 km/L；Civic 為 1993 cc／23.7 km/L；ZR-V 為 1993 cc／20.4 km/L。
- Kia：Picanto 與 EV6 的台灣官方特色頁逐等級建議售價，並配對同站規格頁。Picanto Trendy、Apex 不含加價選配；EV6 選最低等級 Light 標準版。
- Volvo：台灣 EX30 官方選配器讀到 Core／Single Motor Extended Range 基本售價 1,399,000 元，不加付費車色與其他選配；純電規格另取台灣官方 specifications 頁。
- Lexus：各台灣 showroom 頁的 `window.showroomData` 公開資料列出等級名稱與 ID；同一官方頁引用的 `showroom_2024.js` 透過 `/xml/carspec_xml.ashx?c1=<等級 ID>&typ=1` 讀規格。實際讀取此官方 JSON 的 `010101` 建議售價（萬元）、`010306` 排氣量、`010603` 平均油耗，並核對頁面的欄位順序；各車的 `spec_source` 保留具體等級端點。NX 選 200 最低等級與 350h 最低等級；ES 選 300h 與 500e 各最低等級。500e 引擎與燃油油耗欄為「-」，採純電規格，並非以 0 取代油耗。

純電車的 `efficiency_km_l` 是 null，不提供充電費估算。舊購車頁預設 API 清單排除這些車；計畫頁以 `include_ev=true` 取得全部資料。此改動不修改保險、稅費、持有成本或任何財務計算公式。

## 未加入與選擇範圍

- Tesla Model 3／Model Y：官方訂購頁被阻擋，無法讀到可核對的基準價格，未新增；推薦清單原 Model 3 維持 indexed_only。
- Suzuki Swift：已讀官方型錄（1197 cc／24.5 km/L／輕油電），但本次可讀車型頁未顯示與確切等級對應的基準售價，只見全站「起」價，不以此補出等級價格。入門小車改採官方逐等級價格清楚的 Picanto 兩等級。
- Hyundai INSTER、Suzuki e VITARA：頁面可見起價，但本次未完成基準等級價格的明確對應，未新增；純電名額改採 EX30、ES 500e 等已核對等級。
- Toyota Yaris／Mitsubishi Colt Plus／非 PHEV Outlander，以及 Nissan、Mazda、Ford、BMW、Mercedes-Benz、其他 Hyundai／Kia／Volvo 候選：本次選用上列能完整核對的替代車型，未逐款查核，不能據此判定停售或官網不可讀。
- 未新增 PHEV，未擴充推薦清單。既有規格未發現需要改動的差異；Corolla Cross 88.9 萬屬等級差異，非原汽油豪華價格變更。
