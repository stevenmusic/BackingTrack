// 母帶的最後一級:預讀限幅器(AudioWorklet)。用 Blob URL 生出 worklet,不用另外的檔案伺服器設定。
// - 預讀 5ms:增益在峰值到之前就降好,不會削波
// - true peak:每個取樣點之間用 4 倍超取樣(16 點加窗 sinc)估算,天花板以 dBTP 計
// - 放開 80ms(指數)
const CODE = `
class Limiter extends AudioWorkletProcessor {
  static get parameterDescriptors() { return [{ name: "ceiling", defaultValue: 0.89, minValue: 0.01, maxValue: 1 }]; }
  constructor() {
    super();
    this.la = Math.round(sampleRate * 0.005);
    this.buf = [new Float32Array(this.la + 1), new Float32Array(this.la + 1)];
    this.hist = [new Float32Array(16), new Float32Array(16)];
    this.pos = 0;
    this.g = 1;
    this.rel = Math.exp(-1 / (sampleRate * 0.08));
    this.peakWin = new Float32Array(this.la + 1);
    // 4 倍超取樣的三個中間相位(1/4、2/4、3/4)的 16 點加窗 sinc 係數
    this.ph = [1, 2, 3].map(k => {
      const t = new Float32Array(16);
      let sum = 0;
      for (let i = 0; i < 16; i++) {
        const x = i - 7.5 - (k / 4 - 0.5);
        const s = x === 0 ? 1 : Math.sin(Math.PI * x) / (Math.PI * x);
        const w = 0.5 + 0.5 * Math.cos(Math.PI * (i - 7.5) / 8);
        t[i] = s * w; sum += t[i];
      }
      for (let i = 0; i < 16; i++) t[i] /= sum;
      return t;
    });
  }
  truePeak(ch, x) {
    const h = this.hist[ch];
    h.copyWithin(0, 1); h[15] = x;
    let p = Math.abs(h[8]);
    for (const t of this.ph) { let y = 0; for (let i = 0; i < 16; i++) y += t[i] * h[i]; p = Math.max(p, Math.abs(y)); }
    return p;
  }
  process(inputs, outputs, params) {
    const inp = inputs[0], out = outputs[0];
    if (!inp || !inp.length) return true;
    const n = out[0].length, ceil = params.ceiling[0], L = this.la + 1;
    for (let i = 0; i < n; i++) {
      let pk = 0;
      for (let c = 0; c < out.length; c++) {
        const x = (inp[c] || inp[0])[i];
        pk = Math.max(pk, this.truePeak(c, x));
        this.buf[c][this.pos] = x;
      }
      this.peakWin[this.pos] = pk;
      let wmax = 0;
      for (let k = 0; k < L; k++) if (this.peakWin[k] > wmax) wmax = this.peakWin[k];
      const target = wmax > ceil ? ceil / wmax : 1;
      this.g = target < this.g ? target : target + (this.g - target) * this.rel;
      const rd = (this.pos + 1) % L;
      for (let c = 0; c < out.length; c++) out[c][i] = this.buf[c][rd] * this.g;
      this.pos = rd;
    }
    return true;
  }
}
registerProcessor("bt-limiter", Limiter);
`;

const loaded = new WeakMap();
/** 回傳限幅器節點;瀏覽器不支援 AudioWorklet 時回 null(呼叫端退回 DynamicsCompressor) */
export async function makeLimiter(ctx, ceilingDbTP = -1) {
  if (!ctx.audioWorklet || typeof AudioWorkletNode === "undefined") return null;
  try {
    if (!loaded.has(ctx)) {
      const url = URL.createObjectURL(new Blob([CODE], { type: "text/javascript" }));
      loaded.set(ctx, ctx.audioWorklet.addModule(url));
    }
    await loaded.get(ctx);
    const node = new AudioWorkletNode(ctx, "bt-limiter", { outputChannelCount: [2] });
    node.parameters.get("ceiling").value = 10 ** (ceilingDbTP / 20);
    return node;
  } catch {
    return null;
  }
}
