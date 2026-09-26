# 音源與資料集的授權

整理日期 2026-09-26。授權原文是從各倉庫的 LICENSE / readme 直接抄的(2026-09-26 clone 的版本);
網站被這個雲端環境擋住、沒辦法讀原文的,另外標出來。
**這份不是法律意見**。上架付費 App 之前,「不確定」那幾項要自己或請律師再確認一次。

## 總表

| 用在 | 來源 | 授權 | 付費 App | 出處要求 |
| --- | --- | --- | --- | --- |
| 鋼琴(全曲風,Funk、City Pop 以外) | Salamander Grand Piano v3(Alexander Holm) | CC BY 3.0 | ✅ 可以 | 要署名 + 附授權連結 |
| 電鋼琴(Funk、City Pop) | jRhodes3c(Jeff Learman) | 散布取樣要 **CC BY-NC 4.0**;商用要另外取得授權 | ❌ **不行**(除非作者另外授權) | 署名 |
| 鼓(大部分曲風) | Virtuosity Drums(Versilian Studios × Karoryfer) | CC0 1.0 | ✅ 可以 | 不要求(建議仍署名) |
| 鼓(City Pop 的大鼓、小鼓、hi-hat) | SM Drums(Scott McLean、Tod Stillwell、Suleiman Ali) | 作者網站聲明免費、免版稅、任何用途;**倉庫裡沒有 LICENSE 檔** | ⚠️ 大概可以,待確認 | 不明 |
| 鼓(K-Pop 808) | tidalcycles/Dirt-Samples 的 `808*` 資料夾 | **倉庫沒有標授權**,取樣原始出處不明 | ⚠️ **不確定** | 不明 |
| 電貝斯 | Black And Blue Basses(Karoryfer) | CC0 1.0 | ✅ 可以 | 不要求 |
| 低音提琴 | dsmolken.double-bass(D. Smolken) | CC0 1.0 | ✅ 可以 | 不要求 |
| 電吉他(City Pop) | Black And Green Guitars(Karoryfer,Brian Wood 錄) | CC0 1.0 | ✅ 可以 | 不要求 |
| 鋼弦木吉他(Pop) | tonejs-instruments `guitar-acoustic` ← University of Iowa MIS | Iowa:任何用途不受限;整理者標 CC BY 3.0 | ✅ 可以 | 署名 Brosowsky(CC BY 3.0) |
| 電吉他(Swing、Funk) | tonejs-instruments `guitar-electric` ← Karoryfer | 整理者標 CC BY 3.0(原始是 Karoryfer 的免費取樣) | ✅ 大概可以 | 署名 Brosowsky |
| 尼龍弦吉他(Bossa) | tonejs-instruments `guitar-nylon` ← Freesound pack 11573(quartertone) | 整理者標 CC BY 3.0;**Freesound 原頁的授權讀不到** | ⚠️ 不確定 | 至少署名 quartertone + Brosowsky |
| 鼓的節奏(Pop、City Pop、Funk、Blues、Swing) | Groove MIDI Dataset(Google Magenta) | CC BY 4.0 | ✅ 可以 | 要署名 + 附授權連結 + 標明有修改 |
| 貝斯彈法庫(City Pop 的 `bassPhr`) | 12 首商業 City Pop 唱片的貝斯分軌,經 Basic Pitch 轉譜萃取的半小節音型 | 原曲有著作權 | ⚠️ **不確定** | — |
| 字型 | Noto Serif TC / Noto Sans TC(Google Fonts) | SIL OFL 1.1 | ✅ 可以 | 附 OFL |
| 鍵盤片段庫(計畫中) | POP909 | MIT | ✅ 可以 | 附 MIT 聲明;作者要求論文引用 |

風琴、合成器鋪底、銅管、K-Pop 的 pluck / supersaw / 808 低音、打擊小物(沙鈴、鈴鼓、cabasa)、
殘響都是程式即時合成的,沒有外部授權問題。

## 上架付費 App 之前要處理的

1. **jRhodes3c 一定要換或取得授權**。它是 Funk 與 City Pop 的鍵盤(`FEELS.funk.piano`、`FEELS.citypop.piano`)。
   City Pop 依 Steven 2026-09-26 指定不回平台鋼琴,所以 City Pop 的選項只有:寫信給作者(LICENSE 裡的信箱,原文寫
   「please contact me and I will be happy to grant a license」)取得商用授權,或換成 CC0 / CC BY 的電鋼琴;Funk 仍可改回 Salamander。
   免費公開網站屬非商用,現在可以用(要署名)
2. **Dirt-Samples 的 808 要換成出處清楚的 808 取樣**(或退回程式裡的 `synth808` 合成版,那是自己寫的,沒有授權問題)
3. **尼龍弦**:到 Freesound pack 11573 的頁面確認授權(CC0 / CC BY 可以;如果是 CC BY-NC 或 Sampling+ 就要換)
4. **SM Drums**:把作者網站上的授權聲明截圖存證,或寫信確認
5. **貝斯彈法庫**:從商業唱片轉出來的音型。短的伴奏型一般認為不構成著作權保護的旋律,但這是灰色地帶。
   保守的做法是改用有授權的資料(例如自己錄、或用 Groove MIDI 那種明確開放的資料)重做
6. **App 內要有「致謝 / 授權」頁**,列出所有 CC BY 的署名(Salamander、Groove MIDI、tonejs-instruments)與連結。
   目前網頁版只有 README 有寫,App 裡沒有

## 授權原文與出處

### Salamander Grand Piano v3
- 來源:https://github.com/sfzinstruments/SalamanderGrandPiano(取樣實際從 https://github.com/Tonejs/audio 的 `salamander/` mp3 載)
- 原始:https://archive.org/details/SalamanderGrandPianoV3
- LICENSE 檔:`Creative Commons Legal Code — Attribution 3.0 Unported`(全文:https://creativecommons.org/licenses/by/3.0/legalcode)
- README:「Author: Alexander Holm」
- 建議署名:*Salamander Grand Piano V3 by Alexander Holm, licensed under CC BY 3.0*

### jRhodes3c
- 來源:https://github.com/sfzinstruments/jlearman.jRhodes3c
- LICENSE 原文:
  > This sample set is provided free for use as a musical instrument.
  > You can use the sounds in any way in your works as an artist, just as you could with a real instrument.
  > To distribute the samples themselves, such as in an application, software instrument, or as a sample set, the jRhodes samples are licensed under CC BY-NC-SA 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by-nc/4.0 .
  > BY: Credit must be given to the creator.
  > NC: Only noncommercial use of the work is permitted.
  > To use the samples in a commercial product, please contact me and I will be happy to grant a license.
- 注意:同一段文字寫了 BY-NC-SA 又連到 BY-NC,兩者都是**非商業**。App 本身就是「在 application 裡散布取樣」

### Virtuosity Drums
- 來源:https://github.com/sfzinstruments/virtuosity_drums
- LICENSE 檔:`Creative Commons Legal Code — CC0 1.0 Universal`(全文:https://creativecommons.org/publicdomain/zero/1.0/legalcode)
- README:「performances by drummer Austin McMahon」,錄於 Virtuosity Musical Instruments(Boston)

### SM Drums
- 來源:https://github.com/sfzinstruments/SMDrums(倉庫裡只有取樣、sfz、手冊 PDF 與軌道模板,**沒有 LICENSE / README**)
- 作者網站(https://smmdrums.wordpress.com/)的聲明(經搜尋摘要取得,網站本身被這個環境擋住):
  > ALL of the content on this website is for FREE royalty free use by anyone for anything
- 作者:Scott McLean、Tod Stillwell、Suleiman Ali

### Dirt-Samples(808)
- 來源:https://github.com/tidalcycles/Dirt-Samples(用到 `808/`、`808bd/`、`808sd/`、`808hc/`、`808oh/`、`808cy/`、`808mc/`、`808lc/`、`cp/`)
- 倉庫**沒有 LICENSE 檔**,README 只寫「Set of samples used in SuperDirt and the TidalCycles tutorials」,沒有提授權或取樣出處

### Black And Blue Basses
- 來源:https://github.com/sfzinstruments/karoryfer.black-and-blue-basses
- `license` 檔:`Creative Commons Legal Code — CC0 1.0 Universal`

### dsmolken.double-bass
- 來源:https://github.com/sfzinstruments/dsmolken.double-bass
- LICENSE 檔:`CC0 1.0 Universal`
- readme.txt:
  > 1958 Otto Rubner double bass played and mapped by D. Smolken. … Royalty-free for all commercial and non-commercial use. Copyright 2013 D. Smolken.

### Black And Green Guitars
- 來源:https://github.com/sfzinstruments/karoryfer.black-and-green-guitars
- LICENSE 檔:`CC0 1.0 Universal`
- readme.txt:
  > It contains samples of a green Gretsch Anniversary and a black Hofner Club, recorded and photographed by Brian Wood. … Royalty-free for all commercial and non-commercial use. Copyright 2022 Karoryfer Lecolds.

### tonejs-instruments
- 來源:https://github.com/nbrosowsky/tonejs-instruments
- LICENSE.md 原文:
  > MIT License — Copyright (c) 2018 Nicholaus P. Brosowsky
  > Permission is hereby granted, free of charge, to any person obtaining a copy of this software … The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. …
  > SAMPLES RELEASED UNDER [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/)
- sample-source-info.txt(用到的三把):
  > guitar ac   - Iowa
  > guitar el   - Karoryfer
  > guitar ny   - Freesound - 11573__quartertone__classicalguitar-multisampled
- University of Iowa MIS(https://theremin.music.uiowa.edu/MIS.html,經搜尋摘要):「freely available … may be downloaded and used for any projects, without restrictions」
- Freesound pack 11573:https://freesound.org/people/quartertone/packs/11573/(**這個環境讀不到,授權未確認**)
- 注意:整理者把整包標成 CC BY 3.0,但他無權改變原始取樣的授權;原始授權比 CC BY 3.0 嚴的話以原始為準

### Groove MIDI Dataset
- 來源:https://magenta.tensorflow.org/datasets/groove(下載:https://storage.googleapis.com/magentadata/datasets/groove/groove-v1.0.0-midionly.zip)
- 授權(資料集頁面與 TensorFlow Datasets 目錄):
  > The dataset is made available by Google LLC under a Creative Commons Attribution 4.0 International (CC BY 4.0) License.
- 要求引用:Jon Gillick, Adam Roberts, Jesse Engel, Douglas Eck, David Bamman. *Learning to Groove with Inverse Sequence Transformations.* ICML 2019
- 我們有修改(挑小節、換成我們的鼓件代號、重新配音色),CC BY 4.0 要求**標明有修改**
- 建議署名:*Drum grooves adapted from the Groove MIDI Dataset by Google LLC (Gillick et al., 2019), CC BY 4.0*

### POP909(計畫中,還沒用)
- 來源:https://github.com/music-x-lab/POP909-Dataset,MIT License;README:「Please cite this work if you want to use this dataset」(Wang et al., ISMIR 2020)

### Noto Serif TC / Noto Sans TC
- Google Fonts,SIL Open Font License 1.1(https://openfontlicense.org)

## 工具(不隨 App 散布)
Demucs(MIT)、Basic Pitch(Apache-2.0)、MERT、VGGish、Audiobox Aesthetics、LAION-CLAP `larger_clap_music`(Apache-2.0)只在 `tools/realism/` 離線分析時用,
不進 App。參考曲與 AI 曲的音檔從來不進 repo。
