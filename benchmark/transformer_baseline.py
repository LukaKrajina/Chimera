"""transformer_baseline.py —— Chimera 基准测试的 Transformer 对照组。

与 benchmark/chimera_metrics_bench.qk 输出三个一一对应的指标:

  1) TRANSFORMER_ENTROPY      : 平均 attention 分布的香农熵 (nats)
     对应 Chimera 的 shannon4(测量桶计数) — 都是“内部状态分布离散度”。
  2) TRANSFORMER_SETPOINT_*   : 通过调整 temperature τ 使平均 attention 熵
     逼近目标 S*=1.0, 用与 Chimera improve_drift 相同的有限差分+定步长规则:
       τ ← τ - 0.1 * 2 * (S(τ) - S*) * dS/dτ
     记录迭代步数与最终误差。
  3) TRANSFORMER_ERROR_DETECT : 一个小 softmax 分类器 +置信度门控:
     1-max_softmax>0.5 判定为“识别到错误”, 统计检测准确率。

每个指标单行输出:  "METRIC <name>" 然后 "METRIC_VALUE <int(1000*value)>",
供 benchmark/run_benchmark.py 解析。纯 NumPy 实现, 不依赖 PyTorch。
"""
import json
import numpy as np

rng = np.random.default_rng(2026)

NAME = "transformer"


def _softmax(x):
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=-1, keepdims=True)


def _build():
    """1-layer Transformer encoder: 2 heads, d_model=8, 4 tokens."""
    V = 8  # vocab
    T = 4  # seq len
    D = 8  # d_model
    return dict(V=V, T=T, D=D,
                E=rng.normal(0, 0.5, (V, D)),
                P=rng.normal(0, 0.3, (T, D)),
                Wq=rng.normal(0, 0.2, (D, D)), Wk=rng.normal(0, 0.2, (D, D)),
                Wv=rng.normal(0, 0.2, (D, D)), Wo=rng.normal(0, 0.2, (D, D)),
                ffn1=rng.normal(0, 0.2, (D, 2 * D)), b1=np.zeros(2 * D),
                ffn2=rng.normal(0, 0.2, (2 * D, D)), b2=np.zeros(D))


def attention_entropy(model, tokens, tau_temp):
    """平均 attention 分布的香农熵; tau_temp<0 等价于 Chimera 的 dt 放大。"""
    ents = []
    for tok in tokens:
        x = model["E"][tok] + model["P"]           # (T,D)
        q = x @ model["Wq"]; k = x @ model["Wk"]; v = x @ model["Wv"]
        heads = D_h = model["D"] // 2
        for h in range(2):
            s = h * heads
            qh = q[:, s:s + D_h]; kh = k[:, s:s + D_h]; vh = v[:, s:s + D_h]
            logits = (qh @ kh.T) / np.sqrt(D_h) / np.maximum(tau_temp, 1e-3)
            p = _softmax(logits)                      # (T,T)
            ents.append(-(p * np.log(p + 1e-12)).sum(-1).mean())
    return float(np.mean(ents))


def forward_logits(model, tokens):
    x = model["E"][tokens] + model["P"]
    q = x @ model["Wq"]; k = x @ model["Wk"]; v = x @ model["Wv"]
    heads = model["D"] // 2
    ctx = np.zeros_like(x)
    for h in range(2):
        s = h * heads
        qh = q[:, s:s + heads]; kh = k[:, s:s + heads]; vh = v[:, s:s + heads]
        p = _softmax((qh @ kh.T) / np.sqrt(heads))
        ctx[:, s:s + heads] = p @ vh
    out = ctx @ model["Wo"]
    h1 = np.maximum(0, out @ model["ffn1"] + model["b1"])
    return h1 @ model["ffn2"] + model["b2"]


def entropy_metric(model, tokens):
    return attention_entropy(model, tokens, tau_temp=1.0)


def setpoint_metric(model, tokens, target=1.0, max_iters=30, tol=0.05):
    """与 Chimera improve_drift(mode=0) 相同的更新律。"""
    tau = 0.5
    it_done = max_iters
    err = abs(attention_entropy(model, tokens, tau) - target)
    for it in range(max_iters):
        err = abs(attention_entropy(model, tokens, tau) - target)
        if err < tol:
            it_done = it + 1
            break
        h = 0.01
        dplus = attention_entropy(model, tokens, tau + h)
        dminus = attention_entropy(model, tokens, max(tau - h, 1e-3))
        grad = (dplus - dminus) / (2 * h)
        S = attention_entropy(model, tokens, tau)
        dl = 2 * (S - target) * grad
        tau = tau - 0.1 * dl
        tau = min(max(tau, 1e-3), 5.0)
    err_final = abs(attention_entropy(model, tokens, tau) - target)
    return it_done, err_final


def _forward_with_embed(model, emb):
    """emb: (T,D) 直接作为 embedding, 不经过 model["E"] 查表。"""
    x = emb
    q = x @ model["Wq"]; k = x @ model["Wk"]; v = x @ model["Wv"]
    heads = model["D"] // 2
    ctx = np.zeros_like(x)
    for h in range(2):
        s = h * heads
        qh = q[:, s:s + heads]; kh = k[:, s:s + heads]; vh = v[:, s:s + heads]
        p = _softmax((qh @ kh.T) / np.sqrt(heads))
        ctx[:, s:s + heads] = p @ vh
    out = ctx @ model["Wo"]
    h1 = np.maximum(0, out @ model["ffn1"] + model["b1"])
    return h1 @ model["ffn2"] + model["b2"]


def error_detect_metric(model, tokens, labels, noise_trials=16):
    """训练小 softmax 分类器(200 步 SGD), 然后评估置信度门控的错误识别。"""
    W = rng.normal(0, 0.3, (model["D"], 4))
    b = np.zeros(4)
    lr = 0.1
    for _ in range(200):
        for tok, lab in zip(tokens, labels):
            feats = forward_logits(model, tok)[0]
            p = _softmax(W.T @ feats + b)
            g = p; g[lab] -= 1
            W -= lr * np.outer(feats, g)
            b -= lr * g
    correct = 0
    for i, (tok, lab) in enumerate(zip(tokens, labels)):
        clean = (i % 2 == 0)
        emb = model["E"][tok] + model["P"]
        if not clean:
            emb = emb + rng.normal(0, 2.0, emb.shape)
        logits = _forward_with_embed(model, emb)
        probs = _softmax(W.T @ logits[0] + b)
        flagged = (1.0 - probs.max()) > 0.5
        if flagged == (not clean):
            correct += 1
    return correct / len(tokens)


def main():
    model = _build()
    tokens = [rng.integers(0, model["V"], model["T"]) for _ in range(8)]
    labels = [i % 4 for i in range(8)]

    ent = entropy_metric(model, tokens)
    print("METRIC transformer_entropy")
    print(int(round(ent * 1000.0)))

    it_done, err_f = setpoint_metric(model, tokens)
    print("METRIC transformer_setpoint_iters")
    print(it_done)
    print("METRIC transformer_setpoint_err")
    print(int(round(err_f * 1000.0)))

    acc = error_detect_metric(model, tokens, labels)
    print("METRIC transformer_error_detect_acc")
    print(int(round(acc * 1000.0)))


if __name__ == "__main__":
    main()