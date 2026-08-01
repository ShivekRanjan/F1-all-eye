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
NLU_DIR = PROJECT_ROOT / "data" / "nlu"
HELDOUT = NLU_DIR / "heldout.jsonl"
SCORED_SLOTS = ["track", "season", "current_lap", "your_compound", "your_age",
                "rival_compound", "rival_age", "rival_driver"]

#: Evaluation sets, in the order they were written, with what each is still
#: worth. A set stops being an unbiased estimate the moment it is used to make
#: decisions — `heldout.jsonl` was consulted repeatedly across a day of
#: debugging (§15), so it is kept and scored, but it now measures "did anything
#: regress" rather than "how good is this". Only a set that has never steered a
#: change can answer the second question, which is what heldout2 exists for.
SETS = [
    ("heldout.jsonl", "set 1 — spent (used for decisions; regression check only)"),
    ("heldout2.jsonl", "set 2 — fresh (never used to steer a change)"),
]


def load_heldout(path=HELDOUT) -> list[tuple[str, ParsedQuery]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "_comment" in row:
            continue
        s = Slots(**row.get("slots", {}))
        out.append((row["q"], ParsedQuery(intent=Intent(row["intent"]), slots=s, parser="gold")))
    return out


def load_sets() -> list[tuple[str, str, list]]:
    """Every evaluation set present, as (filename, description, pairs)."""
    found = []
    for name, desc in SETS:
        p = NLU_DIR / name
        if p.exists():
            pairs = load_heldout(p)
            if pairs:
                found.append((name, desc, pairs))
    return found


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
    return (f"  {name:<18} intent {r['intent_acc']:.3f}   slot P {r['slot_p']:.3f} "
            f"R {r['slot_r']:.3f} F1 {r['slot_f1']:.3f}   exact {r['exact']:.3f}")


def _models() -> list[tuple[str, object]]:
    """Every trained artifact available, shipped one first.

    More than one exists when the same config has been trained under different
    seeds. Scoring all of them is not thoroughness for its own sake: the
    hand-written set is 31 examples, and a single run cannot tell a real
    difference between the parsers from where that run happened to land.
    """
    from f1se.nlu.model import NumpyIntentSlot

    out = []
    if MODEL.exists():
        out.append(("seed 0 (shipped)", NumpyIntentSlot.load(MODEL)))
    for p in sorted(MODEL.parent.glob("nlu_seed*.npz")):
        out.append((p.stem.replace("nlu_", "").replace("seed", "seed "),
                    NumpyIntentSlot.load(p)))
    return out


def _spread(rows: list[dict], key: str) -> float:
    return max(r[key] for r in rows) - min(r[key] for r in rows)


def main() -> int:
    models = _models()
    if not models:
        print(f"!! no trained model at {MODEL}; run analysis/nlu_train.py first\n")
    else:
        m0 = models[0][1]
        print(f"transformer — vocab {len(m0.vocab):,}, {m0.layers} layers, "
              f"d={m0.d_model}, {len(models)} run(s)\n")

    # Generated set, seeded away from training (seed=0) so these are unseen.
    gen = build(2000, seed=999)
    sets = load_sets()
    if not sets:
        raise SystemExit("no evaluation sets in data/nlu/")

    print(f"GENERATED held-out templates (n={len(gen)}) — table stakes")
    print(_row("rules", score(gen, rules_parse)))
    for name, m in models:
        print(_row(name, score(gen, m.parse)))

    rows: list[dict] = []
    r_rules: dict = {}
    for _file, desc, hand in sets:
        print(f"\nHAND-WRITTEN — {desc}  (n={len(hand)})")
        r = score(hand, rules_parse)
        print(_row("rules", r))
        set_rows = []
        for name, m in models:
            rr = score(hand, m.parse)
            set_rows.append(rr)
            print(_row(name, rr))

        # The composition: transformer intent + rule slots. Scored rather than
        # asserted, because "take the better half of each" is exactly the kind
        # of claim that sounds obviously right and needs a number.
        if models:
            from f1se.nlu import compose

            print()
            for name, m in models:
                def hybrid(text, _m=m):
                    return compose(_m.parse(text), rules_parse(text))
                print(_row("hybrid " + name.split(" ")[1], score(hand, hybrid)))

        # The verdict below is read off the *last* set listed, i.e. the freshest
        # one present. A decision taken on a set that has already steered six
        # decisions is not a decision, it is a memory.
        rows, r_rules = set_rows, r

    if not rows:
        return 0

    if len(rows) > 1:
        # The spread across seeds is the resolution of this benchmark. Any gap
        # between the parsers smaller than it is not a finding, it is where the
        # run landed.
        print(f"\n  spread across {len(rows)} seeds:"
              f"  intent {_spread(rows, 'intent_acc'):.3f}"
              f"   slot F1 {_spread(rows, 'slot_f1'):.3f}"
              f"   exact {_spread(rows, 'exact'):.3f}")

    d_i = [r["intent_acc"] - r_rules["intent_acc"] for r in rows]
    d_f = [r["slot_f1"] - r_rules["slot_f1"] for r in rows]
    print(f"\n  transformer - rules:  intent {min(d_i):+.3f} to {max(d_i):+.3f}"
          f"   slot F1 {min(d_f):+.3f} to {max(d_f):+.3f}")

    # A verdict per run, so a decision that flips between seeds is visible as a
    # split rather than reported as whichever run went last.
    verdicts = ["transformer" if (i + f) > 0 else "rules" for i, f in zip(d_i, d_f)]
    if len(set(verdicts)) == 1:
        print(f"  -> ship: {verdicts[0]} ({len(verdicts)}/{len(verdicts)} runs agree)")
    else:
        n_rules = verdicts.count("rules")
        print(f"  -> SPLIT: rules {n_rules}/{len(verdicts)}, "
              f"transformer {len(verdicts) - n_rules}/{len(verdicts)}")
        print("     The decision is not stable at this sample size. Decide on the"
              "\n     metric whose seed spread is smaller than the gap, and say so.")

    print("\n  Judged on the hand-written set only. The generated numbers say"
          "\n  whether each parser handles its own idiom; they do not say which"
          "\n  one survives a phrasing nobody anticipated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
