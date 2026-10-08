# 風格規格 v1(styles/)

依「BackingTrack 風格規格書 v1」產生的資料、事件引擎與**真實取樣**播放器。
試聽頁是 `styles/index.html`(GitHub Pages 上的 `/styles/`);主網頁 `index.html` 還沒換。

- `styles.json`:9 個風格(pop、mandopop_ballad、jpop、citypop、kpop_dance、kpop_ballad、rnb_neosoul、lofi、reggaeton),
  節奏型字串照規格原樣搬,只多了 `ranges` / `rules` / `optionalSamples` 三個欄位放規格裡用文字寫的規則
- `engine.mjs`:`render(data, styleId, { progression, key, bars, density, bpm, swing, seed, humanize, countIn })`
  → `{ events, plans, meta }`。只產生事件(時間、MIDI 音高、力度),不發聲
- `samples.json`:取樣清單,由 `tools/samples/build_manifest.py` 從各取樣庫的**實際檔案列表**產生(不照公式推檔名)
- `sampler.mjs`:取樣樂器(力度層、round robin、開放 hi-hat 被閉合 hi-hat 掐掉)
- `player.mjs`:即時播放(`currentTime` 提前 0.2 秒排)與 `renderOffline()`(離線算成音檔)
- `index.html`:試聽頁(風格、進行或自己輸入和弦、調、密度、速度、可選聲部)
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

## 樂器(全部是錄音取樣,沒有即時合成)
| 樂器 | 取樣庫 | 用在 |
| --- | --- | --- |
| 平台鋼琴 | Salamander Grand Piano V3,16 層力度取 5 層 | pop、華語、K-pop 抒情、J-pop、lofi、K-pop 舞曲、reggaeton |
| 電鋼琴 | jRhodes3c,5 層力度(照原作者 sfz) | City Pop、R&B(**非商用授權,上架前要換**) |
| 原聲鼓 | Virtuosity Drums 近麥,多力度層 × round robin | 電子鼓以外全部 |
| 電子鼓 | TR-808 實機取樣(Dirt-Samples) | K-pop 舞曲、reggaeton |
| 電貝斯 | Black And Blue Basses darkblack,4 層力度 × 4 round robin,半音一個取樣 | 全部 |
| 弦樂 | VSCO-2-CE 小提琴 / 中提琴 / 大提琴聲部 | 鋪底(pad) |
| 乾淨電吉他 | Black And Green Guitars green staccato | City Pop 切音(high,可關) |

規格裡寫「合成」的部分改成真樂器(Steven 2026-10-08:「合成音色一定要換成真實取樣樂器,否則就乾脆不要」):
- K-pop 舞曲的 pluck → 平台鋼琴短音;pad → 弦樂;synth bass → 電貝斯
- reggaeton 的 synth bass → 電貝斯
- lofi 的黑膠底噪:找不到授權清楚的錄音,**拿掉**(低通、音高飄移是效果,保留)

混音只做到「聽得清楚、不削波」(各軌音量、殘響送出、−3dB 的保險壓縮),母帶之後再做。

## 量測
`node tools/samples/render_styles.mjs <輸出資料夾> style[:進行[:密度[:小節[:只算哪幾軌]]]] ...`
用無頭 Chromium 離線算成 WAV、印 peak / RMS;取樣從 `/tmp/smp` 的 blobless clone 現抓(先照 `tools/samples/build_manifest.py` 開頭的說明 clone)。
需要 playwright:`ln -s /opt/node-tools/node_modules tools/samples/node_modules`(已在 .gitignore)
