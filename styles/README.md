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
| 電鋼琴 | jRhodes3d 完整長度立體聲版,5 層力度(照原作者 sfz) | City Pop、R&B(非商用授權;免費網站可用) |
| 原聲鼓 | Virtuosity Drums 近麥,多力度層 × round robin | 電子鼓以外全部 |
| 電子鼓 | TR-808 實機取樣(Dirt-Samples) | K-pop 舞曲、reggaeton |
| 電貝斯 | Black And Blue Basses darkblack,4 層力度 × 4 round robin,半音一個取樣 | 全部 |
| 弦樂 | VSCO-2-CE 小提琴 / 中提琴 / 大提琴聲部 | 鋪底(pad) |
| 乾淨電吉他 | Black And Green Guitars green staccato | City Pop 切音(high,可關) |
| 破音吉他 | Emilyguitar 乾聲(DI)→ 音箱模擬(re-amp) | J-pop high power chord(可選,預設關) |
| slap 貝斯 | Project16 Rickenbacker 4001 Slap1 + Slap2(兩組當 round robin) | City Pop high(可選,預設關) |
| 低音提琴 | Meatbass pizz,4 層力度 × 4 round robin | Lo-fi(可選,預設關) |
| 尼龍吉他 | Philharmonia 古典吉他(ScrollScore 處理版),每個半音、2 層力度 | Reggaeton(可選,取代鋼琴) |
| 黑膠底噪 | Record Fuzzies(CC0 唱片底噪錄音),−30dB 循環 | Lo-fi(可關) |

取樣夠不夠(Steven 2026-10-08:「只要取樣數量太少,就不要用」):`tools/samples/audit.py`。
Rhodes 是唯一例外(每 4 個白鍵一個取樣):量過移調 3 半音的泛音差 4.8–7.1 dB,跟鋼琴移調 3 半音(5.2–8.0 dB)差不多,
但鋼琴實際最多只移 1.5 半音,所以 F4–B4 之間的 Rhodes 會比鋼琴差一點;要完全解決只能委託錄音

規格裡寫「合成」的部分改成真樂器(Steven 2026-10-08:「合成音色一定要換成真實取樣樂器,否則就乾脆不要」):
- K-pop 舞曲的 pluck → 平台鋼琴短音;pad → 弦樂;synth bass → 電貝斯
- reggaeton 的 synth bass → 電貝斯
- lofi 的黑膠底噪:2026-10-08 找到 CC0 的唱片底噪錄音,加回來(可關)

混音只做到「聽得清楚、不削波」(各軌音量、殘響送出、−3dB 的保險壓縮),母帶之後再做。

## 量測
`node tools/samples/render_styles.mjs <輸出資料夾> style[:進行[:密度[:小節[:只算哪幾軌]]]] ...`
用無頭 Chromium 離線算成 WAV、印 peak / RMS;取樣從 `/tmp/smp` 的 blobless clone 現抓(先照 `tools/samples/build_manifest.py` 開頭的說明 clone)。
需要 playwright:`ln -s /opt/node-tools/node_modules tools/samples/node_modules`(已在 .gitignore)

## 彈法:人性化與每小節變化(`feel.json`,Steven 2026-10-08:「讓彈奏更人性化,不要只有過門才變化」)
`feel.json` 由 `tools/feel/build_feel.py` 從三個資料庫的統計產生(出處與量到的數字見 `docs/SOURCES.md` R1)。
**規格 2.6 的人性化改掉了**(資料證明模型錯):
- 規格:每一下獨立高斯 σ6ms、力度 ±8 均勻亂數
- 現在:①整團一起飄(每小節共同偏移,AR(1))②每個位置的系統偏差與強弱(鼓照 Groove MIDI、鍵盤力度照 POP909)
  ③每一下自己的抖動(各鼓件比例照資料)。整體大小錨在規格的 σ(Groove MIDI 是即興、電子鼓錄的,量到的約大一倍)
- 強弱只在「同一種符號」之間分(規格的 X / x / o 層級保留)
- 和弦各音不同時落下(Goebl 2001:頂音先、全距約 10ms、頂音 +6);吉他切音照 GuitarSet:偶數格下刷、奇數格上刷、各弦相差約 4ms

每小節的變化(不是只有過門):
- 鼓:Groove MIDI 同曲風鼓手在每個位置「多打 / 省略」的機率 × 35%,依樂句第幾小節加權;
  大鼓第一拍、小鼓 2 4 拍、重音 X、過門小節不動;密度 low / standard / high 乘 0.3 / 0.6 / 1;K-pop 舞曲(程式打的)再乘 1/3
- 貝斯:鼓手多踩的大鼓,貝斯在那一格跟著彈根音
- 鍵盤:POP909 的搶拍比例(2.8%)× 50%,下一顆和弦提早一個八分音符進來(分解和弦的曲風不做)
- `render(..., { vary: false })` 完全照規格的節奏型

鋼琴取樣改成 16 層力度(照原作者 sfz 的分界)、力度對音量照 `amp_veltrack 73`、放鍵加原作者錄的制音聲(−37dB);
所有取樣播放跳過起音前的空白(`leadOf`)

## 混音的數學檢查(`tools/mix/analyze.py`,Steven 2026-10-08:「取樣通常很乾,直接加在一起不一定是好事,你要幫我檢查」)
1. 響度:ITU-R BS.1770-4(K-weighting、400ms 區塊、−70 / −10 門檻),各軌相對全混音幾 LU
2. 頻率飽滿:1/3 八度頻帶,對 63Hz–8kHz 擬合斜線,偏離 > ±6dB 的頻帶列出來;2–5kHz 要在斜線以下(讓給主旋律)
3. 互相蓋住:同一頻帶兩軌都占全混音 ≥ 30%
4. 空間:左右相關(目標 0.3–0.9)、單聲道損失、殘響/乾(同一組事件有殘響減掉沒殘響)
音量校正用 `tools/mix/solve_balance.py` 算(目標寫在檔頭),結果寫進 `styles.json` 的 `mix`(dB)
