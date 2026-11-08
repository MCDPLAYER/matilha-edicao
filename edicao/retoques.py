"""Retoques de ÁUDIO num master que já está pronto — sem refazer a imagem (que é a parte cara).

  remix          refaz só o áudio inteiro (ex.: trocou os efeitos) e junta com a imagem do master sem recodificá-la;
  trilha-delta   mexe só no volume da TRILHA num trecho (ex.: "a música está alta aos 2:50"), somando ao WAV do master a
                 diferença entre a trilha com o ajuste e a trilha como estava, e grava o ajuste em ajustes.json para o
                 próximo master completo sair igual.

Só valem quando o plano de tempo é o MESMO do master: mexeu em corte, ordem ou duração = master de novo.
A mistura é soma linear (o limitador só dobra acima do teto de pico), então a diferença é exata fora dos picos.
"""
from __future__ import annotations

import copy
import wave
from pathlib import Path

import numpy as np

from . import ajustes as AJ
from .audio import blocos_trilha, masterizar, montar_audio, trilha_chunk
from .comum import salvar_json
from .config import SPF, SR
from .projeto import Projeto


def remix(projeto: str, video_in: str, saida: str):
    proj = Projeto(projeto)
    wav = Path(saida).with_suffix(".wav")
    resumo = montar_audio(proj, wav, 0, proj.mapa.n_saida)
    ganho = masterizar(video_in, wav, saida, proj.lufs, proj.pico_db - 0.1)
    print(f"ganho {ganho:+.2f} dB · {resumo}\nPRONTO: {saida}")


def trilha_delta(projeto: str, wav_antigo: str, wav_novo: str, rid: str, qa: int, qb: int, db: float, nota: str = ""):
    """Ajusta a trilha em `db` dB entre os quadros da saída [qa, qb) do WAV antigo; grava em wav_novo e em ajustes.json."""
    proj = Projeto(projeto)
    arq_aj = proj.raiz / "ajustes.json"
    aj_old = AJ.ler(arq_aj)
    aj_new = copy.deepcopy(aj_old)
    aj_new["audio"] = [r for r in aj_new["audio"] if r.get("id") != rid]
    aj_new["audio"].append(dict(id=rid, a=qa, b=qb, voz=0, trilha=db, sfx=0, nota=nota))
    a, n = qa * SPF, (qb - qa) * SPF
    so = np.zeros((n, 2), np.float32)
    for bl in blocos_trilha(proj, []):
        t = trilha_chunk(bl, a, n)
        if t is not None:
            so += t
    e0 = AJ.envelope(aj_old, "trilha", a, n, SR, SPF)
    e1 = AJ.envelope(aj_new, "trilha", a, n, SR, SPF)
    e0 = np.ones(n, np.float32) if e0 is None else e0
    e1 = np.ones(n, np.float32) if e1 is None else e1
    delta = so * (e1 - e0)[:, None]
    with wave.open(str(wav_antigo), "rb") as r:
        params = r.getparams()
        pcm = np.frombuffer(r.readframes(r.getnframes()), "<i2").reshape(-1, 2).astype(np.float32) / 32767
    pcm = pcm.copy()
    pcm[a:a + n] += delta
    with wave.open(str(wav_novo), "wb") as w:
        w.setparams(params)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
    AJ.gravar(arq_aj, aj_new)

    def rms(x):
        return 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)
    print(f"trilha no trecho: {rms(so * e0[:, None]):.1f} -> {rms(so * e1[:, None]):.1f} dBFS · gravado {wav_novo} · ajuste {rid}")
