# 網頁混音 / 母帶:完整步驟與可搬走的程式碼

BackingTrack 的混音鏈是整個 Web Audio 上能做到的專業流程,**每一步都量過**。
以後做別的網頁混音(伴奏、節拍器、線上 DAW、遊戲音樂)可以直接搬:

- 程式碼:`tools/webmix/webmix.js`(單檔 ES module、零相依)
  - 由 `python3 tools/webmix/build.py` 從 `index.html` 抽出來,**index.html 是原稿**
  - `--check` 檢查兩邊一致
- 自我測試:`tools/webmix/test.html`
  - 要走 http(`python3 -m http.server`,打開 `/tools/webmix/test.html`)
  - AudioWorklet 在 `file://` / `about:blank` 載不到
- 量測:`tools/realism/lufs.py`(LUFS、True Peak、L/R 相關、單聲道損失)

## 用法

```js
import { createWebMix } from "./webmix.js";
const ctx = new AudioContext();
const mix = await createWebMix(ctx, {
  lufs: -14, truePeak: true, monoBelow: 120,
  multiband: { lo: [-18, 2, 0.03, 0.2], mid: [-20, 1.5, 0.02, 0.15], hi: [-24, 2, 0.005, 0.1] },
  reverb: { hp: 250, lp: 6000 },
});
const drums = mix.bus("drums", { hp: 45, comp: [-18, 3, 0.01, 0.12], par: [1, -30, 8], sat: 0.35, send: 0.05 });
const bass  = mix.bus("bass",  { hp: 55, comp: [-24, 4, 0.006, 0.15, 1.1], sat: 0.5 });
const keys  = mix.bus("keys",  { eq: [600, -3, 0.4], comp: [-22, 2.5, 0.012, 0.18], chorus: 0.25, send: 0.2 });
drumSampler.connect(drums.input);
mix.reset();            // 每次重新播放(換歌)時呼叫:響度重新量
mix.meter();            // { worklet, agcGainDb, limiterReductionDb }
```

**沒寫的欄位 = 透明**:那一站被繞過,或設成 0dB。所以可以一站一站開,一次聽一個改變。

## 完整步驟(混音 = 每條 bus;母帶 = 總線)

| # | 站 | 在哪 | 做什麼 / 為什麼 | BackingTrack City Pop 的值 |
|---|---|---|---|---|
| 1 | 音量(gain staging) | bus `level` | 先把每層放到對的比例,後面的壓縮才有意義 | `drumLevel 2.24`、`keysLevel 0.28` |
| 2 | 高通 / 低通 | bus `hp` | 每一層切掉不屬於它的超低頻(那是貝斯與大鼓的) | 鼓 45、貝斯 55、吉他 / 鋪底各自 |
| 3 | 減法 EQ | bus `eq` | 先挖掉擠的那一段(250–600Hz 箱子聲),再考慮加 | 鍵盤 600Hz −3、鼓 1k −7 |
| 4 | 串聯壓縮 | bus `comp` | 讓一層「站在同一個位置」 | 貝斯 −24/4:1、吉他、Rhodes −22/2.5:1 |
| 5 | 並聯壓縮 | bus `par` | 紐約壓縮:音頭不變,鼓身與尾巴變厚 | 鼓 1 份、−30/8:1 |
| 6 | 飽和 | bus `sat` | 磁帶 / 前級的圓:尖峰磨一點、泛音多一點,小喇叭聽得到 | 鼓 0.35、貝斯 0.5 |
| 7 | 亮度 / 空氣 | bus `air` | 高頻架子;**backing track 2–5kHz 要讓給主旋律** | City Pop 全部 0 |
| 8 | 調變 | bus `chorus` | Rhodes / 吉他的 chorus(音高偏移 ≤ 3 音分) | 0.25 |
| 9 | 聲像 / 寬度 | bus `width` | 低頻往中間;鼓 0.5 | — |
| 10 | 空間 | bus `send` + `reverb` | 共用一顆殘響 = 同一個房間。回送切低頻(糊掉低頻的第一名)與高頻 | 回送 250Hz–6kHz |
| 11 | 側鏈 | (app 自己做) | 大鼓壓貝斯 / 鋪底 | City Pop 不給 |
| 12 | 段落起伏 | (app 自己做) | 副歌推、主歌收 | `arrange` |
| M1 | 超低頻高通 | 母帶 | 24Hz 以下是浪費音量空間 | 固定 |
| M2 | 母帶 EQ | `midEq` / `airEq` | 整體的傾斜 | 330Hz −2.5 |
| M3 | 三段壓縮 | `multiband` | 200Hz / 3kHz 切(LR4),一段太滿只壓那一段 | 1.5–2:1 |
| M4 | 低頻單聲道 | `monoBelow` | 120Hz 以下的 Side 收掉(M/S) | 120 |
| M5 | 黏著壓縮 | 固定 | 2:1、30ms、250ms,只碰最大聲那幾下 | 固定 |
| M6 | 母帶飽和 | 固定 | x − x³/3 | 固定 |
| M7 | 響度對齊 | `lufs` | BS.1770-4 整合響度、閘門,慢慢推到目標 | −14 LUFS |
| M8 | True Peak 限幅 | `truePeak` | 看前 5ms + 4× 內插偵測取樣之間的峰值 | 天花板 0.85(−1.4 dBTP) |
| M9 | 軟削波 | 固定 | 保險,正常碰不到 | 固定 |
| M10 | 抖動(dither) | **不用** | 只有降位元(輸出 16-bit 檔)才需要;即時播放是 32-bit 浮點進音效卡 | — |
| M11 | 量測 | `lufs.py` | LUFS、dBTP、L/R 相關、單聲道損失 | −14±1 LUFS、≤ −1 dBTP |

## Web Audio 一定會踩的坑(都踩過)

1. **`lowpass` / `highpass` 的 Q 單位是 dB**,不是線性。
   - Butterworth 的 0.707 要寫 `20·log10(0.707) = −3.01`
   - 寫成 0.707 會變線性 1.085,分頻器加回來在切點凸 6dB
   - `peaking` / `allpass` / `bandpass` 的 Q 是線性,只有 `lowpass` / `highpass` 是 dB
2. **DynamicsCompressor 會自己偷補增益**:補 `(1 / 0dBFS 過曲線後的增益)^0.6`。
   - 例:−30dB、2:1 會自己大 8dB
   - 門檻越低、比例越高,沒被壓到的小聲音越大聲
   - `compAutoMakeupDb()` 照 WebKit 原始碼算出來再扣掉(跟實測差 < 0.01dB)
3. **DynamicsCompressor 自帶 6ms 延遲**(288 取樣 @ 48k)。
   - 串聯:開了就整條晚 6ms → 用開關切,而且那一軌提早 6ms 排
   - 並聯:乾的那一路一定要補同樣的 6ms,不然會梳狀濾波 / 變兩下
4. **WaveShaper 的 `oversample: "2x"` 有 128 取樣(2.7ms)延遲**;曲線只管 −1～1,超出去硬削。
   - 飽和前 ÷R、後 ×R 撐大範圍
   - k 小的時候不開超取樣
5. **AudioWorklet 只能在 http(s) 載**(Blob URL 也一樣);`file://` 會失敗 → 一定要有退路(這裡退回內建壓縮器)。
6. **量響度要用 BS.1770**:K 加權、400ms 塊、−70 絕對閘門與 −10 LU 相對閘門。
   - 用 RMS 或 AnalyserNode 輪詢都不準
   - 播放中的響度對齊要**量進來的訊號**(不是自己調過的),不然會自己追自己
7. **分頻器要相位對齊**:三段時,低頻段要多過一顆第二切點的二階全通(Q 0.707),三段加回來才是平的。
   - 驗法:脈衝進去、各段門檻 0 / 比例 1,量頻響要 ±0.6dB 以內

## 驗收方法(每次改都跑)

- **積木的空測(null test)**:OfflineAudioContext 丟脈衝,量頻響與延遲。
  - 三段壓縮加回來 ±0.6dB
  - 低頻單聲道只動 Side
  - 並聯壓縮沒有梳狀
- **整首**:`render.mjs` 錄四種疏密 → `lufs.py` 看 LUFS 與 dBTP → 響度對齊之後比八度頻帶。
  - 改之前 vs 改之後,頻帶差要在 ±1.5dB 內
  - 2–5k **不准變多**
- **bus 單獨**:`probe_solo.js` 錄單一 bus 比 RMS / 亮度,用來校壓縮的補償與並聯的量
- **效能**:CPU 降速 6× 看排程來不及的次數(不能比改之前多)
