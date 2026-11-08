"""Regras de vão entre peças — o que impede o "frame solto" e a "lasca".

Uma linha do tempo é uma lista de CAMADAS (dicts) com, no mínimo:
    {"camada": "midia" | "card" | "motion" | "cta" | "mini-intro" | "capitulo" | "tela-final" | "selo",
     "slot": "S010", "a": quadro_inicial_da_saida, "b": quadro_final_da_saida (exclusivo)}
e, opcionais: "quadros_arquivo" (quantos quadros o arquivo da peça tem), "pula" (quadros pulados no começo da peça),
"partes": [{"ss": início no clipe, "disp": segundos disponíveis}] (mídia).

Por que existe: o apresentador sozinho na tela por menos de ~1 s entre duas peças lê como "o vídeo travou / quadro solto".
As funções abaixo fecham esses vãos de um jeito fixo e previsível, sem nunca congelar imagem.
"""
from __future__ import annotations

from .config import FPS

PECAS = ("midia", "card", "motion", "cta", "selo", "mini-intro", "capitulo", "tela-final")
ESTICAVEIS = ("card", "motion", "cta")      # peças com arquivo próprio que podem esticar até o fim do arquivo


def puxar(c: dict, g: int, fps: int = FPS):
    """A mídia começa g quadros mais cedo — e mais cedo TAMBÉM na fonte (assim não precisa repetir imagem no fim)."""
    c["a"] -= g
    if len(c.get("partes") or []) == 1:
        p0 = dict(c["partes"][0])
        volta = min(p0["ss"], g / fps)
        p0["ss"] -= volta
        p0["disp"] += volta
        c["partes"] = [p0]


def fechar_gui_solto(camadas: list, avisos: list, fps: int = FPS, limite_s: float = 1.0) -> tuple[int, int]:
    """Fecha os vãos de apresentador-sozinho menores que `limite_s` entre duas peças, nesta ordem de preferência:
       1. a mídia de antes estica (a imagem nunca congela: use `plano_estica` no render);
       2. o card/motion de antes estica até o fim do arquivo dele;
       3. a mídia seguinte começa mais cedo (na fonte também);
       4. a peça seguinte entra até 6 quadros mais cedo.
    Devolve (fechados, sobrando) e acrescenta um aviso por vão que não deu para fechar sozinho."""
    pc = [c for c in camadas if c["camada"] in PECAS]
    uniao: list = []
    for a, b in sorted((c["a"], c["b"]) for c in pc):
        if uniao and a <= uniao[-1][1]:
            uniao[-1][1] = max(uniao[-1][1], b)
        else:
            uniao.append([a, b])
    lim = round(limite_s * fps)
    ok = resto = 0
    for (_, g0), (g1, _) in zip(uniao, uniao[1:]):
        if not 0 < g1 - g0 < lim:
            continue
        antes = [c for c in pc if c["b"] == g0]
        depois = [c for c in pc if c["a"] == g1]
        m = next((c for c in antes if c["camada"] == "midia"), None)
        if m is not None:
            m["b"] = g1
            ok += 1
            continue
        fim = g0
        for c in antes:
            if c["camada"] in ESTICAVEIS and c.get("quadros_arquivo"):
                teto = c["a"] + c["quadros_arquivo"] - c.get("pula", 0)
                if teto > c["b"]:
                    c["b"] = min(g1, teto)
                    fim = max(fim, c["b"])
        if fim >= g1:
            ok += 1
            continue
        m = next((c for c in depois if c["camada"] == "midia"), None)
        if m is not None:
            puxar(m, g1 - fim, fps)
            ok += 1
            continue
        o = next((c for c in depois if c["camada"] in (*ESTICAVEIS, "selo")), None)
        if o is not None and g1 - fim <= 6:
            o["a"] = fim
            ok += 1
            continue
        resto += 1
        avisos.append(f"vão de {(g1 - fim) / fps:.2f}s em q{fim} "
                      f"({'/'.join(c['slot'] for c in antes)} -> {'/'.join(c['slot'] for c in depois)}): sem como fechar sozinho")
    avisos.append(f"apresentador sozinho < {limite_s:g} s entre peças: {ok} fechados, {resto} sobrando")
    return ok, resto


def esticar_midia_ate_a_proxima(camadas: list, fps: int = FPS, max_s: float = 1.0) -> int:
    """Vão curto (até `max_s`) entre duas mídias: a primeira estica até a segunda — o apresentador por menos disso lê como piscada.
    Vão maior é apresentador DE PROPÓSITO e fica. Devolve quantos vãos fechou."""
    md = sorted((c for c in camadas if c["camada"] == "midia"), key=lambda c: c["a"])
    n = 0
    for c0, c1 in zip(md, md[1:]):
        if 0 < c1["a"] - c0["b"] <= round(max_s * fps):
            c0["b"] = c1["a"]
            n += 1
    return n
