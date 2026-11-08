"""EDL (lista de decisão de edição) no formato que a caça técnica lê — e que serve de "mapa" do vídeo para humanos.

Cada TRECHO é um pedaço da saída em que o conjunto de camadas não muda. Um trecho tem:
  saida / saida_quadros   início e fim na saída (s e quadros)
  bruto                   [ini, fim] do bruto que aparece ali, ou None se for inserção
  camada_principal        'apresentador' | 'midia' | 'capitulo' | 'tela-final'
  fonte_principal         arquivo ou rótulo do que domina a tela
  camadas                 [{"camada": "base", "fonte": "apresentador", "bruto": [...], "coberto_por_midia": bool},
                           {"camada": "midia", "slot": "S010", "arquivo": "...", "origem": "autor X (opcional)"},
                           {"camada": "card" | "motion" | "cta" | "selo" | "shutter" | ..., "slot": "..."}]

`gerar_edl(proj, camadas)` quebra a linha do tempo em cada borda de segmento/camada e preenche os trechos.
`camadas` usa o mesmo formato de `vaos.py` ({"camada","slot","a","b", ...}) e é opcional.
"""
from __future__ import annotations

from .config import FPS
from .projeto import Projeto

APRESENTADOR = "apresentador"


def gerar_edl(proj: Projeto, camadas: list | None = None) -> dict:
    camadas = camadas or []
    segs = proj.mapa.segmentos()
    n = segs[-1]["b"] if segs else 0
    pontos = {0, n}
    for sg in segs:
        pontos |= {sg["a"], sg["b"]}
    for c in camadas:
        pontos |= {max(0, min(n, c["a"])), max(0, min(n, c["b"]))}
    pontos = sorted(pontos)
    trechos = []
    for a, b in zip(pontos, pontos[1:]):
        if b <= a:
            continue
        sg = next(s for s in segs if s["a"] <= a < s["b"])
        ativas = sorted((c for c in camadas if c["a"] <= a < c["b"]), key=lambda c: c.get("ordem", 5))
        midia = next((c for c in ativas if c["camada"] == "midia"), None)
        cam: list = []
        bruto = None
        if sg["tipo"] == "base":
            ba = sg["bruto_a"] + (a - sg["a"])
            bruto = [round(ba / FPS, 4), round((ba + b - a) / FPS, 4)]
            cam.append(dict(camada="base", fonte=APRESENTADOR, bruto=bruto, coberto_por_midia=bool(midia)))
        else:
            cam.append(dict(camada="base", fonte=f"{APRESENTADOR} (fundo da inserção)", bruto=None))
            cam.append(dict(camada=sg.get("kind", "capitulo"), slot=sg.get("slot")))   # 'capitulo' ou 'mini-intro'
        for c in ativas:
            item = dict(camada=c["camada"], slot=c.get("slot"))
            for k in ("arquivo", "origem", "layout"):
                if c.get(k):
                    item[k] = c[k]
            cam.append(item)
        if midia:
            principal, fonte = "midia", str(midia.get("arquivo") or midia.get("slot"))
        elif sg["tipo"] == "ins":
            principal, fonte = "capitulo", str(sg.get("slot"))
        else:
            principal, fonte = APRESENTADOR, APRESENTADOR
        trechos.append(dict(saida=[round(a / FPS, 4), round(b / FPS, 4)], saida_quadros=[a, b], bruto=bruto,
                            camada_principal=principal, fonte_principal=fonte, camadas=cam))
    return dict(gerado_por="edicao.edl", bruto=str(proj.bruto), quadros_bruto=proj.n_bruto, duracao_saida_s=round(n / FPS, 3),
                quadros_saida=n, n_trechos=len(trechos), trechos=trechos)
