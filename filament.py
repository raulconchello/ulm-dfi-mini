"""Rough filament estimate per printed part (no slicer needed).

Assumes ~1 mm of solid skin (perimeters + top/bottom), 15 % infill inside,
PLA at 1.24 g/cm3 and 5 % extra for brim and purge.

Run:  uv run python filament.py
"""

import contextlib
import io
import runpy

RHO, SKIN, INFILL, EXTRA = 1.24, 1.0, 0.15, 1.05
EUR_PER_KG = (12, 18)  # budget PLA in Germany

with contextlib.redirect_stdout(io.StringIO()):
    model = runpy.run_path("model.py")

total, by_colour = 0.0, {}
for p in model["parts"]:
    if not p["printed"]:
        continue
    s = p["shape"]
    skin = min(s.volume, s.area * SKIN)
    grams = (skin + INFILL * (s.volume - skin)) / 1000 * RHO * EXTRA
    total += grams
    by_colour[p["mat"]] = by_colour.get(p["mat"], 0) + grams
    print(f"{p['name']:<16} {p['mat']:<12} {grams:6.0f} g")

print()
for colour, grams in sorted(by_colour.items(), key=lambda kv: -kv[1]):
    print(f"{colour:<12} {grams:6.0f} g")
lo, hi = (total / 1000 * e for e in EUR_PER_KG)
print(f"\ntotal {total:.0f} g  ->  {lo:.0f}-{hi:.0f} EUR of PLA")
