# 風格規格 v1(styles/)

依「BackingTrack 風格規格書 v1」產生的資料、事件引擎與**真實取樣**播放器。
試聽頁是 `styles/index.html`(GitHub Pages 上的 `/styles/`)。**2026-10-08 起主網頁 `index.html` 的聲音也是這個引擎**
(主網頁保留自己的介面與播放控制,每一圈交給 `render({ barSpans, densities, barBase, meter })` 算,見 `CLAUDE.md` 最上面一節)。

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
- **華語 / K-pop 抒情的分解和弦改用 `arp_inv`**(Steven 2026-10-08:「應該找近的位置(轉位,而不是跟著和弦名稱彈原位)而且有 bass 撐住彈低音」「音跟音之間斷掉了」):
  左手 = 和弦的低音(斜線和弦就是斜線那個音)36–47 離上一顆最近 + 它的高八度;右手 = 和弦音(有七度 3、5、7,沒有 1、3、5)
  用 Viterbi 挑最近的轉位(55–69);一律踩延音踏板(每個音撐到換和弦,同一個音重彈時前一顆停);換和弦那一格一定補左手低音。
  `node tools/feel/arp_check.mjs`:空檔 0ms、右手換和弦平均移動 1.0–1.5 半音、每次換和弦都有左手低音
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

## 空間與融合(Steven 2026-10-08:「整體聲音沒有融合在一起……不要跟之前一樣重複試錯」)
原因:各取樣庫錄在不同房間、不同距離(Virtuosity 中距離麥、Salamander AB 立體聲、VSCO 在廳裡、貝斯與吉他是 DI 完全沒空間),
之前每軌送固定量的雜訊殘響,本來遠的更遠、本來乾的還是乾。現在照下面的順序一次算出來:
1. **量取樣本身的空間**(`tools/mix/space.py`):每軌單獨算(跳過母帶鏈),500Hz–4kHz 用左右相干性的大小 |Γ| 把能量拆成直達與擴散
   (Thiergart et al. 2012 的 signal-to-diffuse 估計,擴散場相干 = 0 的特例;用大小不用實部,間隔式立體聲麥的時間差才不會被當成殘響)。
   量到(dB,越大越近;6ms 對齊之後):鼓的中距離麥 +3.1、鋼琴 +4.5～+7.6、Rhodes +10、弦樂 −0.3(本來就遠)、貝斯 / 吉他 / 808 +25～+67(幾乎全乾)
2. **真的空間**:人工殘響換成真實錄音的 IR(`styles/ir/`,`tools/mix/make_ir.py`,MIT 授權的 Conner's IR Library):
   room = 真實客廳 T20 左 0.63 / 右 0.62 秒(跟鼓的房間麥 0.5–0.65 秒同長),plate = 真的板式殘響;原檔左右很不對稱(左 1.77、右 3.59 秒),
   每個聲道各自修到 1.79 秒、能量拉平(不然尾巴飄右邊)。載不到或 8 秒沒回應才退回雜訊 IR
3. **鼓用自己的房間麥**:Virtuosity 的 `Samples/room/` 跟中距離麥同一次演奏、一對一同步播(同一顆 round robin、同一個起音位置),
   −6dB,背景補載不擋播放;原聲鼓不再送人工殘響(預備拍的 hi-hat 也帶房間麥,同一組鼓)
4. **舞台**:以「鼓手的房間」為錨(中距離麥 + 房間麥量到的 DDR = A,各曲風 +1.2～+1.7dB),其他軌寫相對 A 的距離
   (`styles.json` 的 `space.stage`):貝斯 +8(低頻要乾要近)、鍵盤 / 吉他 +1、第二鍵盤 −1、弦樂鋪底 −3;808 +3、大鼓不送殘響。
   pre-delay 越近越長(20 / 15 / 12 / 8 / 5ms)。殘響能量直接量得到,所以是閉式解 k = sqrt((D/目標 − R) / E殘響),不用試;
   結果寫進每個曲風的 `space.sends`,再重算一次驗證
5. **黏合**:鼓組(各鼓件 + 大鼓 + 房間麥)先過一台壓縮(4:1、門檻 −16dB、knee 6、起音 10ms 讓鼓頭過去、釋放 120ms;
   Web Audio 自動補的增益照 Chromium 的公式扣掉 `compAutoMakeupDb`,6ms 預讀延遲由其他軌與殘響一起延後補齊 `COMP_LAT`,
   `node tools/samples/align_check.mjs` 量大鼓 / 貝斯 / 鍵盤峰值差 0.023ms);再過總線黏著壓縮(2:1、門檻 −18dB)與一點飽和
   (tanh,k 0.5,0dBFS 約 −0.7dB,奇次諧波,4 倍超取樣)。
   壓縮量看「有在壓的時候」:每 10ms 讀一次 reduction 取 95 百分位(平均會被鼓聲之間的空檔稀釋——門檻 −24 時平均 3.2dB,
   其實打下去壓 8dB,所以改成 −16)。現在的量(`node tools/samples/render_styles.mjs /tmp/probe <曲風>::high:8::probe`):
   鼓組 3.4–3.7dB(pop 3.7、華語抒情 3.4、City Pop 3.7、R&B 3.4、K-pop 舞曲 3.5、Lo-fi 3.4),
   總線 0.8–2.0dB(1.2 / 1.3 / 1.4 / 0.8 / 1.8 / 2.0);業界常用範圍鼓組 3–4dB、總線 1–2dB

## 拍號(Steven 2026-10-08:「拍號應該還是有可能會有 3 拍」)
- 4/4 的節奏型在 `tracks`,3/4、6/8 在 `meters["3/4"].tracks`(一小節 12 格、過門 6 格);沒寫的拍號 = 這個曲風不打(會講清楚)
- 支援 3/4、6/8:Pop、華語抒情、K-pop 抒情(繼承)、Lo-fi(3/4)、R&B(6/8,12/8 慢歌);J-pop、City Pop、K-pop 舞曲、Reggaeton 只有 4/4
- 3/4 兩顆和弦 = 2 拍 + 1 拍;6/8 兩顆 = 各一個附點四分;6/8 不搖擺;預備拍照拍子數(3/4 三下、6/8 兩下)
- 寫法參考舊網頁的 3 拍(3/4「蹦恰恰」小鼓 2、3 拍;6/8 小鼓第 4 個八分)與 Groove MIDI 的 3-4 / 6-8 段落(資料少:571 / 106 小節,
  只取時間偏差大小與 hi-hat 強弱,變化機率再打五折);鍵盤沒有三拍資料,不分強弱、不搶拍

## 母帶(Steven 2026-10-08:「母帶跟混音都幫我做好」)
`黏著壓縮(2:1、門檻 −18dB、起音 30ms)→ 各曲風響度校正(styles.json 的 master.gainDb)→ 總線飽和 → 預讀限幅器(limiter.mjs,AudioWorklet,
預讀 5ms、4 倍超取樣估 true peak、天花板 −1 dBTP)`;worklet 不能用時退回 DynamicsCompressor。
目標 −14 LUFS(串流平台的標準響度)、true peak ≤ −1 dBTP;`tools/mix/solve_loudness.py` 量完寫回 `master.gainDb`
