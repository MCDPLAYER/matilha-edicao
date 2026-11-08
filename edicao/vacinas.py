"""Vacinas da caça técnica: cada defeito que um cliente já apontou TEM que ser achado pelo caçador.

Mexeu num limiar ou numa regra do caçador? Rode as vacinas: se uma falha, o caçador ficou cego para algo que o cliente já viu.
Chegou nota técnica nova? Ela vira vacina ANTES do conserto (o teste falha, você conserta, o teste passa).

`vacinas.json`:
  {"vacinas": [{"nota": "frame solto aos 07:21", "video": "caminho.mp4", "edl": "EDL.json" (opcional), "niveis": "..." (opcional),
                "transcricao": "..." (opcional; precisa p/ respiro), "bruto": "..." (opcional),
                "tempo_s": 441.0, "folga_s": 1.5, "tipos": ["corte relâmpago", "pulo no apresentador"]}]}

  python -m edicao vacinas vacinas.json
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from .caca import cacar
from .config import FPS

LINHA = re.compile(r"^- \*\*[\d:.]+\*\* \(q (\d+)\) · ([^·]+?) · ")


def _achados(video, niveis, edl, transcricao, bruto) -> list:
    out = Path(tempfile.gettempdir()) / f"vacina-{abs(hash((video, niveis, edl, transcricao, bruto)))}.md"
    out.unlink(missing_ok=True)
    cacar(video, edl=edl, niveis=niveis, transcricao=transcricao, bruto=bruto, out=out)
    achados = []
    for ln in out.read_text(encoding="utf-8").splitlines():
        m = LINHA.match(ln)
        if m:
            achados.append((int(m.group(1)) / FPS, m.group(2).strip()))
    return achados


def main(arquivo: str) -> int:
    vs = json.loads(Path(arquivo).read_text(encoding="utf-8"))["vacinas"]
    cache, falhas, pulou = {}, 0, 0
    for v in vs:
        if not Path(v["video"]).exists():
            pulou += 1
            print(f"⏭️  {v['nota']} · vídeo fora do disco ({Path(v['video']).name})")
            continue
        k = (v["video"], v.get("niveis"), v.get("edl"), v.get("transcricao"), v.get("bruto"))
        if k not in cache:
            cache[k] = _achados(*k)
        hit = [(t, tp) for t, tp in cache[k] if tp in v["tipos"] and abs(t - v["tempo_s"]) <= v["folga_s"]]
        falhas += not hit
        print(f"{'✅' if hit else '❌'} {v['nota']} ({v['tempo_s']:.1f} s) · " + (f"achou {hit[0][1]} em {hit[0][0]:.1f} s" if hit else "NÃO ACHOU"))
    print(f"{len(vs) - pulou - falhas}/{len(vs) - pulou} vacinas passaram" + (f" · {pulou} sem o vídeo no disco" if pulou else ""))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
