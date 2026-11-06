#!/usr/bin/env python3
"""Inline data/*.json into src/template.html and write index.html."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
tpl = open(os.path.join(ROOT, "src", "template.html"), encoding="utf-8").read()
for key, fname in (("NETWORK", "network.json"), ("BACKGROUND", "background.json")):
    data = open(os.path.join(ROOT, "data", fname), encoding="utf-8").read().replace("</", "<\\/")
    marker = "/*__" + key + "__*/null"
    assert marker in tpl, marker
    tpl = tpl.replace(marker, data)
out = os.path.join(ROOT, "index.html")
open(out, "w", encoding="utf-8").write(tpl)
print("wrote", out, os.path.getsize(out), "bytes")
