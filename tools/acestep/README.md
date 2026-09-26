# ACE-Step 1.5 實測腳本(2026-09-26)

目標:Suno 等級的伴奏,而且要照使用者的和弦。ACE-Step 1.5(MIT)在 CPU 上用 2B turbo / base、int8 量化測。
環境:`git clone https://github.com/ace-step/ACE-Step-1.5 /tmp/ace15`,模型從 Hugging Face `ACE-Step/Ace-Step1.5` 下載到 `/tmp/ace15/checkpoints`,
需要 `vector_quantize_pytorch`、`torchao==0.10.0`(配 torch 2.5.1)。CPU fp32 會用到 14GB 記憶體被 OOM 砍掉,要 int8。

| 腳本 | 做什麼 |
| --- | --- |
| `cover.py <src> <強度> <tag>` | cover:拿我們的伴奏當導引重新生成 |
| `lego.py <src> lego\|complete <track> <tag>` | 在導引上加一軌 / 補整團(要 base 模型) |
| `t2m.py` | 和弦寫在 caption 與 lyrics 裡,從零生成 |
| `chk.py` / `chords.py` | 每小節量「和弦音佔比」(隨機約 0.33)與自動辨識的和弦 |

## 結果(Fmaj7–E7–Am7–C7,110 BPM,20 秒)
| | 和弦音佔比 | 辨識到的和弦 |
| --- | --- | --- |
| 我們的引擎(導引) | 0.45 | 大致照進行 |
| cover 0.5 / 0.8 / 1.0 | 0.36 / 0.36 / 0.37 | 跑掉(0.8 全變 D) |
| lego 吉他 / 鍵盤 | 0.34 / 0.33 | 亂 |
| complete 補整團 | 0.32 | 幾乎全是 Dm |
| 和弦寫在文字裡(text2music) | **0.38** | 四小節一循環 F–E–F–G,抓到一部分 |

結論:現成的 ACE-Step **不會照小節跟和弦**,音訊導引(cover / lego / complete)都不行;文字寫和弦有一點反應。
CPU 一段 20 秒要 2–3 分鐘。XL(4B)的權重 20GB,這個容器放不下也沒有 GPU,沒測。
