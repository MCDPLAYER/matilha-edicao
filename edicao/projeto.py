"""Leitura do `projeto.json`: tudo que descreve UM vídeo, num arquivo só, com caminhos relativos à pasta dele.

Exemplo completo em `exemplos/projeto.exemplo.json`. Campos:

  bruto          vídeo bruto (já decupado) — obrigatório
  voz            (opcional) áudio de voz mais limpo, com a MESMA duração do bruto; se faltar, usa o áudio do bruto
  transcricao    (opcional) JSON de palavras com tempo (Whisper / faster-whisper)
  cortes_s       [[ini, fim], ...] pedaços do bruto a tirar (retakes), em segundos do bruto
  insercoes      [{"id","em_s","duracao_s","tipo","vo","vo_em_s"}] tempo novo aberto na saída (capítulo, mini-intro);
                 `vo` (opcional) = locução que toca durante a inserção, `vo_em_s` = quanto depois do início ela entra
  trilha         {"blocos":[{"bloco","arquivo","curva_db":[[t, dB], ...]}]}  música por trecho, com curva de volume
  sfx            {"eventos":[{"t_s","nome","camadas":[{"arquivo","ancora_ms","ganho_db","atraso_ms"}]}]}
  tempo_das_marcas  "bruto" (padrão) ou "saida": em que régua estão os tempos de trilha e sfx
  saida          {"lufs": -14, "pico_db": -2.5}

Dois princípios que o formato embute:
  - música e efeitos são ESCOLHIDOS à mão por quem edita; o código só ENCAIXA (posição, curva, nível);
  - efeito em CAMADAS: cada evento junta 2–3 sons (ataque + corpo + cauda), nunca um som seco sozinho.
"""
from __future__ import annotations

import json
from pathlib import Path

from .comum import quadros, sonda
from .config import CFG, FPS
from .mapa import Mapa


class Projeto:
    def __init__(self, caminho):
        self.arquivo = Path(caminho).resolve()
        self.raiz = self.arquivo.parent
        self.dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        d = self.dados
        self.bruto = self._p(d["bruto"])
        self.voz = self._p(d["voz"]) if d.get("voz") else None
        self.transcricao = self._p(d["transcricao"]) if d.get("transcricao") else None
        self.cortes_s = [tuple(x) for x in d.get("cortes_s", [])]
        self.insercoes_def = d.get("insercoes", [])
        self.trilha = d.get("trilha") or {}
        self.sfx = d.get("sfx") or {}
        self.tempo_das_marcas = d.get("tempo_das_marcas", "bruto")
        self.lufs = float(d.get("saida", {}).get("lufs", CFG["lufs_alvo"]))
        self.pico_db = float(d.get("saida", {}).get("pico_db", CFG["pico_db"]))
        info = sonda(self.bruto)
        if not info or not info["video"]:
            raise SystemExit(f"bruto não encontrado ou ilegível: {self.bruto}")
        self.info_bruto = info
        self.n_bruto = info["video"]["nb_frames"] or round(info["dur"] * FPS)
        self.mapa = self._mapa()

    def _p(self, rel) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.raiz / p

    def _mapa(self) -> Mapa:
        cortes = [(quadros(a), quadros(b)) for a, b in self.cortes_s]
        ins = [dict(fc=quadros(i["em_s"]), n=quadros(i["duracao_s"]), slot=i.get("id", f"INS{k}"), kind=i.get("tipo", "capitulo"),
                    vo=i.get("vo"), vo_em_s=float(i.get("vo_em_s", 0.3)))
               for k, i in enumerate(self.insercoes_def)]
        return Mapa(self.n_bruto, cortes, ins)

    def arquivo_voz(self) -> Path:
        """Voz limpa se existir com a duração do bruto (±50 ms); senão o próprio bruto."""
        if self.voz and self.voz.exists():
            dv = (sonda(self.voz) or {}).get("dur") or 0
            if abs(dv - self.info_bruto["dur"]) < 0.05:
                return self.voz
        return self.bruto

    def resolver(self, rel) -> Path:
        return self._p(rel)
