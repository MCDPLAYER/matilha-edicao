"""Ajustes de VOLUME travados à mão — o que o editor ouviu e mexeu vence a regra automática.

Arquivo `ajustes.json` ao lado do projeto:
  {"audio": [{"id": "A1", "a": 900, "b": 960, "voz": 0, "trilha": -6, "sfx": 0, "nota": "trilha alta na TV"}]}

a/b são QUADROS da saída; os ganhos são em dB e somam onde se sobrepõem. A rampa de 15 ms nas bordas evita estalo.
Por que um arquivo e não "mexer no código": o ajuste sobrevive quando o vídeo é montado de novo, e fica documentado o porquê.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .comum import salvar_json


def ler(caminho) -> dict:
    d = {"audio": []}
    p = Path(caminho) if caminho else None
    if p and p.exists():
        try:
            lido = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(lido.get("audio"), list):
                d["audio"] = lido["audio"]
        except Exception:
            pass
    return d


def gravar(caminho, d: dict):
    salvar_json(caminho, {"audio": d.get("audio", [])})


def envelope(aj: dict, faixa: str, a: int, n: int, sr: int, spf: int):
    """Ganho linear por amostra para o bloco [a, a+n) (em amostras da saída), ou None se nenhum ajuste toca esse bloco."""
    regs = [r for r in aj["audio"] if float(r.get(faixa, 0) or 0) != 0]
    if not regs:
        return None
    env = None
    rampa = int(0.015 * sr)
    for r in regs:
        x0, x1 = int(r["a"]) * spf, int(r["b"]) * spf
        lo, hi = max(a, x0 - rampa), min(a + n, x1 + rampa)
        if hi <= lo:
            continue
        if env is None:
            env = np.zeros(n, np.float64)   # em dB
        pos = np.arange(lo, hi, dtype=np.float64)
        peso = np.clip(np.minimum((pos - (x0 - rampa)) / max(1, rampa), ((x1 + rampa) - pos) / max(1, rampa)), 0, 1)
        env[lo - a:hi - a] += float(r[faixa]) * peso
    if env is None:
        return None
    return np.power(10.0, env / 20.0).astype(np.float32)
