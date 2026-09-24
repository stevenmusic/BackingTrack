"""VGGish(Google AudioSet 的音訊嵌入模型)純 numpy 實作。
不裝 PyTorch:pypi 的 torch 是 CUDA 版,這個環境跑不起來;權重檔(.pth)是 zip + pickle,
用自訂的 Unpickler 直接讀成 numpy。架構與前處理照 harritaylor/torchvggish 與
tensorflow/models 的 vggish_input / mel_features 逐條對過。
權重:https://github.com/harritaylor/torchvggish/releases/download/v0.1/vggish-10086976.pth"""
import pickle
import numpy as np
from scipy.signal import resample_poly

SR = 16000

class _Lazy:
    """先記下要怎麼切,整個 pickle 讀完、原始資料都到手之後才真的做出陣列"""
    def __init__(self, key, offset, size, stride): self.key, self.offset, self.size, self.stride = key, offset, size, stride

def load_pth(path):
    """讀舊版(<1.6)的 torch.save 格式:magic / protocol / sys_info / 物件 / storage keys / 原始資料。
    每份 storage 的原始資料前面有 8 bytes 的元素個數"""
    import collections
    with open(path, 'rb') as f:
        for _ in range(3): pickle.load(f)                 # magic、protocol、sys_info
        dtypes = {}
        class U(pickle.Unpickler):
            def find_class(self, mod, name):
                if name == '_rebuild_tensor_v2':
                    return lambda key, off, size, stride, *a: _Lazy(key, off, tuple(size), tuple(stride))
                if name == 'OrderedDict': return collections.OrderedDict
                if name.endswith('Storage'): return name
                return super().find_class(mod, name)
            def persistent_load(self, pid):
                _, typ, key, *_ = pid
                dtypes[key] = {'FloatStorage': np.float32, 'LongStorage': np.int64}.get(typ, np.float32)
                return key
        obj = U(f).load()
        keys = pickle.load(f)
        raw = {}
        for k in keys:
            n = int(np.frombuffer(f.read(8), np.int64)[0])
            dt = np.dtype(dtypes[k]); raw[k] = np.frombuffer(f.read(n * dt.itemsize), dt)
    out = collections.OrderedDict()
    for name, t in obj.items():
        a = raw[t.key]
        out[name] = np.lib.stride_tricks.as_strided(a[t.offset:], shape=t.size,
            strides=[s * a.itemsize for s in t.stride]).copy()
    return out

def _hz_to_mel(f): return 1127.0 * np.log(1.0 + f / 700.0)

def _mel_matrix(nbins=64, nspec=257, sr=SR, lo=125.0, hi=7500.0):
    nyq = sr / 2.0
    spec_mel = _hz_to_mel(np.linspace(0.0, nyq, nspec))
    edges = np.linspace(_hz_to_mel(lo), _hz_to_mel(hi), nbins + 2)
    w = np.empty((nspec, nbins))
    for i in range(nbins):
        l, c, u = edges[i:i + 3]
        w[:, i] = np.maximum(0.0, np.minimum((spec_mel - l) / (c - l), (u - spec_mel) / (u - c)))
    w[0, :] = 0.0
    return w

_MEL = _mel_matrix()

def examples(wave, sr):
    """波形 → (N, 96, 64) 的 log-mel 例子(每個 0.96 秒、不重疊)"""
    if wave.ndim > 1: wave = wave.mean(axis=1)
    if sr != SR:
        from math import gcd
        g = gcd(int(sr), SR); wave = resample_poly(wave, SR // g, int(sr) // g)
    win, hop, nfft = 400, 160, 512
    n = 1 + (len(wave) - win) // hop
    if n <= 0: return np.zeros((0, 96, 64), np.float32)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    hann = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(win) / win)   # periodic
    spec = np.abs(np.fft.rfft(wave[idx] * hann, nfft))
    logmel = np.log(spec @ _MEL + 0.01)
    k = len(logmel) // 96
    return logmel[:k * 96].reshape(k, 96, 64).astype(np.float32)

def _conv3(x, w, b):
    # x (N,C,H,W), w (O,C,3,3), padding 1
    N, C, H, W = x.shape
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    cols = np.empty((N, C, 3, 3, H, W), np.float32)
    for i in range(3):
        for j in range(3): cols[:, :, i, j] = xp[:, :, i:i + H, j:j + W]
    out = np.einsum('ncijhw,ocij->nohw', cols, w, optimize=True) + b[None, :, None, None]
    return np.maximum(out, 0)

def _pool(x):
    N, C, H, W = x.shape
    return x[:, :, :H // 2 * 2, :W // 2 * 2].reshape(N, C, H // 2, 2, W // 2, 2).max(axis=(3, 5))

class VGGish:
    def __init__(self, path):
        self.p = {k: np.asarray(v, np.float32) for k, v in load_pth(path).items()}
    def embed(self, ex, batch=16):
        out = []
        for s in range(0, len(ex), batch):
            x = ex[s:s + batch][:, None]
            p = self.p
            x = _pool(_conv3(x, p['features.0.weight'], p['features.0.bias']))
            x = _pool(_conv3(x, p['features.3.weight'], p['features.3.bias']))
            x = _conv3(x, p['features.6.weight'], p['features.6.bias'])
            x = _pool(_conv3(x, p['features.8.weight'], p['features.8.bias']))
            x = _conv3(x, p['features.11.weight'], p['features.11.bias'])
            x = _pool(_conv3(x, p['features.13.weight'], p['features.13.bias']))
            x = x.transpose(0, 2, 3, 1).reshape(len(x), -1)          # 跟 TF 版一樣 NHWC 攤平
            for k in ('embeddings.0', 'embeddings.2', 'embeddings.4'):
                x = np.maximum(x @ p[k + '.weight'].T + p[k + '.bias'], 0)
            out.append(x)
        return np.concatenate(out) if out else np.zeros((0, 128), np.float32)
