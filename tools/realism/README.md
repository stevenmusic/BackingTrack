# 伴奏真實度評測(eval)

判斷「伴奏聽起來像不像真的錄音」,而且每次改程式都能重跑、比較。兩把尺:

| | 怎麼量 | 當什麼用 |
| --- | --- | --- |
| **你的盲聽分數** | [伴奏盲聽台](https://claude.ai/artifact/GxmtQqTjiCE1jTSrGYL8ek):一段 10 秒,1–5 分,勾出哪件樂器假 | **標準答案** |
| **VGGish 自動評分** | Google AudioSet 的音訊嵌入模型,算跟真實錄音的距離(FAD)與判別器機率 | 輔助,之後用你的分數去校正它 |

## 流程
```
1. 改 index.html
2. cases.json 加一組新版本  →  node render.mjs          # 錄片段,聲學特徵寫進 db/clips.jsonl
3. python realism.py score                                # VGGish:P(真)、最近距離、各組 FAD → db/scores.jsonl
4. 片段放上盲聽台:**WAV 包成 base64 的 JSON**(`clips/<id>.json`,`{type, b64}`)再發佈、db 的 clips 集合加一筆。
   artifact 的附屬檔案**直接放 WAV 會 403**、`<audio>` 也會被擋,JSON + fetch + Web Audio 才播得出來
5. 你打分 → 讀回 db/ratings.jsonl → python realism.py analyze   # 寫進 KNOWLEDGE.md
```

## 環境(雲端容器)
- **取樣**:CDN 被擋,從 GitHub blobless clone 到 `/tmp/smp/<repo>`,render.mjs 用 `page.route` 對到本機。
  需要的 repo:`sfzinstruments/{jlearman.jRhodes3c, virtuosity_drums, karoryfer.black-and-blue-basses, dsmolken.double-bass}`、
  `nbrosowsky/tonejs-instruments`、`Tonejs/audio`、`tidalcycles/Dirt-Samples`。
  缺的檔案會寫進 `/tmp/smp/missing.txt`,那一筆不收(錄到的會是合成備援)
- **原始 repo 本來就沒有的檔案**(正式環境也 404)照錄,列在 `db/prod404.txt`
- **VGGish 權重**(290MB,不進 repo):
  `curl -L -o /tmp/vgg/vggish.pth https://github.com/harritaylor/torchvggish/releases/download/v0.1/vggish-10086976.pth`
  pypi 的 torch 是 CUDA 版跑不起來,所以 `vggish_np.py` 是純 numpy 實作(`pip install numpy scipy soundfile`)
- **參考曲只存嵌入不存音檔**(`db/refs/*.npy`)。版權音檔不要進 repo

## 檔案
- `cases.json` 要錄哪些片段(版本 × 曲風 × 疏密)。**舊的不要刪**,分數才能跨版本比
- `db/clips.jsonl` 每段的 id、commit、曲風、聲學特徵(RMS、peak、波峰因數、L/R 相關、八度頻帶)
- `db/scores.jsonl` / `db/summary.json` VGGish 評分
- `db/ratings.jsonl` 盲聽分數(從盲聽台的 db 讀回來)
- `KNOWLEDGE.md` 知識庫:人工整理的結論 + `analyze` 自動產生的相關分析
