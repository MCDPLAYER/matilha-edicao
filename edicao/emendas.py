"""Emendas escondidas no BRUTO: pulos de 1 quadro que já vêm na gravação decupada que o cliente/apresentador mandou.

Quem decupa (tira respiro e erro) deixa emendas de 1 quadro. Com o apresentador sozinho na tela elas viram "frame solto" —
e o defeito está no arquivo recebido, não no seu render. A solução do método: varrer o bruto UMA vez, listar as emendas, e o
plano nunca deixa uma delas à mostra (cobre com mídia, ou troca o enquadramento exatamente ali: "o corte direto do plano aberto
para um mais fechado já funciona").

Saída: JSON com [{"q": quadro, "t": segundos, "forca": ...}]. Lê em streaming (64x36 cinza). Se a leitura parar no meio,
NADA é gravado: resultado de leitura incompleta nunca vira "limpo".
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .comum import NO_WINDOW, baixa_prioridade, salvar_json, sonda
from .config import FPS

W, H = 64, 36


def varrer(bruto, log) -> list:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(bruto), "-an",
           "-vf", f"fps={FPS},scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    n, ant, dif = W * H, None, []
    with open(log, "wb") as lg:
        pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=lg, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, bufsize=1 << 20)
        while True:
            buf = pr.stdout.read(n)
            if len(buf) < n:
                break
            f = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
            dif.append(0.0 if ant is None else float(np.mean(np.abs(f - ant))))
            ant = f
        pr.wait()
    esperado = (sonda(bruto) or {}).get("dur", 0) * FPS
    if pr.returncode or len(dif) < 0.99 * esperado:
        raise SystemExit(f"leitura do bruto parou em {len(dif)} quadros (ffmpeg {pr.returncode}): nada gravado")
    d = np.array(dif)
    pulos = []
    for i in range(1, len(d) - 9):
        viz = max(np.median(d[max(0, i - 8):i]), np.median(d[i + 1:i + 9]), 0.3)
        if d[i] > 3.0 and d[i] > 8 * viz:    # pico ISOLADO no meio de tomada contínua = emenda
            pulos.append(dict(q=i, t=round(i / FPS, 3), forca=round(float(d[i]), 1)))
    return pulos


def main(bruto, saida):
    baixa_prioridade()
    p = varrer(bruto, Path(saida).with_suffix(".ffmpeg.log"))
    salvar_json(saida, dict(bruto=str(bruto), fps=FPS, pulos=p))
    print(f"{len(p)} emenda(s) no bruto -> {saida}")
