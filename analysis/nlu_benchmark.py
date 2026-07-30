"""Head-to-head: hand-written rules vs the from-scratch transformer.

    python analysis/nlu_benchmark.py

Scored on two sets that answer different questions:

* **generated** — held-out template output. Measures competence on phrasings of
  the kind the model trained on. The rule parser has never seen these either,
  but they share the template vocabulary, so a strong score here is table
  stakes rather than evidence.
* **hand-written** (`data/nlu/heldout.jsonl`) — the real test. Different word
  order, register and vocabulary, written before either parser was scored, and
  never generated. Neither parser was tuned against it.

The second set is the one that decides which parser ships, because the whole
argument for a learned model is generalising to phrasings nobody wrote a rule
for. If it can't do that, the rules win and the transformer is a documented
rejection like every other model in this repo that failed to earn its place.

Slot scoring is exact-match per field, micro-averaged: a slot is right only if
it equals the gold value, and predicting a slot nobody asked for costs
precision. That is deliberately strict — a duel answered with the wrong tyre
age is wrong, not partially right.
"""

from __future__ import annotations

import json

from f1se.config import PROJECT_ROOT
from f1se.nlu.generate import build
from f1se.nlu.rules import parse as rules_parse
from f1se.nlu.schema import Intent, ParsedQuery, Slots

MODEL = PROJECT_ROOT / "data" / "processed" / "nlu_intent_slot.npz"
HELDOUT = PROJECT_ROOT / "data" / "nlu" / "heldout.jsonl"
SCORED_SLOTS = ["track", "season", "current_lap", "your_compound", "your_age",
                "rival_compound", "rival_age", "rival_driver"]


def load_heldout() -> list[tuple[str, ParsedQuery]]:
    out = []
    for line in HELDOUT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "_comment" in row:
            continue
        s = Slots(**row.get("slots", {}))
        out.append((row["q"], ParsedQuery(intent=Intent(row["intent"]), slots=s, parser="gold")))
    return out


def score(pairs, parse_fn) -> dict:
    n = len(pairs)
    intent_ok = 0
    tp = fp = fn = 0
    exact = 0
    for text, gold in pairs:
        try:
            pred = parse_fn(text)
        except Exception:
            fn += sum(1 for f in SCORED_SLOTS if getattr(gold.slots, f) is not None)
            continue
        if pred.intent is gold.intent:
            intent_ok += 1
        all_right = pred.intent is gold.intent
        for f in SCORED_SLOTS:
            g, p = getattr(gold.slots, f), getattr(pred.slots, f)
            if g is not None and p == g:
                tp += 1
            elif g is not None and p != g:
                fn += 1
                all_right = False
            elif g is None and p is not None:
                fp += 1
                all_right = False
        exact += all_right
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"n": n, "intent_acc": intent_ok / n, "slot_p": prec, "slot_r": rec,
            "slot_f1": f1, "exact": exact / n}


def _row(name: str, r: dict) -> str:
    return (f"  {name:<14} intent {r['intent_acc']:.3f}   slot P {r['slot_p']:.3f} "
            f"R {r['slot_r']:.3f} F1 {r['slot_f1']:.3f}   exact {r['exact']:.3f}")


def main() -> int:
    have_model = MODEL.exists()
    model_parse = None
    if have_model:
        from f1se.nlu.model import NumpyIntentSlot
        m = NumpyIntentSlot.load(MODEL)
        model_parse = m.parse
        meta_params = len(m.vocab)
        print(f"transformer loaded — vocab {meta_params:,}, {m.layers} layers, d={m.d_model}\n")
    else:
        print(f"!! no trained model at {MODEL}; run analysis/nlu_train.py first\n")

    # Generated set, seeded away from training (seed=0) so these are unseen.
    gen = build(2000, seed=999)
    hand = load_heldout()

    print(f"GENERATED held-out templates (n={len(gen)}) — table stakes")
    print(_row("rules", score(gen, rules_parse)))
    if model_parse:
        print(_row("transformer", score(gen, model_parse)))

    print(f"\nHAND-WRITTEN unseen phrasings (n={len(hand)}) — THE TEST")
    r_rules = score(hand, rules_parse)
    print(_row("rules", r_rules))
    if model_parse:
        r_model = score(hand, model_parse)
        print(_row("transformer", r_model))
        d_i = r_model["intent_acc"] - r_rules["intent_acc"]
        d_f = r_model["slot_f1"] - r_rules["slot_f1"]
        print(f"\n  transformer - rules:  intent {d_i:+.3f}   slot F1 {d_f:+.3f}")
        winner = "transformer" if (d_i + d_f) > 0 else "rules"
        print(f"  -> ship: {winner}")
        print("\n  Judged on the hand-written set only. The generated numbers say"
              "\n  whether each parser handles its own idiom; they do not say which"
              "\n  one survives a phrasing nobody anticipated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
