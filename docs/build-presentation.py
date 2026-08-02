#!/usr/bin/env python3
"""Assemble le deck de présentation autonome à partir de la source allégée.

Usage :  python3 docs/build-presentation.py

Remplace chaque `src="__IMG:nom__"` de presentation-cockpit-purple-team.src.html
par le PNG docs/img/<nom>.png encodé en base64, puis écrit le fichier final
presentation-cockpit-purple-team.html. Après un `make seed-demo` + refresh des
captures (skill refresh-demo-showcase), relancer ce script suffit.
"""
import base64
import pathlib
import re
import sys

DOCS = pathlib.Path(__file__).resolve().parent
SRC = DOCS / "presentation-cockpit-purple-team.src.html"
OUT = DOCS / "presentation-cockpit-purple-team.html"
IMG = DOCS / "img"


def inline(match: re.Match) -> str:
    png = IMG / f"{match.group(1)}.png"
    data = base64.b64encode(png.read_bytes()).decode("ascii")
    return f'src="data:image/png;base64,{data}"'


def main() -> int:
    html = SRC.read_text(encoding="utf-8")
    out, count = re.subn(r'src="__IMG:([a-z0-9-]+)__"', inline, html)
    if "__IMG:" in out:
        print("ERREUR : placeholders non résolus", file=sys.stderr)
        return 1
    OUT.write_text(out, encoding="utf-8")
    print(f"{OUT.name} : {count} images inlinées, {OUT.stat().st_size:,} octets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
