"""A small transformer for joint intent classification and slot filling.

Written from scratch — the tokeniser, the scaled dot-product attention, the
multi-head wrapper, the encoder block and the two heads are all here rather than
imported from ``nn.TransformerEncoder``. The point of the exercise is to own the
architecture, and a 1–2M parameter encoder over a ~700-word domain vocabulary
trains on a CPU in minutes.

**Joint, not two models.** Intent and slots are predicted from one shared
encoder: knowing the sentence is an undercut question tells you a bare number is
probably a lap, and seeing "laps old" tells you the sentence is about a duel. The
two tasks inform each other, so they share representations and are trained with a
summed loss.

**Slots are BIO tags, not a regex.** Each token is labelled B-/I-/O against a slot
type, so the model learns *where a value sits in a sentence* rather than which
words to look for. That is the whole bet against the rule parser: it should
generalise to phrasings nobody wrote a pattern for.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from f1se.nlu.lexicon import normalise
from f1se.nlu.schema import Intent, ParsedQuery, Slots

PAD, UNK, CLS = "<pad>", "<unk>", "<cls>"

# Slot types the tagger can mark. Scalars only — the ones that appear as literal
# spans in the sentence. Derived fields (objective, max_stops) come from intent
# plus keyword cues and are handled after decoding.
SLOT_TYPES = [
    "track", "season", "current_lap",
    "your_compound", "your_age",
    "rival_compound", "rival_age",
    "rival_driver", "gap",
]
TAGS = ["O"] + [f"{p}-{s}" for s in SLOT_TYPES for p in ("B", "I")]
TAG2ID = {t: i for i, t in enumerate(TAGS)}
INTENTS = [i.value for i in Intent]
INTENT2ID = {v: i for i, v in enumerate(INTENTS)}


# --------------------------------------------------------------------------- #
# Tokeniser
# --------------------------------------------------------------------------- #
@dataclass
class Tokenizer:
    """Word-level, built from the training corpus.

    Word-level is the right call for a closed domain: the vocabulary is small
    and every meaningful token ("softs", "monza", "lap") is a whole word. Sub-word
    tokenisation would buy nothing but sequence length. Numbers are collapsed to
    a single <num> token — the model needs to know *that* a number is there and
    what role it plays; the digits are read back off the surface string.
    """

    vocab: list[str]

    def __post_init__(self):
        self.stoi = {w: i for i, w in enumerate(self.vocab)}

    @classmethod
    def build(cls, texts: list[str], min_count: int = 1) -> "Tokenizer":
        counts: dict[str, int] = {}
        for t in texts:
            for w in cls.split(t):
                counts[w] = counts.get(w, 0) + 1
        words = sorted(w for w, c in counts.items() if c >= min_count)
        return cls([PAD, UNK, CLS, *words])

    @staticmethod
    def split(text: str) -> list[str]:
        out = []
        for w in normalise(text).split():
            out.append("<num>" if any(ch.isdigit() for ch in w) else w)
        return out

    def encode(self, text: str, max_len: int) -> tuple[list[int], list[str]]:
        toks = self.split(text)[: max_len - 1]
        ids = [self.stoi[CLS]] + [self.stoi.get(t, self.stoi[UNK]) for t in toks]
        ids += [self.stoi[PAD]] * (max_len - len(ids))
        return ids[:max_len], toks

    def __len__(self) -> int:
        return len(self.vocab)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
def _build_torch():
    """Imported lazily: inference ships without torch (see NumpyIntentSlot)."""
    import torch
    import torch.nn as nn

    class MultiHeadSelfAttention(nn.Module):
        """Scaled dot-product attention, multi-head, written out.

        softmax(QK^T / sqrt(d_k)) V, with the heads split along the feature
        dimension and re-joined after. The mask zeroes padding *before* the
        softmax so pad positions can never contribute probability mass.
        """

        def __init__(self, d_model: int, n_heads: int):
            super().__init__()
            assert d_model % n_heads == 0
            self.h, self.dk = n_heads, d_model // n_heads
            self.q = nn.Linear(d_model, d_model)
            self.k = nn.Linear(d_model, d_model)
            self.v = nn.Linear(d_model, d_model)
            self.o = nn.Linear(d_model, d_model)

        def forward(self, x, mask):
            B, T, D = x.shape
            def heads(t):
                return t.view(B, T, self.h, self.dk).transpose(1, 2)
            q, k, v = heads(self.q(x)), heads(self.k(x)), heads(self.v(x))
            att = (q @ k.transpose(-2, -1)) / math.sqrt(self.dk)
            att = att.masked_fill(~mask[:, None, None, :], float("-inf"))
            att = att.softmax(-1)
            out = (att @ v).transpose(1, 2).contiguous().view(B, T, D)
            return self.o(out)

    class EncoderBlock(nn.Module):
        """Pre-norm block: norm -> attention -> residual -> norm -> FFN -> residual.

        Pre-norm because it trains stably at this depth without a warmup
        schedule, which keeps the training loop short enough to read.
        """

        def __init__(self, d_model: int, n_heads: int, ff: int, dropout: float):
            super().__init__()
            self.n1, self.n2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
            self.att = MultiHeadSelfAttention(d_model, n_heads)
            self.ff = nn.Sequential(
                nn.Linear(d_model, ff), nn.GELU(), nn.Dropout(dropout), nn.Linear(ff, d_model)
            )
            self.drop = nn.Dropout(dropout)

        def forward(self, x, mask):
            x = x + self.drop(self.att(self.n1(x), mask))
            return x + self.drop(self.ff(self.n2(x)))

    class IntentSlotTransformer(nn.Module):
        def __init__(self, vocab: int, n_intents: int, n_tags: int, *,
                     d_model=128, n_heads=4, layers=3, ff=256, dropout=0.1, max_len=48):
            super().__init__()
            self.emb = nn.Embedding(vocab, d_model, padding_idx=0)
            self.pos = nn.Embedding(max_len, d_model)
            self.blocks = nn.ModuleList(
                [EncoderBlock(d_model, n_heads, ff, dropout) for _ in range(layers)])
            self.norm = nn.LayerNorm(d_model)
            self.intent_head = nn.Linear(d_model, n_intents)
            self.tag_head = nn.Linear(d_model, n_tags)

        def forward(self, ids):
            mask = ids != 0
            pos = torch.arange(ids.size(1), device=ids.device)[None, :]
            x = self.emb(ids) + self.pos(pos)
            for b in self.blocks:
                x = b(x, mask)
            x = self.norm(x)
            # Position 0 is <cls>: a slot that attends over everything and
            # carries no token meaning of its own, so it is free to become a
            # sentence summary.
            return self.intent_head(x[:, 0]), self.tag_head(x)

    return torch, nn, IntentSlotTransformer


# --------------------------------------------------------------------------- #
# Torch-free inference
# --------------------------------------------------------------------------- #
@dataclass
class NumpyIntentSlot:
    """Forward pass in numpy, so the deployed API needs no torch.

    Mirrors the same architecture the training code defines — the same trick the
    LSTM nowcast uses (`models/lap_time.py`), for the same reason: a 500 MB torch
    wheel on a free tier to run a 1M-parameter model is a poor trade.
    """

    w: dict
    vocab: list[str]
    d_model: int
    n_heads: int
    layers: int
    max_len: int

    def __post_init__(self):
        self.tok = Tokenizer(self.vocab)

    @classmethod
    def load(cls, path) -> "NumpyIntentSlot":
        z = np.load(Path(path), allow_pickle=False)
        meta = json.loads(str(z["meta_json"]))
        w = {k: z[k] for k in z.files if k != "meta_json"}
        return cls(w=w, vocab=meta["vocab"], d_model=meta["d_model"],
                   n_heads=meta["n_heads"], layers=meta["layers"], max_len=meta["max_len"])

    @staticmethod
    def _ln(x, g, b, eps=1e-5):
        m = x.mean(-1, keepdims=True)
        v = x.var(-1, keepdims=True)
        return (x - m) / np.sqrt(v + eps) * g + b

    @staticmethod
    def _gelu(x):
        return 0.5 * x * (1 + np.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x ** 3)))

    @staticmethod
    def _softmax(x, axis=-1):
        e = np.exp(x - x.max(axis=axis, keepdims=True))
        return e / e.sum(axis=axis, keepdims=True)

    def forward(self, ids: np.ndarray):
        w, H, dk = self.w, self.n_heads, self.d_model // self.n_heads
        T = len(ids)
        mask = ids != 0
        x = w["emb"][ids] + w["pos"][:T]
        for L in range(self.layers):
            p = f"b{L}."
            h = self._ln(x, w[p + "n1.g"], w[p + "n1.b"])
            q = (h @ w[p + "q.w"].T + w[p + "q.b"]).reshape(T, H, dk).transpose(1, 0, 2)
            k = (h @ w[p + "k.w"].T + w[p + "k.b"]).reshape(T, H, dk).transpose(1, 0, 2)
            v = (h @ w[p + "v.w"].T + w[p + "v.b"]).reshape(T, H, dk).transpose(1, 0, 2)
            att = q @ k.transpose(0, 2, 1) / math.sqrt(dk)
            att = np.where(mask[None, None, :], att, -1e9)
            out = (self._softmax(att) @ v).transpose(1, 0, 2).reshape(T, self.d_model)
            x = x + (out @ w[p + "o.w"].T + w[p + "o.b"])
            h = self._ln(x, w[p + "n2.g"], w[p + "n2.b"])
            h = self._gelu(h @ w[p + "ff0.w"].T + w[p + "ff0.b"])
            x = x + (h @ w[p + "ff1.w"].T + w[p + "ff1.b"])
        x = self._ln(x, w["norm.g"], w["norm.b"])
        intent = x[0] @ w["intent.w"].T + w["intent.b"]
        tags = x @ w["tag.w"].T + w["tag.b"]
        return intent, tags

    def parse(self, text: str) -> ParsedQuery:
        ids, toks = self.tok.encode(text, self.max_len)
        n = min(len(toks) + 1, self.max_len)
        intent_logits, tag_logits = self.forward(np.array(ids[:n]))
        p = self._softmax(intent_logits)
        intent = Intent(INTENTS[int(np.argmax(p))])
        tag_ids = np.argmax(tag_logits[1:n], axis=-1)   # skip <cls>
        return ParsedQuery(
            intent=intent,
            slots=decode_tags(text, toks, [TAGS[i] for i in tag_ids]),
            confidence=float(p.max()),
            parser="transformer",
        )


# --------------------------------------------------------------------------- #
# BIO helpers
# --------------------------------------------------------------------------- #
def decode_tags(text: str, tokens: list[str], tags: list[str]) -> Slots:
    """BIO tags -> Slots, reading literal values off the original words."""
    from f1se.nlu.lexicon import COMPOUND_ALIASES, DRIVER_ALIASES, canonical_track

    raw = normalise(text).split()
    spans: dict[str, list[str]] = {}
    cur_type: str | None = None
    cur: list[str] = []
    for i, tag in enumerate(tags[: len(raw)]):
        if tag.startswith("B-"):
            if cur_type:
                spans.setdefault(cur_type, []).append(" ".join(cur))
            cur_type, cur = tag[2:], [raw[i]]
        elif tag.startswith("I-") and cur_type == tag[2:]:
            cur.append(raw[i])
        else:
            if cur_type:
                spans.setdefault(cur_type, []).append(" ".join(cur))
            cur_type, cur = None, []
    if cur_type:
        spans.setdefault(cur_type, []).append(" ".join(cur))

    s = Slots()

    def num(v: str) -> int | None:
        digits = "".join(c for c in v if c.isdigit())
        return int(digits) if digits else None

    if "track" in spans:
        s.track = canonical_track(spans["track"][0]) or canonical_track(text)
    if "season" in spans:
        s.season = num(spans["season"][0])
    if "current_lap" in spans:
        s.current_lap = num(spans["current_lap"][0])
    if "your_age" in spans:
        s.your_age = num(spans["your_age"][0])
    if "rival_age" in spans:
        s.rival_age = num(spans["rival_age"][0])
    if "gap" in spans:
        try:
            s.gap_s = float("".join(c for c in spans["gap"][0] if c.isdigit() or c == "."))
        except ValueError:
            pass
    for key, field in (("your_compound", "your_compound"), ("rival_compound", "rival_compound")):
        if key in spans:
            setattr(s, field, COMPOUND_ALIASES.get(spans[key][0].split()[-1]))
    if "rival_driver" in spans:
        s.rival_driver = DRIVER_ALIASES.get(spans["rival_driver"][0].split()[-1])
    return s
