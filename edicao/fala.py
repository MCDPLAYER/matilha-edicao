"""Onde a fala está em silêncio — para que NENHUM corte, mídia ou card caia no meio de uma palavra.

Regra de ouro do método: toda borda (mídia, card, mini, capítulo, zoom) cai na borda de PALAVRA, medida na forma de onda.
O tempo por palavra de uma transcrição erra uns 100–200 ms; quem decide o ponto exato é a ENERGIA do áudio:
  - `vale(t)`         o trecho mais quieto perto de t (centro dos 60 ms mais silenciosos);
  - `borda(t)`        t se já estiver em silêncio, senão o vale mais próximo;
  - `apos_fala(t)`    ponto de entrada de uma inserção: logo depois da última palavra, cortando o respiro que sobra;
  - `silencio_em(t)`  o trecho contínuo de silêncio que contém t.

Os resultados ficam em cache (JSON) para a segunda rodada ser instantânea.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from .comum import NO_WINDOW, salvar_json
from .config import CACHE

SR = 16000          # taxa só para medir energia (não precisa de qualidade)
PASSO = 0.01        # energia em janelas de 10 ms
JANELA_VALE = 0.06  # o ponto de corte é o centro dos 60 ms mais quietos


class Fala:
    """Medidor de silêncio sobre um arquivo de áudio/vídeo (`fonte`) e, opcionalmente, uma transcrição com tempo por palavra.

    A transcrição esperada é o JSON do Whisper/faster-whisper:
      {"segments": [{"words": [{"start": 1.2, "end": 1.5, "word": "olá"}, ...]}, ...]}
    """

    def __init__(self, fonte, transcricao=None, cache=None):
        self.fonte = str(fonte)
        self.transcricao = Path(transcricao) if transcricao else None
        self._cache_arq = Path(cache) if cache else CACHE / f"fala-{Path(fonte).stem}.json"
        self._cache: dict | None = None
        self._palavras: list | None = None

    # -- cache
    def _c(self) -> dict:
        if self._cache is None:
            try:
                self._cache = json.loads(self._cache_arq.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}
        return self._cache

    def _gravar(self):
        salvar_json(self._cache_arq, self._cache)

    # -- palavras
    def palavras(self) -> list:
        if self._palavras is None:
            if not self.transcricao or not self.transcricao.exists():
                self._palavras = []
            else:
                t = json.loads(self.transcricao.read_text(encoding="utf-8"))
                self._palavras = sorted((float(w["start"]), float(w["end"]))
                                        for s in t.get("segments", []) for w in s.get("words", []))
        return self._palavras

    # -- energia
    def _energia(self, t0: float, t1: float) -> np.ndarray:
        """Energia RMS em janelas de 10 ms do trecho [t0, t1) da fonte."""
        t0 = max(0.0, t0)
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
               "-i", self.fonte, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
        raw = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW).stdout
        x = np.frombuffer(raw, dtype=np.float32)
        h = int(PASSO * SR)
        n = len(x) // h
        return np.sqrt(np.mean(x[:n * h].reshape(n, h).astype(np.float64) ** 2, axis=1) + 1e-12) if n else np.zeros(0)

    def vale(self, t: float, raio: float = 0.25) -> float:
        """Tempo (s) do trecho mais quieto em [t-raio, t+raio]."""
        k = f"vale|{t:.3f}|{raio:.3f}"
        c = self._c()
        if k in c:
            return c[k]
        t0 = max(0.0, t - raio)
        e = self._energia(t0, t + raio)
        if len(e) < 3:
            return t
        w = max(1, int(round(JANELA_VALE / PASSO)))
        m = np.convolve(e, np.ones(w) / w, mode="valid")
        alvo = np.arange(len(m)) * PASSO + t0 + w * PASSO / 2
        i = int(np.argmin(m + 1e-9 * np.abs(alvo - t)))   # empate (silêncio digital): fica o mais perto de t
        c[k] = round(float(alvo[i]), 3)
        self._gravar()
        return c[k]

    def db_em(self, t: float) -> float:
        """Energia (dB) dos 60 ms em volta de t."""
        k = f"db|{t:.3f}"
        c = self._c()
        if k in c:
            return c[k]
        e = self._energia(t - 0.03, t + 0.03)
        c[k] = round(float(20 * np.log10(np.mean(e) + 1e-9)), 1) if len(e) else -90.0
        self._gravar()
        return c[k]

    def borda(self, t: float, raio: float = 0.15, limiar_db: float = -40.0) -> float:
        """Borda de peça na borda da palavra. Já em silêncio = fica; no meio da fala = o vale mais quieto a ±raio.
        O mesmo t de entrada dá a mesma saída: duas peças coladas continuam coladas."""
        if self.db_em(t) <= limiar_db:
            return t
        return self.vale(t, raio)

    def silencio_em(self, t: float, limiar_db: float = -45.0, raio: float = 2.0) -> tuple:
        """O trecho contínuo de silêncio (energia abaixo do limiar) que contém t: (início, fim) em s. Fora de silêncio: (t, t)."""
        k = f"sil|{t:.3f}|{limiar_db}|{raio}"
        c = self._c()
        if k in c:
            return tuple(c[k])
        t0 = max(0.0, t - raio)
        e = 20 * np.log10(self._energia(t0, t + raio) + 1e-9)
        i = int(round((t - t0) / PASSO))
        if not (0 <= i < len(e)) or e[i] > limiar_db:
            r = (t, t)
        else:
            a = i
            while a > 0 and e[a - 1] <= limiar_db:
                a -= 1
            b = i
            while b < len(e) - 1 and e[b + 1] <= limiar_db:
                b += 1
            r = (round(t0 + a * PASSO, 3), round(t0 + (b + 1) * PASSO, 3))
        c[k] = list(r)
        self._gravar()
        return r

    def apos_fala(self, t: float, raio: float = 0.6):
        """Ponto de entrada de uma inserção (capítulo, mini-intro): devolve (fc, corte), em s da fonte.
        fc = 60 ms depois da última palavra; corte = (a, b) com o resto do silêncio até 100 ms antes da palavra seguinte
        (o respiro que sobra sai). Sem silêncio claro: o vale de sempre e nenhum corte."""
        v = self.vale(t, raio)
        ini, fim = self.silencio_em(v, limiar_db=-42.0, raio=2.0)
        if fim - ini < 0.12:
            return v, None
        fc = round(ini + 0.06, 3)
        corte = (fc, round(fim - 0.10, 3)) if (fim - 0.10) - fc > 0.12 else None
        return fc, corte

    def pausa_perto(self, t: float, raio: float = 1.5, minimo: float = 0.08):
        """A pausa entre palavras mais perto de t: (início, fim). Sem transcrição ou sem pausa no raio = None."""
        ws = self.palavras()
        melhor = None
        for (_, a1), (b0, _) in zip(ws, ws[1:]):
            if b0 - a1 < minimo:
                continue
            meio = (a1 + b0) / 2
            if abs(meio - t) <= raio and (melhor is None or abs(meio - t) < abs((melhor[0] + melhor[1]) / 2 - t)):
                melhor = (a1, b0)
        return melhor
