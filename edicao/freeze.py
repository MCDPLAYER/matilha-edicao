"""Quadro congelado ("o vídeo travou"): mede com o `freezedetect` do ffmpeg, sempre com um CONTROLE no bruto.

O controle responde "o que o próprio bruto já tem de parado?" (um apresentador imóvel por 0,5 s conta como parado).
O resultado da montagem só se lê contra ele — sem o controle, todo plano calmo vira alarme falso e o alarme que sempre toca ninguém lê.
Os dois são medidos a 1920x1080 para o limiar de ruído ser comparável.
"""
from __future__ import annotations

import re
import subprocess

from .comum import FLAGS, tempo_txt

RE_INI = re.compile(r"freeze_start: ([0-9.]+)")
RE_DUR = re.compile(r"freeze_duration: ([0-9.]+)")


def medir(arq, ss: float | None = None, dur: float | None = None, n_db: int = -60, d: float = 0.3) -> list:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-threads", "2", "-filter_threads", "1", "-loglevel", "info"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-i", str(arq), "-an", "-vf", f"scale=1920:1080,freezedetect=n={n_db}dB:d={d}", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, creationflags=FLAGS)
    txt = r.stderr.decode("utf-8", "replace")
    ini = [float(x) for x in RE_INI.findall(txt)]
    dur_ = [float(x) for x in RE_DUR.findall(txt)]
    return [(t, dur_[i] if i < len(dur_) else None) for i, t in enumerate(ini)]   # sem duration = parado até o fim do trecho


def relatorio(arq, bruto=None, controle=None) -> str:
    """`controle` = (ini, fim) em s do bruto de um trecho com o apresentador puro, sem peças."""
    res = medir(arq)
    lin = [f"freezedetect n=-60dB d=0.3 em {arq}: {len(res)} trechos parados"]
    lin += [f"  parado a partir de {tempo_txt(t)} por {('%.2f s' % d) if d else 'até o fim'}" for t, d in res[:30]]
    if controle and bruto:
        ctl = medir(bruto, controle[0], controle[1] - controle[0])
        lin.append(f"CONTROLE (bruto {controle[0]:.0f}-{controle[1]:.0f} s, o apresentador puro): {len(ctl)} trechos parados")
        lin += [f"  parado a partir de {tempo_txt(t)} por {('%.2f s' % d) if d else 'até o fim'}" for t, d in ctl[:30]]
    return "\n".join(lin)
