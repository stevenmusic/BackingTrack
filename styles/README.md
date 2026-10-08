# 風格規格 v1(styles/)

依「BackingTrack 風格規格書 v1」產生的資料與事件引擎。**還沒有接到 `index.html`**,網頁的聲音沒有變。

- `styles.json`:9 個風格(pop、mandopop_ballad、jpop、citypop、kpop_dance、kpop_ballad、rnb_neosoul、lofi、reggaeton),
  節奏型字串照規格原樣搬,只多了 `ranges` / `rules` / `optionalSamples` 三個欄位放規格裡用文字寫的規則
- `engine.mjs`:`render(data, styleId, { progression, key, bars, density, bpm, swing, seed, humanize, countIn })`
  → `{ events, plans, meta }`。只產生事件(時間、MIDI 音高、力度),不發聲
- `engine.test.mjs`:規格第 6 節的 7 項驗收 + 級數 ↔ 範例對照、fill / crash / 預備拍。跑法:`node --test styles/engine.test.mjs`

## 規格沒寫死、這裡做的決定
- 和弦進行以**級數**為準(`roman`),`example` 只拿來對照;`mando_4536251` 的級數照範例改成 8 小節(規格的級數少了 `Vsus4` 與第二個 `I`)
- voice leading 整串一起挑(Viterbi):總移動最少,頂音跳進 > 4 只有真的排不出來才會發生(9 風格 × 12 調 × 32 小節實測 0 次)
- `triad_add9` 只用規格的 3-5-9、5-9-3 時,有些調在 low(≤ 69)排不出 ≤ 4 的跳進,所以 9-3-5 當備案(罰分,只有前兩種不行才用)
- `rootless4`:有寫延伸音照寫;屬七往下五度解決到小和弦用 ♭9(E7→Am7);半減和弦用根音取代九度(自然九度在調外、11 度太寬)
- `arp5` 跨 16 半音,43–67 放不下 E、F、F♯ 開頭,第一音往下借到 40–42;sus 和弦的「10」超過 67 時降八度
- 延音碰到換和弦就斷開、在換的那一格重彈新和弦;`N` 只有真的延進下一小節才吃掉下一小節第 0 格
- 貝斯 `8` 超出 48 時,先挑彈得到高八度的根音八度;C♯、D、D♯ 兩個八度都放不下,`8` 會折回同一個音
- City Pop「每個 C 最多延長 2 格」= 每一下最長 3 格,low 的 `C---` 也照這條變短
