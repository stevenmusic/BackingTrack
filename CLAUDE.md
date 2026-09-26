# BackingTrack 專案規則

只寫**現在成立的規則**。量測數字、實驗經過、被退回的做法、踩坑故事都在 `docs/HISTORY.md`
(要改某一塊之前先去那裡搜那一塊的關鍵字,很多「為什麼不這樣做」的答案在那裡)。
評測工具的細節在 `tools/realism/README.md` 與 `KNOWLEDGE.md`。

## 回報方式(使用者要求,每次都照做)
- **所有回覆一律用中文**:分析結果、比較、總結、進度回報都用中文寫(程式碼、檔名、指令照原文)
- **每一則回覆**結尾用**中文**簡短說明這次做了什麼、調整了什麼(沒改東西也要講「這次沒改」)
- 改完推到開發分支並開 PR(見下面「審查流程」);**不再直接推 main**
- 資料能自己查就自己查,不要叫使用者丟資料(WebSearch 可用;很多網站被擋,GitHub 通常通)

## 審查流程
1. 所有改動一律走**分支 + PR**,**禁止直接推 main**
2. 每次開 PR 前,先叫審查員(`.claude/agents/reviewer.md`,規則在 `docs/REVIEWER.md`)審一次
3. 把審查意見**原文**貼進 PR 描述,不得刪改;在後面逐條回應,只能用三種:
   - 【同意】已修,附 commit
   - 【反駁】附程式碼或數據證據
   - 【待 Steven 決定】說明選項與取捨
4. 有阻擋問題時,修完再叫審查員審一次,**最多 3 輪**;第 3 輪後仍有阻擋問題,停下來在 PR 描述寫明,等 Steven 決定
5. 審查員看不到的背景如果讓意見的前提錯誤,用【反駁】直接指出,不要照做
6. 審查員會列「下一步」;**照清單自己改完再送審,不要停下來問**。只有【待 Steven 決定】的事才停。
   `CLAUDE.md` 其他寫「先問」的規則(重做真人片段庫、「刻意不做」的項目)一律算【待 Steven 決定】,不因為照清單就跳過
- 議題與會議紀錄在 `docs/REVIEW.md`;每一輪把狀態更新進去
- **effort 分工**(Steven 2026-09-26 授權):審查員 `reviewer` 是 high;照指令跑量測、整理數字交給 `runner`(low);
  同一個問題審查連續兩輪都卡住,那一件改用 Fable 5.1(Agent 的 `model` 參數)。主對話的 effort 由 Steven 自己設
- **Steven 已授權(2026-09-26):審查全部開綠燈**。審查員沒有阻擋就可以自己合併 PR
- **不再給 Steven 盲測(2026-09-26:「不要給我盲測了,交給你分析,選擇A或B」)**。改預設由 Claude 決定,三條都要過:
  ① **編曲規則有權威出處**(`docs/SOURCES.md`:樂手訪談、樂器雜誌、唱片名單)② 規則全過(旋律 0 違規、下數 ≠ 0、peak ≤ 0.85)
  ③ 不推翻 Steven 以前親耳退回的方向(`docs/HISTORY.md`)。
  **所有規則建立在編曲規則之上,不是測量分數**(Steven 2026-09-26):量尺只用來擋壞掉的東西(外音、下數 0、爆音),
  除非量尺本身被驗證過是對的,否則分數不能當採用或退回的理由。
  每一項的決定與理由寫進 `docs/REVIEW.md`;Steven 主動說不好聽的,照他說的退回

## 產品方向(2026-09-26 使用者定的)
- **公開網站給其他人用,暫時不做 App**
- **暫時只專注 City Pop**(2026-09-26):其他曲風先不動,除非是修壞掉的東西
- **每次生成不能有額外費用**,前置費用可以。不接按次計費的 API
- **繼續用現在的引擎與音色庫**(使用者:音色庫 OK,問題在**風格特徵不夠像**)。網頁程式已退回 fd8a1ca 的版本(見「真人片段庫」)。
  AI 生成音訊(ACE-Step 1.5)實測過:cover / lego / complete 都不照和弦,文字寫和弦只抓到一部分;
  全世界目前沒有「Suno 音質 + 精準照和弦」的做法(見 `tools/acestep/README.md`),這條路先停

## 技術棧與絕對規則
- **單檔 `index.html`**,CSS/JS 內嵌,CDN only,無 build,GitHub Pages 直接部署。不要拆檔,除非使用者明確要求
  (限幅器的 AudioWorklet 也是用 Blob URL 從同一檔生出來的)
- 配色/字體/元件跟 ScrollScore、SightScore、LoudMaster 共用同一套變數(gold / ivory / muted / line / danger),不要發明新顏色
- 排程一律用 `AudioContext.currentTime` 提前排(約 0.15–0.2 秒);setInterval 只負責「來看一下」,**不准用 setTimeout 排音符**
- 取樣只抓這次進行真的會用到的音,不准一次載完整組
- 解析失敗要擋住播放並明講是哪一個 token,不准猜
- **整份檔案不准出現 `Math.random()`**:變化一律 `hash01(絕對位置, salt)`(兩輪 murmur,不要簡化)或 `mulberry32` 固定種子
- 任何取樣播放都要 `start(when, leadOf(buffer))`(跳過起音前的空白)
- 「取樣一定載得到」這個假設永遠不成立:每一種取樣都要有備援(鋼琴→三角波、鼓→`synthDrum`、吉他→KS、Rhodes→平台鋼琴、808→`synth808`)
- 排程裡**不准針對某一個曲風寫 if**:差異一律寫成 `FEELS[x]` 的欄位,**沒寫的曲風要零差異**

## 和弦語法(`normalizeSymbol` / `parseProgression`)
- `QUALITY` 表對著 HarmonyMap 的和弦資料庫生成(80 種類型、134 種拼法),HarmonyMap 加和弦這裡要跟著補。
  不收「So What」(有空白)與「♯5」(跟 `C♯5` 撞)
- 正規化:全形轉半形 → `∆ Δ △`→maj、`° ◦`→dim、`−`(U+2212)→m。**不要動 `+`**(`+`、`7+5`、`It+6` 是字面 key);
  key 大小寫有意義(`M7` ≠ `m7`),不准整串 toLowerCase
- 半形 `-` 是小節分隔符;只有「根音後緊接 `-` 再接數字或結尾」才是小三(`C-7`→`Cm7`),而且要在切 token **之前**處理
- `/`:斜線後面真的是音名才是轉位(用 lastIndexOf,`C6/9/E` 才切得對);貝斯與左手彈 `chord.bassPc`
- `parseChord` 要保留 `rootLetter` / `bassLetter` / `suffix` / `slash`(移調拼字要用)

## 小節與時值
- `|` 是小節線。**沒寫 `|` 時一個和弦一小節**(舊存檔/連結全靠這條);`groupsToText()` 同規則寫回
- 一小節最多 = 拍數顆和弦。沒寫時值就平分、前面拿多的(`spansOf`,4/4 三顆 = 2+1+1)
- 延長記號(一定用空白隔開):`/` 多一拍、`.` 多一格(八分)。沒有 `|` 時記號 = 多一整小節。
  寫了時值就照字面,最後一顆補滿或被切掉。除了最後一顆,每一顆至少一拍
- 和弦格子走 `meter().div`(`chordDiv()`),**不吃曲風的 `sub`**:同一串和弦在任何曲風換和弦的位置一樣
- `fromBeat` 可以是小數,**不准拿它跟整數拍比 `===`**:左手與鋪底用 `startsInBeat` + `slotTime(…, sp.from)`;
  貝斯例外走整數拍(`floor(fromBeat)`),和弦換在拍中間時貝斯到下一拍才換
- 分析(判調、判曲風、代理和弦)一律看攤平的 `flatChords()`;排程看 span(`spanAt`)
- 貝斯把每顆和弦當一小節看;**City Pop / Funk 的十六分切分例外,用整小節的絕對格號**
- 編輯:`barGroups()` 回含延長記號的原始 token(`bar.raw`);`chordTokens()` / `posOf()` 跳過延長記號;
  刪一顆要連後面的延長記號一起刪

## 曲風、疏密、拍號、速度
- **曲風**(`FEELS`,UI 顯示英文名 Pop / City Pop / K-Pop / Bossa / Blues / Swing / Funk,不翻譯)。
  程式 key 不准改:`straight` / `citypop` / `kpop` / `latin` / `blues` / `swing` / `funk`(存檔、網址 `f=` 都用它)
- **預設自動**:`detectFeel()` 只回 straight / latin / swing——任一顆九度以上 → swing;**一半以上(含)**有六度七度(屬七不算)→ latin;其餘 straight。
  City Pop / K-Pop / Blues / Funk 永遠不自動判到(它們定義在律動上),**不要為了能自動判到去猜和弦**
- 指定之後鎖住(`feelPick`),換和弦不推翻。實心金的膠囊 = 現在在彈的(`feelNow`);「自動」是獨立的 `.auto-chip`,亮時空心金。不要把自動塞回曲風那排,那排不要標題
- 曲風膠囊在卡片最上面全寬;**點曲風會把速度帶到該曲風中速**(`TEMPO_QUICK[feel][meter]`),自動判斷不帶
- 不適用的拍號寫在 `FEELS[x].meters`,判斷只走 `feelFitsMeter()`;變暗是提示不是鎖,點下去連拍號一起換
- **疏密是使用者那一軸**(`PATTERNS`:pad / comp / drive,加 `mix` = 每圈 pad→comp→drive→comp)。
  別的東西(段落庫、曲風)不准改疏密。排程一律問 `styleAt(absBar)`,不准直接比 `styleOn`
- **拍號**只有 4/4、3/4、6/8(`METERS`),使用者選。所有節奏型用「第幾格」寫,不准寫死 4:
  用 `beatsInBar()` / `slotsInBar()` / `beatSlots()` / `midBeat()`;`slotTime()` 是唯一換算時間的地方,複拍子不搖
- `GROOVES` / `COMP_CELLS` / `KICK_CELLS` / `SNARE_CELLS` 都是「曲風 → 拍號 → 型」,加拍號三張表都要補
- 十六分的曲風用 `sub: 2`,只有 `subOf()` / `divNow()` 看它
- 單拍子 ↔ 複拍子切換時,速度超出新拍號的範圍才換成中間值;`bpmNote` 6/8 顯示 ♩.

## 代理和弦(「和弦變化」開關,`reharmOn`)
- 第一圈照原譜;之後每圈換 1–2 格,在圈的第一小節第一拍換(`buildLap`)。畫面顯示真的在響的(`barsNow()`)。
  改和弦/按播放/關開關都 `resetLap()`,而且**要在 `renderBars()` 之前**
- 換的是代理和弦(`SUB_RULES`),不是改 7/9/13;加色彩音只是墊底,要過 `progPcs` / `extFits` 守門,只能往上加(`EXT_TABLE["13"]` 為空)
- 先判調(`keyOf()`,只看骨架音 `KEY_CORE`,降七度與延伸音不算)
- 只有 Bossa / Swing(`JAZZ_FEELS`)可以副屬、三全音代理、補 ii;其他曲風只做不動骨架的事
- 標準是「這首歌還是不是這首歌」:換根音的規則要少。以下情況**不准換根音**:
  調外的招牌和弦、上一格要解決到這裡(`resolvesHere`:屬七下五度、屬七下半音、減七上半音)、
  低音在走級進線(`bassLine`)、旁邊那格同根音不同性質(`pairedRoot`,一模一樣的重複不算)、換完跟鄰居同一顆(`clashesNeighbour`)
- 副屬化(根音不動改屬七):下一格在四度上方才給,**下一格已是屬七時不准**(那是 ii-V 的 ii);色彩音照 `domSuffix()` 保留
- 三全音代理的根音一律拼降記號(`flatNameOf`);轉位保留原性質(`x.full`)且低音要級進(`stepToNext`)
- `mood`:大七↔小七是換情緒。`tonic` 只給 Bossa/Swing;`sub`(IV↔ii)整圈最後一顆不換;一圈最多換一次情緒
- 拆一顆成兩顆(`sus→V`、`拆ii-V`):只拆單獨一顆且沒寫時值的,一圈最多一顆,拆出來的標 `added` 不佔選取序號;律動只換音高不加下數
- 改規則要跑 scratchpad 式的機器驗證(`tools/realism/mood_check.mjs`、`harmony.mjs`),不要靠讀

## 旋律只准用和弦音(唯一例外見下)
- 「旋律」= 每一下和聲的頂音(鋼琴、兩把吉他、鋪底、銅管、人聲切片、lead)+ 單音線條(arp、第二把吉他)。貝斯不算
- **唯一的例外(Steven 2026-09-26)**:City Pop 切音吉他照ギター・マガジン的指型(`parts.chopForms`,`docs/SOURCES.md` G1)時,
  **吉他和弦的頂音可以是九度**(只在九度在調內、和弦沒有 ♭9/♯9 時);鋼琴、鋪底、銅管、第二把吉他的單音線不放寬。驗證加 `HARM_GTR9=1`
- 唯一判斷:`melodyOk()`——只准根、三、五(含 ♭5/♯5)、六、七、sus 的二/四度、轉位低音;
  不准九/十一/十三度、調外經過音,**屬七的降七度也不准**
- 三道守門:`buildVoicing` 頂音罰 100 + `fixTop`;吉他 `guitarNotesFor` → `fixTop`;單音線條先 `filter(melodyOk)`。
  新增和聲層從 `sp.v` 拿音,新增線條要走其中一道
- 驗證:`node tools/realism/harmony.mjs <曲風> "<進行>"`,「旋律上的和弦外音」要是 0,**而且下數不是 0**(下數 0 = 排程壞了);全部跑 `allharm.sh`

## 聲位與演奏
- `buildVoicing` 每小節挑離前一個最近的轉位;捨音順序 五音 → 根音(轉位不捨)→ 延伸音,上聲部最多四音(`trimTones`)
- 鋼琴 comping:重拍落滿、反拍拿掉底下的音(頂音一直在);音長用 `compDur()`(每小節一種觸鍵);強弱 1.35 / 1.0 / 0.62 / 0.45
- 力度改音色不只改音量:鋼琴與貝斯都有力度低通(`velRef`);只有鼓有真的多力度層,**不要給鋼琴做多力度層**(記憶體會爆)
- 左手讓位:`lhGain()` = `FEELS[x].lh` ?? (boogie 0.38 : 0.55);三種疏密左手都要撐長
- 吉他:Pop 刷弦用真的手型(`realShape`,照移調後的根音挑,`prewarmGuitar` 也要傳 transpose);
  封閉和弦 5 弦 / 6 弦照**左手位置**挑移動最少的(`gtrHand` / `strumNotes`,`resetLap` 歸零),`prewarmGuitar` 要照播放順序走多圈;
  切音的ギター・マガジン指型(`parts.chopForms`)與右手一直刷(`parts.chopBrush`)**預設不開**:一起開時 Steven 說「非常機械」;
  Bossa 拇指低音 + 三弦 clave(跟 cross stick 共用 `g.clave`);切音不彈根音;每條弦差兩三音分
- 貝斯一律待在 E1–D♯2 附近(`bassMidiFor`),移調不跟著跑;兩把琴 buffer 分開收(`bassBuffers.electric/.upright`),檔名音高寫法不同不准混用
- 鋪底一顆和弦落一次、不跟節奏打;City Pop 用連奏鋪底(`padLegato`)。失諧至少四顆不等距,兩顆一定是固定晃動
- 樂句呼吸:`phraseHole()`(鍵盤與吉他不同 salt);編曲層級 `FEELS[x].arrange` / `layerOn()`,**關卡只在 `scheduleExtras`**,
  只有第四層(吉他、鋪底、銅管、打擊小物)可以進出,鼓/貝斯/鋼琴永遠在
- 人性化欄位 `micro` / `pocket` / `timing` / `roll2` / `velRange` / `artic`:除了 K-Pop(刻意量化)全部曲風都開著。
  要的是有結構的偏差(長程相關、拍點緊拍點間鬆),量級不准超過真人

## 鼓
- 每個曲風一種打法(`GROOVES`),拍子感來源不能拿掉:Pop/Blues/Funk/City Pop 是小鼓 2、4(`f.snarePiece`);
  Bossa 是 cross stick 的 clave(兩小節一循環 3+2);Swing 是 hi-hat 踏鈸 2、4 + ride 型 `[0,2,3,4,6,7]`、小鼓 comping 平均抽、大鼓 feathering;
  **K-Pop 是 half-time,拍手只打第 3 拍,不准補 2、4**
- `kickHold`(大鼓整段固定)/ `bassFollowKick`(貝斯跟大鼓)**預設不開**:照字面做成「整段一模一樣」聽起來機械(Steven 2026-09-26)。
  City Pop:hi-hat 走十六分(強弱 `hatAcc`)、open hat 在反拍且一定被下一顆 closed hat 掐掉(`chokeOhat`)、大鼓與貝斯綁同一條時間(`timing.tie`)。
  鼓的節奏是 `GROOVES` / `KICK_CELLS` / `SNARE_CELLS` 的格子加人性化(`timing`、`pocket`)
- 高密度的鈸靠強弱差不吵(skip note、後半拍輕),**不是把總量壓掉**;兩層平均分布的高頻不准疊(打擊小物要嘛跟 backbeat、要嘛小一個量級)
- 過門只佔最後一拍、hi-hat 不斷、力度漸強;搖擺的過門走三連音;一格的進行沒有過門
- 鼓件照曲風載(`FEEL_PIECES`);載入分三段:擋播放的只有中間層一兩個 rr,其餘背景補,背景大包等 `drumFillGate`
- `SRC_DRUMS` 停在 `Samples/`,麥位由呼叫端接;房間麥只抓中間層
- 808:`ensureDrums()` 在 `drumKit()==="e808"` 時只回 `ensure808()`;取樣與合成各一張 trim 表(`D808_TRIM` / `E808_TRIM`),加音色兩張都要補並重量響度;
  808 大鼓用短的 `BD0025`,長尾巴是 `sub808` 貝斯的工作

## 音源與音色(對照 `FEELS[x].piano / drums / drumSet / kit / parts`)
| 曲風 | 鍵盤 | 鼓 | 貝斯 | 第四層 |
| --- | --- | --- | --- | --- |
| Pop | Salamander | Virtuosity | 電貝斯 | 鋼弦刷弦×2、鈴鼓 backbeat |
| City Pop | Rhodes(jRhodes3c,非商用授權,商用前要換) | SM Drums(大小鼓、hi-hat)+ Virtuosity(tom、鈸、open hat) | 電貝斯 | Hofner 切音 + 第二把吉他、合成銅管、合成鋪底、沙鈴八分;配器輪換 `orchs` |
| K-Pop | 合成 pluck | 808 取樣 | 808 合成 sub | supersaw、低音鋪底 `klow`、arp、沙鈴+指響、乒乓延遲 |
| Bossa | Salamander | Virtuosity(cross stick) | 低音提琴 | 尼龍弦 clave、cabasa |
| Blues | Salamander | Virtuosity | 電貝斯(boogie) | Hammond(很輕),不給吉他 |
| Swing | Salamander | Virtuosity(ride) | 低音提琴 | archtop Freddie Green |
| Funk | Rhodes | Virtuosity | 電貝斯 | 悶音切音、鈴鼓 backbeat |
- 使用者**不能單獨選音色**,不要加那個選單。音色與聲位是兩件事,不要混著改
- **換音色不用先問(Steven 2026-09-26:「換音色時,以真實歌曲使用的音色為基準,之後不要問我」)**:
  基準是唱片樂手名單上那一層真的是什麼(`docs/SOURCES.md` C1)。還是要過下面「取樣比合成好」的兩個條件,
  也不推翻 Steven 親耳退回過的(`docs/HISTORY.md`)
- 取樣來源(細節與授權見 README 與 `docs/LICENSES.md`):Salamander(Tonejs/audio)、jRhodes3c、Virtuosity Drums(`Samples/mid/`)、
  SM Drums、Black And Blue Basses(`darkblack` mf)、dsmolken 低音提琴(`pizz/`)、Black And Green Guitars(Gretsch stac / Hofner ord)、
  nbrosowsky tonejs-instruments(鋼弦/尼龍/電吉他 mp3)、tidalcycles Dirt-Samples 808(WAV)。
  VCSL 是管弦打擊樂,不准拿來當爵士鼓
- **新增音源 / 資料集只收 CC0、CC BY、MIT 這一類可商用的**,加進 `docs/LICENSES.md`;非商業授權(jRhodes3c 那種)要上架前換掉
- 每個檔都走 `fetchDecode()` 多來源(jsDelivr → raw.githubusercontent,鋼琴多 tonejs.github.io)。新增音源照這個模式
- 取樣表照真的檔案列,不准照公式推(Rhodes 兩層拼、吉他有洞、tonejs 的 G5 指錯檔不收);換撥弦取樣先量音頭音準(`SMP_EXT[x].tune`)與音量(`smpNorm`)
- 合成的(刻意不換):Hammond(`PeriodicWave`)、K-Pop 的 pluck/supersaw/808 低音、City Pop 鋪底(唱片也有 KORG λ 弦樂機)。
  **判準是「真的唱片裡那一層怎麼來的」**;弦樂鋪底不准換回取樣(Steven 盲聽退回過)。
  取樣只在兩條都成立時比合成好:(a) 要「一組人」時真的有一組人(不是同一顆取樣疊四次)(b) 取樣撐得住聲部的長度
- 合成的東西算完要存(`ksBuffer`、`hat808Buf`、`noiseBuf`),`prewarmGuitar` 要在按播放前算好/載好,用到 `pluck` 的新層要把音加進 `want`;
  解碼一顆一顆排隊;每顆合成音起音要 1–1.5ms 斜坡
- 殘響 IR 用固定種子、左右不同種子;任何卷積 IR 要正規化能量
- 播放中換曲風,音色在背景跟上,不准 await

## 混音與母帶
- 鏈:`masterGain(TL_IN 0.75)→ 高通 24Hz → 黏著壓縮 → 飽和(x−x³/3)→ outGain(TL_OUT 2.35)→ 看前 5ms 的限幅器 worklet(天花板 0.85)→ 軟削波(保險)`。
  worklet 載不到時退回舊鏈(DynamicsCompressor,outGain 1.08)。**量聲音一定走 http**,`file://` 載不到 worklet
- 目標:**peak ≤ 0.85、零削波、RMS 約 −11～−14 dBFS**;Swing 偏小聲是本色不硬拉
- 每條 bus 的處理寫在 `FEELS[x].mix`(高通、EQ、壓縮、chorus、`drumLevel`、`master`…),**沒寫就透明**。
  壓縮器不是拿來加音量的;調變效果先算音高偏移(深度 × 2π × 速率,≤3 音分);頻譜比對只能當方向
- 側鏈 `FEELS[x].duck`:K-Pop 深、Funk 很淺、Pop 一點點;City Pop 與 acoustic 曲風(Bossa/Swing/Blues)不給
- 低頻往中間收;相位目標:單聲道 penalty ≤1.5dB、L/R 相關 0.3–0.9
- 尖峰過高先找「誰在撐著」(一路 solo 到單一鼓件),不是找誰最大聲;量響度要逐取樣掃,不用 analyser 輪詢;
  改演奏法(音長、密度)之後要重量各層比例

## 真人片段庫(已退回,2026-09-26)
- 第十輪的「真人片段庫」(Groove MIDI 鼓、貝斯轉譜彈法庫 `bassPhr`、上下文挑選 `pickBassPhr`)**已經整個退回**:
  使用者回報網頁播不出聲音,要求回到改做法之前、音色微調過很多次的版本(`index.html` 回到 fd8a1ca,只保留之後的介面修正)
- 那一版在同一組 12 段量到「像真人」141%、規則版 122%,但使用者盲聽不認同;經過與數據在 `docs/HISTORY.md` 與 `tools/realism/db/groove.json`
- 要再做之前先問使用者

## 驗收與量測
- 標準是**有出處的編曲規則**;Steven 主動說不好聽的照他說的退回。MERT / VGGish / Audiobox 只能擋明顯壞掉的,不能宣稱「變真實」。百分比超過 100% 只代表進到真歌那一群
- 雲端容器連不到 CDN:取樣用 `git clone --filter=blob:none` 拉到 `/tmp/smp/`,Playwright `page.route` 對到本機;
  不要在 blobless clone 上跑 `git ls-tree -l`。錄音從固定拍點開始(`currentBeat() >= 32`)
- 量完刪大檔(分軌、wav),磁碟會滿;參考曲換了要刪 `/tmp/simcache.npz`;參考曲音檔一律不進 repo
- 分析腳本的全域名稱加 `__` 前綴(不要蓋掉 app 的 `groove()` 等)
- 效能:CPU 降速 6× 跑三四次看中位數,標準是「來不及 0 次」

## 介面
- 版面:680px 以上兩欄(左 = 這首曲子:輸入 → 小節數/段落庫 → 小節格 → 小節編輯條 → 播放 → 和弦鍵盤;右 = 怎麼伴奏)。
  斷點 900 / 680 / 600 / 400。**改版面要量 `scrollHeight`**:1280×720、1280×800、1440×900、1100×800、900×800、800×800、820×900 等,
  4–24 小節不准捲(已知例外見 HISTORY)
- **每次改版面,中文與英文介面都要各量一次**(英文字通常比較長,溢出/換行要兩種都看)
- 一排數量不固定用 grid `auto-fill`,不用 flex、不用 `auto-fit`;`minmax` 下限不要太大
- 和弦名字寧可縮字也不准被切;縮字用 `min(字級, calc(寬 ÷ 字數 ÷ 0.76))`,算時扣掉內距;容器查詢一律取名
- 小節格一排四格(>12 格且夠寬才八格,門檻 430px),不准六欄;字級低於 8px 就畫點(`fitBarNames`),真的放不下退一排兩格(≤8 小節)
- 小節編輯條 `#barEdit` 自己一排:點方塊選、拖把手改位置(半拍一步)、＋ 切、× 併;合法性畫的時候就算好;拖的時候只動 CSS
- 小節數是下拉(4 的倍數到 40,`LEN_STEP` / `LEN_MAX`),非 4 倍數要插進選項
- 和弦鍵盤:字母與升降分開;選中是金框淡金底;`:hover` 包在 `@media (hover:hover)`;性質比音程集合(`qualKey`)
- 移調:文字框留原稿,顯示用 `chordDisplay()`,整段一起決定字母(`transposeSteps`)
- 段落庫:浮動面板、預設收起,分頁 = 曲風(跟著 `feelNow`),數「這個曲風幾組」;螢幕夠大時內嵌(`placeSecPanel`,`.card` 要 `width:100%`)
- 復原:改文字前 `pushUndo()`;⌘Z 只在焦點不在輸入框時攔
- 分享連結 `?c=&bpm=&m=&s=&t=`,有參數就蓋過 localStorage。沒有 service worker
- SVG 顯示/隱藏走 `setAttribute("hidden")` 加 `svg[hidden]{display:none}`;改速度用 `reanchorTempo`
- i18n:`I18N.zh` / `I18N.en` 兩邊的 key 要一樣,新增 `data-i18n` 要兩邊都補

## 段落庫(`SECTIONS`)
- 每筆只帶 `text` / `feel` / `meter` / `role`(verse / pre / chorus / form),**不准帶疏密**
- 全部 C 大調 / A 小調;每組要是真的常用、自己循環得起來的完整進行;循環進行不要硬撐成八小節
- 同一曲風不准有兩組「只差和弦變化會做的事」的進行(留七和弦那版);跨曲風同根音是可以的
- Pop 維持三和弦(不然會被判成 Bossa);K-Pop 的 V 留三和弦;爵士 3/4、6/8 要用九度以上聲位
- 整串 ii-V 沒有主和弦、♭VII 主導的進行會讓 `keyOf` 判錯,不收
- 接段落用 `partGroups` + `groupsToText`,不准用 `-` 串;拍號或曲風不同時當新的一首
- 目前 83 組:Pop 21、City Pop 24、K-Pop 6、Bossa 7、Blues 6、Swing 14、Funk 5

## 刻意不做 / 拿掉的(要加回來先問)
- 必選的曲風入口選單;單獨的音色選單;各軌靜音(鼓與貝斯永遠都在,沒有開關);愈練愈快;MIDI 匯出;小節區段循環
- AI 直接生成音訊(不能照和弦、不能離線、授權多非商用)
