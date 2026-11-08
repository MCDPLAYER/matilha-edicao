"""Mapa da linha do tempo: do vídeo BRUTO para o vídeo de SAÍDA.

Duas operações mudam o tempo, e as duas são feitas em QUADROS inteiros (nunca em segundos com vírgula):
  - corte    : tira um pedaço do bruto (um retake, um respiro longo). Voz e imagem saem juntas.
  - inserção : abre tempo novo na saída (vinheta de capítulo, mini-intro) onde o bruto fica "pausado".

Com o mapa, qualquer marca feita em tempo do bruto (um SFX, um zoom, uma curva de trilha) vira tempo de saída sem conta de cabeça.
"""
from __future__ import annotations


class Mapa:
    """Cortes e inserções, tudo em quadros do bruto; devolve quadros de saída.

    cortes    : lista de (a, b) em quadros do bruto. Cortes que se tocam são fundidos.
    insercoes : lista de dicts {fc: quadro do bruto onde entra, n: quantos quadros abre, ...}
    """

    def __init__(self, n_bruto: int, cortes: list, insercoes: list):
        self.n_bruto = n_bruto
        fundidos: list = []
        for a, b in sorted(cortes):
            if fundidos and a <= fundidos[-1][1]:
                fundidos[-1][1] = max(fundidos[-1][1], b)
            else:
                fundidos.append([a, b])
        self.cortes = [tuple(x) for x in fundidos]
        self.ins = sorted(insercoes, key=lambda x: x["fc"])

    def removidos_antes(self, f: float) -> float:
        return sum(min(f, b) - a for a, b in self.cortes if f > a)

    def inseridos(self, f: float, lado: str) -> int:
        return sum(i["n"] for i in self.ins if (i["fc"] <= f if lado == "ini" else i["fc"] < f))

    def saida(self, f: float, lado: str = "ini") -> float:
        """Quadro do bruto -> quadro da saída.
        lado 'ini': a inserção que cai exatamente em f vem ANTES (o quadro f já é depois dela).
        lado 'fim': a inserção em f não entra (um intervalo que termina em f termina antes dela)."""
        return f - self.removidos_antes(f) + self.inseridos(f, lado)

    def segmentos(self) -> list:
        """Lista ordenada da saída: 'base' (pedaço contíguo do bruto) e 'ins' (inserção).
        Cada item tem a, b (quadros da saída); 'base' tem bruto_a; 'ins' tem os dados da inserção."""
        itens = [(i["fc"], 0, i) for i in self.ins] + [(a, 1, (a, b)) for a, b in self.cortes]
        itens.sort(key=lambda x: (x[0], x[1]))
        segs, cur, out = [], 0, 0
        for pos, tipo, it in itens:
            if pos > cur:
                segs.append(dict(tipo="base", a=out, b=out + pos - cur, bruto_a=cur))
                out += pos - cur
                cur = pos
            if tipo == 0:
                segs.append(dict(tipo="ins", a=out, b=out + it["n"], **{k: v for k, v in it.items() if k not in ("n", "fc")}, fc=it["fc"]))
                out += it["n"]
            else:
                cur = max(cur, it[1])
        if cur < self.n_bruto:
            segs.append(dict(tipo="base", a=out, b=out + self.n_bruto - cur, bruto_a=cur))
        return segs

    @property
    def n_saida(self) -> int:
        s = self.segmentos()
        return s[-1]["b"] if s else 0
