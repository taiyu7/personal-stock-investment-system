
`TODO.md`

```md
# TODO

## Phase 1：建立本機 MVP

- [ ] 建立 Python 虛擬環境
- [ ] 建立 requirements.txt
- [ ] 安裝 streamlit、pandas、yfinance
- [ ] 建立 app.py
- [ ] 建立 config/watchlist.py
- [ ] 建立 services/market_data.py
- [ ] 串接 yfinance
- [ ] 顯示前日國際市況
- [ ] 顯示美股 AI 指標股
- [ ] 顯示總經市況
- [ ] 顯示台股相關資料
- [ ] 自動計算漲跌與漲跌幅
- [ ] 加入簡單結論文字

## Phase 2：改善資料可靠度

- [ ] 檢查 yfinance 對 SOX、DXY、美債 10 年、台指期的代號是否正確
- [ ] 若資料抓不到，改用替代代號或其他資料源
- [ ] 加入錯誤提示
- [ ] 加入資料更新時間
- [ ] 加入快取，避免重複抓資料

## Phase 3：結論規則強化

- [ ] 將結論邏輯抽到獨立檔案
- [ ] 加入多空分數
- [ ] 加入「偏多 / 中性 / 偏空」判斷
- [ ] 加入隔日台股觀察重點

## Phase 4：未來擴充

- [ ] 加入外資台指期未平倉
- [ ] 加入台股漲跌家數
- [ ] 加入台股主流族群
- [ ] 加入財經 M 平方資料人工紀錄區
- [ ] 加入每日盤前筆記輸出
- [ ] 考慮部署到 Streamlit Community Cloud