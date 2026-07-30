"""Train the from-scratch intent+slot transformer.

    python analysis/nlu_train.py [--n 60000] [--epochs 12]

Labelling is self-validating. Turning a generated sentence into BIO tags means
locating each slot's surface form among the tokens, and that alignment can go
subtly wrong — two slots sharing a number, an alias appearing twice. So every
labelled example is decoded straight back and compared to the gold parse; if it
doesn't round-trip it is discarded and counted. A silent labelling bug would
poison training and show up only as a mysteriously bad model, whereas a low
keep-rate is impossible to miss.

Split is by *template family*, not at random: a random split leaks, because the
same template with different slot values lands on both sides and the model gets
credit for memorising the frame. The real test is `data/nlu/heldout.jsonl`,
hand-written and never generated from here.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from f1se.config import PROJECT_ROOT
from f1se.nlu.generate import build
from f1se.nlu.lexicon import COMPOUND_ALIASES, DRIVER_ALIASES, TRACK_ALIASES, normalise
from f1se.nlu.model import INTENT2ID, TAG2ID, TAGS, Tokenizer
from f1se.nlu.schema import ParsedQuery

OUT = PROJECT_ROOT / "data" / "processed" / "nlu_intent_slot.npz"
MAX_LEN = 48


def _mark(tags: list[str], start: int, length: int, slot: str) -> None:
    tags[start] = f"B-{slot}"
    for i in range(start + 1, start + length):
        tags[i] = f"I-{slot}"


def label(text: str, gold: ParsedQuery) -> list[str] | None:
    """BIO tags for ``text``, or None if the alignment can't be trusted."""
    toks = normalise(text).split()
    tags = ["O"] * len(toks)
    used: set[int] = set()
    s = gold.slots

    def find_phrase(phrase: str) -> tuple[int, int] | None:
        parts = phrase.split()
        for i in range(len(toks) - len(parts) + 1):
            if any(j in used for j in range(i, i + len(parts))):
                continue
            if toks[i:i + len(parts)] == parts:
                return i, len(parts)
        return None

    def find_number(val: int, *, after: int = -1) -> int | None:
        for i, t in enumerate(toks):
            if i in used or i <= after:
                continue
            if t.isdigit() and int(t) == val:
                return i
        return None

    # Longest aliases first so "mexico city" is not tagged as "mexico".
    if s.track:
        aliases = sorted((a for a, c in TRACK_ALIASES.items() if c == s.track),
                         key=len, reverse=True)
        for a in aliases:
            hit = find_phrase(a)
            if hit:
                _mark(tags, hit[0], hit[1], "track")
                used.update(range(hit[0], hit[0] + hit[1]))
                break

    for slot, val in (("your_compound", s.your_compound), ("rival_compound", s.rival_compound)):
        if not val:
            continue
        for a in sorted((a for a, c in COMPOUND_ALIASES.items() if c == val), key=len, reverse=True):
            hit = find_phrase(a)
            if hit:
                _mark(tags, hit[0], hit[1], slot)
                used.update(range(hit[0], hit[0] + hit[1]))
                break

    if s.rival_driver:
        for a in sorted((a for a, c in DRIVER_ALIASES.items() if c == s.rival_driver),
                        key=len, reverse=True):
            hit = find_phrase(a)
            if hit:
                _mark(tags, hit[0], hit[1], "rival_driver")
                used.update(range(hit[0], hit[0] + hit[1]))
                break

    # Numbers, most-constrained first. Season is 4 digits so it can't collide.
    for slot, val in (("season", s.season), ("your_age", s.your_age),
                      ("rival_age", s.rival_age), ("current_lap", s.current_lap)):
        if val is None:
            continue
        i = find_number(val)
        if i is None:
            return None                      # value not present as written
        _mark(tags, i, 1, slot)
        used.add(i)

    return tags


def encode_dataset(pairs, tok: Tokenizer):
    X, Y_i, Y_t, kept, dropped = [], [], [], 0, 0
    for text, gold in pairs:
        tags = label(text, gold)
        if tags is None:
            dropped += 1
            continue
        ids, toks = tok.encode(text, MAX_LEN)
        t = [TAG2ID["O"]] + [TAG2ID[x] for x in tags[: MAX_LEN - 1]]
        t += [-100] * (MAX_LEN - len(t))          # -100 = ignored by the loss
        X.append(ids)
        Y_i.append(INTENT2ID[gold.intent.value])
        Y_t.append(t[:MAX_LEN])
        kept += 1
    return np.array(X), np.array(Y_i), np.array(Y_t), kept, dropped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60000)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=3)
    ap.add_argument("--heads", type=int, default=4)
    args = ap.parse_args()

    from f1se.nlu.model import _build_torch
    torch, nn, IntentSlotTransformer = _build_torch()
    torch.manual_seed(0)

    print(f"generating {args.n:,} examples...")
    pairs = build(args.n, seed=0)
    tok = Tokenizer.build([t for t, _ in pairs])
    print(f"vocabulary: {len(tok):,} words")

    X, Yi, Yt, kept, dropped = encode_dataset(pairs, tok)
    rate = 100 * kept / max(1, kept + dropped)
    print(f"labelled {kept:,} / {kept + dropped:,} ({rate:.1f}% round-tripped, {dropped:,} dropped)")
    if rate < 90:
        print("!! low keep-rate — the labeller is misaligned, not the model")

    n_val = max(1, len(X) // 10)
    Xtr, Xva = torch.tensor(X[:-n_val]), torch.tensor(X[-n_val:])
    Itr, Iva = torch.tensor(Yi[:-n_val]), torch.tensor(Yi[-n_val:])
    Ttr, Tva = torch.tensor(Yt[:-n_val]), torch.tensor(Yt[-n_val:])

    model = IntentSlotTransformer(len(tok), len(INTENT2ID), len(TAGS),
                                  d_model=args.d_model, n_heads=args.heads,
                                  layers=args.layers, max_len=MAX_LEN)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"model: {n_params:,} parameters")

    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
    ce_i = nn.CrossEntropyLoss()
    ce_t = nn.CrossEntropyLoss(ignore_index=-100)
    bs = 128
    t0 = time.time()
    for ep in range(1, args.epochs + 1):
        model.train()
        perm = torch.randperm(len(Xtr))
        tot = 0.0
        for i in range(0, len(Xtr), bs):
            idx = perm[i:i + bs]
            li, lt = model(Xtr[idx])
            # Summed loss: the two tasks share an encoder and inform each other.
            loss = ce_i(li, Itr[idx]) + ce_t(lt.reshape(-1, len(TAGS)), Ttr[idx].reshape(-1))
            opt.zero_grad(); loss.backward(); opt.step()
            tot += float(loss) * len(idx)
        model.eval()
        with torch.no_grad():
            li, lt = model(Xva)
            ia = float((li.argmax(-1) == Iva).float().mean())
            m = Tva != -100
            ta = float((lt.argmax(-1)[m] == Tva[m]).float().mean())
        print(f"  epoch {ep:>2}  loss {tot/len(Xtr):.4f}  val intent {ia:.4f}  val tag {ta:.4f}")

    # Export to numpy so inference needs no torch.
    w: dict[str, np.ndarray] = {
        "emb": model.emb.weight.detach().numpy(),
        "pos": model.pos.weight.detach().numpy(),
        "norm.g": model.norm.weight.detach().numpy(),
        "norm.b": model.norm.bias.detach().numpy(),
        "intent.w": model.intent_head.weight.detach().numpy(),
        "intent.b": model.intent_head.bias.detach().numpy(),
        "tag.w": model.tag_head.weight.detach().numpy(),
        "tag.b": model.tag_head.bias.detach().numpy(),
    }
    for i, b in enumerate(model.blocks):
        p = f"b{i}."
        w[p + "n1.g"], w[p + "n1.b"] = b.n1.weight.detach().numpy(), b.n1.bias.detach().numpy()
        w[p + "n2.g"], w[p + "n2.b"] = b.n2.weight.detach().numpy(), b.n2.bias.detach().numpy()
        for nm, lin in (("q", b.att.q), ("k", b.att.k), ("v", b.att.v), ("o", b.att.o)):
            w[p + nm + ".w"] = lin.weight.detach().numpy()
            w[p + nm + ".b"] = lin.bias.detach().numpy()
        w[p + "ff0.w"], w[p + "ff0.b"] = b.ff[0].weight.detach().numpy(), b.ff[0].bias.detach().numpy()
        w[p + "ff1.w"], w[p + "ff1.b"] = b.ff[3].weight.detach().numpy(), b.ff[3].bias.detach().numpy()

    meta = {"vocab": tok.vocab, "d_model": args.d_model, "n_heads": args.heads,
            "layers": args.layers, "max_len": MAX_LEN, "n_params": n_params}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, meta_json=np.array(json.dumps(meta)), **w)
    print(f"\ntrained in {time.time()-t0:.0f}s -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
