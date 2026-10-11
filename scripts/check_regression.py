"""CI gate: the proposed system must keep beating the baselines on the frozen special-move scenario."""
import json
import sys

res = json.load(open(sys.argv[1]))
b4 = res["B4 proposed"]
fails = []
if b4["move_accuracy"] < 0.95:
    fails.append(f"B4 move accuracy {b4['move_accuracy']:.3f} < 0.95")
if b4["move_accuracy"] <= res["B2 temporal-only"]["move_accuracy"]:
    fails.append("B4 no longer beats B2 (legal constraints stopped helping)")
if b4["move_accuracy"] <= res["B1 frame-only"]["move_accuracy"] + 0.5:
    fails.append("B4 no longer clearly beats frame-only baseline B1")
if b4["false_confirmations_per_100_moves"] > 2.0:
    fails.append(f"false confirmations/100 moves = {b4['false_confirmations_per_100_moves']:.2f} > 2.0")
print("regression gate:", "FAIL\n  " + "\n  ".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
