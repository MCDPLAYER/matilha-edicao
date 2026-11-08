"""Zoom com intenção e esticar clipe sem "pulo".

Duas decisões de método que viraram código:

1. ZOOM só para dar ênfase, SEMPRE com curva (bézier), nunca linear. "Blablabla" normal fica no plano aberto; "e atenção nisso" ganha zoom.
   Cada zoom é uma lista de chaves {"t0","t1","s0","s1","bezier":[x1,y1,x2,y2]} (tempo em segundos do bruto, escala 1.0 = sem zoom).

2. CLIPE CURTO para a cena: até 1,5x mais lento ele só estica; além disso ele vai-e-volta (para frente e para trás, 1,3x mais lento).
   O loop seco ("clipe reinicia") é lido pelo espectador como um pulo.
"""
from __future__ import annotations

from .config import FPS

LENTO_MAX = 1.5      # até aqui o clipe só fica mais lento (cabe sem repetir)
LENTO_VAIVEM = 1.3   # acima disso: vai-e-volta, nesta lentidão


def bezier(p: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Curva cúbica estilo CSS (cubic-bezier). p em [0,1] = progresso no tempo; devolve o progresso na escala."""
    p = min(1.0, max(0.0, p))

    def bx(s):
        return 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3

    def by(s):
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3

    lo, hi, s = 0.0, 1.0, p
    for _ in range(40):          # bisseção: acha o s em que bx(s) = p
        x = bx(s)
        if abs(x - p) < 1e-7:
            break
        if x > p:
            hi = s
        else:
            lo = s
        s = (lo + hi) / 2
    return by(s)


def escala_zoom(z: dict, t: float) -> float:
    """Escala do zoom `z` no tempo t (segundos do bruto), a partir das chaves."""
    ks = z["chaves"]
    if t <= ks[0]["t0"]:
        return float(ks[0]["s0"])
    for k in ks:
        if t < k["t0"]:
            return float(k["s0"])
        if t <= k["t1"]:
            return k["s0"] + (k["s1"] - k["s0"]) * bezier((t - k["t0"]) / (k["t1"] - k["t0"]), *k["bezier"])
    return float(ks[-1]["s1"])


def zoompan_filtro(z: dict, bruto_a: int, n: int, W: int, H: int, fps: int = FPS) -> str:
    """Filtro `zoompan` do ffmpeg para n quadros, começando no quadro `bruto_a` do bruto. `z['foco']` = [x, y] em 0–1.
    A escala vai como tabela quadro a quadro. O parser de expressão do ffmpeg falha com ~100 termos encadeados
    (medido: 80 ok, 110 erro), então a soma é agrupada de 8 em 8."""
    fx, fy = z["foco"]
    vals = [max(1.0, escala_zoom(z, (bruto_a + i) / fps)) for i in range(n)]
    termos = [f"eq(on\\,{i})*{v:.5f}" for i, v in enumerate(vals)]
    tab = "+".join("(" + "+".join(termos[k:k + 8]) + ")" for k in range(0, len(termos), 8))
    xexpr = f"'min(max({fx:.5f}*iw-iw/zoom/2\\,0)\\,iw-iw/zoom)'"
    yexpr = f"'min(max({fy:.5f}*ih-ih/zoom/2\\,0)\\,ih-ih/zoom)'"
    return f"zoompan=z='{tab}':x={xexpr}:y={yexpr}:d=1:s={W}x{H}:fps={fps}"


def plano_estica(precisa_s: float, disponivel_s: float) -> tuple[float, bool]:
    """Clipe de `disponivel_s` segundos para cobrir `precisa_s`: devolve (fator de lentidão, vai-e-volta?)."""
    if precisa_s <= disponivel_s * LENTO_MAX:
        return max(1.0, precisa_s / max(disponivel_s, 0.05) * 1.01), False
    return LENTO_VAIVEM, True
