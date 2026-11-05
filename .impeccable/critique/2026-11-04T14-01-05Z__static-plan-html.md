---
target: planner (static/plan.html)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
timestamp: 2026-11-04T14-01-05Z
slug: static-plan-html
---
# Impeccable critique：計畫頁 `static/plan.html`（2026-11-04）

Method: dual-agent（A：設計審查 · B：偵測器與瀏覽器證據，兩者互相隔離，A 完成前 B 的結果不進入綜合）

## 範圍與限制（先讀這段）

- 目標：`static/plan.html`，搭配 `plan-page.js`、`planner-model.js`、`event-picker.js`、`results-model.js`、`explanation-model.js`、`shell.css`、`style.css`。`planner.html` 只是跳到登入頁的轉址頁。
- 計畫頁需要 Supabase 登入，沒有輸入任何帳密。瀏覽器只看到 `/login.html`，**沒有看到真正的計畫畫面、沒有截圖、沒有 375px 手機檢視**。以下設計判斷全部來自原始碼，視覺層級與實際排版需要你登入後目視確認。
- 偵測器為降級模式（HTML 解析模組缺失，改用 regex），結果是低估，不代表乾淨。
- 這次的 `PRODUCT.md` 把「個人財務評估固定 60 個月」寫成產品事實，那是教授會議稿對舊購車頁的描述；計畫頁的期間選項有 60／120／240，需要你確認哪個才是現在的產品事實。

## 設計健康分數：24/40（可接受，需明顯改善）

| # | 啟發式 | 分 | 主要問題 |
|---|---|---|---|
| 1 | 系統狀態可見 | 2 | 「正在計算」寫在頁首 `#pageStatus`（plan.html:13），按鈕在頁底，看不到；整頁 fieldset 被 disabled（shell.js:139），沒有 spinner |
| 2 | 貼近真實世界 | 2 | 「留空使用後端預設」（plan.html:34,35,49）、「Monte Carlo」、「亂數種子」（results-model.js:76,82,88）、「支出為負」（plan.html:21,22） |
| 3 | 使用者控制 | 2 | 一個計畫只能放一個事件（plan-page.js:141-142）且沒說明；刪除只靠 `window.confirm`；改任一欄位結果就消失（:257） |
| 4 | 一致性 | 3 | 外殼與導覽一致；圓角不一（8／9／12／14px）；期間選項 60／120／240 與 PRODUCT.md 的 60 個月描述不一致 |
| 5 | 防錯 | 2 | 月份是純文字 pattern 欄（plan.html:19），沒有 `title`、`inputmode` 或月份選擇器 |
| 6 | 辨識優於回憶 | 3 | 範本卡加圖示、選定後收合、事件摘要清楚 |
| 7 | 彈性與效率 | 2 | 沒有預設情境；核心問題「兩款車差在哪」在這頁做不到 |
| 8 | 美學與極簡 | 2 | 結果 16 張卡（plan.html:84-105）；購車表單最多約 20 欄 |
| 9 | 錯誤復原 | 3 | 白話中文並附修正建議（shell.js:62），但顯示在頁首，使用者看不到 |
| 10 | 說明文件 | 3 | 假設區預設展開，有資料來源與抽樣說明；沒有名詞對照 |
| | **合計** | **24/40** | 60%，Acceptable |

## 設計專屬性判定：可與同類產品互換

- 色票（style.css:2-10）是 Tailwind 預設值（slate、emerald、red），版面是白底圓角卡片加側欄，看不出購車、台灣或「錢包」。
- 有自己個性的只有兩處：事件範本卡的線條圖示（event-picker.js:4-14）和淨資產範圍圖的白話圖例（plan.html:75-77）。

**偵測器（降級模式）**
- HTML（plan、dashboard、profile、onboarding、login）：1 筆 `em-dash-overuse`，在 plan.html。判定為誤報：16 個「—」全是 `<strong>` 的空值 placeholder（plan.html:85-104）。
- `style.css`：5 筆。`side-tab` 在 355（`.scenario-summary-card`，真）、432 與 705（琥珀色提示框，語意為警告，影響較小）；`border-accent-on-rounded` 在 726（`.profile-draft-review`，用於 profile 頁）；`overused-font` 在 20（Inter 配 Noto Sans TC，中文實際顯示 Noto Sans TC）。`shell.css` 0 筆。
- 瀏覽器：能注入偵測腳本的只有 login.html，console 回報 1 筆對比 4.47:1（#64748b 對 #f6f8fb，差 0.03）。兩頁共用 CSS，plan 頁很可能也有，但未驗證。live server 已停止。

## 總評

骨架是誠實的：假設與來源預設展開、圖表有文字替代、AI 說明標示哪些是後端數字。最大的缺口是結果出現的那一刻：使用者按下按鈕，看不到回饋，結果出來後得讀完 16 張同等級的卡片，才可能理解自己的現金會不會不夠。

## 優點

1. **圖表兼顧無障礙**：canvas 有 `role=img` 與 aria-label，另附文字摘要（results-model.js:39-46），線條有虛線樣式，不只靠顏色。
2. **誠實度設計**：範圍圖用「9 成／5 成」白話說明；假設與資料來源預設展開；AI 說明用 `<strong title>` 標示後端事實（explanation-model.js:20）。
3. **外殼與鍵盤**：skip-link、抽屜 `inert` 與焦點陷阱（shell.js:205-218）、`:focus-visible` 都有。

## 優先問題

1. **[P1] 結果沒有「答案優先」層級**
   - 為什麼重要：這是最高風險的時刻。16 張同字級卡片，「現金不足機率」排第 6，使用者得捲到底按「用白話解釋結果」才有人話。違反 PRODUCT.md 原則 5。結果區也沒有明講「這不是預測或保證」。
   - 修法：結果區最上方放一張結論卡：「最低現金 X，發生在 YYYY-MM；現金不足機率 Y%」加一句限制說明。其餘數字摺疊。
   - 建議指令：`/impeccable clarify`，再 `/impeccable layout`
2. **[P1] 計算狀態與錯誤離使用者太遠**
   - 為什麼重要：按鈕在頁底，回饋在頁首；整頁 disabled 讓焦點掉到 body，螢幕閱讀器使用者尤其受影響。
   - 修法：在按鈕旁放 `role=status` 行內狀態與 spinner；成功後把焦點移到結果標題；不要把整頁灰掉。
   - 建議指令：`/impeccable harden`
3. **[P1] 工程用語外露**
   - 為什麼重要：違反「白話」原則，目標使用者是一般民眾。
   - 修法：「後端預設」改「系統預設值」；「Monte Carlo」改成「N 次隨機模擬」；移除「亂數種子」或收進進階；「支出為負」改成收入／支出選項。
   - 建議指令：`/impeccable clarify`
4. **[P2] 視覺語彙是範本風格，層級太平**
   - 為什麼重要：口試評審認不出專屬性；數字沒有主角。label 12px 全部加粗（style.css:293）。
   - 修法：定義一個主角數字級距；label 改一般字重；統一圓角；給購車情境一個辨識元素；處理 4 處 side-tab／粗邊與對比 4.47:1。
   - 建議指令：`/impeccable typeset`，再 `/impeccable bolder`
5. **[P2] 選項過載與產品說法不一致**
   - 為什麼重要：10 張範本卡中 6 張「即將推出」（event-templates.js:6-11）；購車表單約 20 欄；一計畫一事件與「事件時間軸」、「雙車比較」的說法矛盾；期間 120／240 與 PRODUCT.md 的 60 個月不一致。
   - 修法：「即將推出」收成一行說明；購車表單分步；統一期間說法。
   - 建議指令：`/impeccable distill`，再 `/impeccable shape`

## 認知負荷：8 項中 5 項失敗（危急）

- 失敗：單一焦點、分塊（「現金」群組 9 張卡）、視覺層級、一次一件事（購車表單約 20 欄）、最少選項（範本 10 張卡）。
- 通過：分組、工作記憶、漸進揭露。

## 情緒旅程

按下「執行模擬」→ 頁首變「正在計算…」但使用者看的是頁底 → 結果出現但頁面不捲動、焦點不移動 → 先看到圖，不是結論 → 要自己找出最重要的數字。結尾沒有安心或下一步。「可以考慮」建議區（explanation-model.js:35）接近 PRODUCT.md 禁止的個人化建議，需確認後端措辭。傳資料給 Gemini 的告知只在按鈕下方小字（plan.html:118）。

## 人物紅旗

- **Jordan（第一次使用）**：開頭一段長文塞滿術語（plan.html:68）；看不懂 YYYY-MM 的錯誤；結果沒有第一句結論。
- **Sam（無障礙）**：`perform` 把按鈕 disabled，焦點掉到 body；多個 `aria-live` 同時更新（`pageStatus`、`explanationResult`、`insuranceTotal`）；16 張卡是 span 加 strong，沒有語意關聯；muted 文字約 4.4:1（偵測器在 login 頁實測 4.47:1）。
- **Casey（手機）**：按鈕 `min-height: 40px`，低於 44px（style.css:25）；月份欄沒有原生月份選擇器；375px 下 16 張卡接近一個螢幕一張（未實測）。
- **阿美（45 歲、想買 Toyota、不懂財務）**：不知道排氣量、折舊、利率要填什麼，沒有預填或「我不確定」；看到「現金不足機率 3%」不知道怎麼解讀。

## 次要觀察

- plan.html 沒載入字型，Inter／Noto Sans TC 靠使用者本機字型（只有 index.html 載入 Google Fonts）。
- 第一個 fieldset（plan.html:14）沒有 legend。
- 「車輛估值」與「經濟成本」的差異對一般人不直覺。
- 車價來源日期在購車表單中看不到；vehicle-fees-form.js:14 只連結原廠規格。

## 值得思考的問題

1. 口試評審只給 10 秒，這頁要他看到哪一個數字、哪一句話？
2. 一個計畫只能放一個事件，「事件時間軸」與「兩款車比較」要在哪裡實現？
3. 如果一個陌生人看不到任何「購車」或「台灣」字樣，還能認出這是 FutureWallet 嗎？

## 建議的修復順序（距功能凍結 2026-11-15 剩 11 天）

1. 結論卡 + 計算狀態就地顯示（問題 1、2，影響最大、檔案集中在 plan.html／plan-page.js／results-model.js）
2. 工程用語改白話（問題 3，純文案，風險最低）
3. 視覺層級與 4 處粗邊、對比（問題 4）
4. 選項過載與期間說法（問題 5，需先決定產品說法）
