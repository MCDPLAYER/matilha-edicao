"""Configuração do kit: valores padrão + um config.json opcional.

Ordem de busca do arquivo de configuração:
  1. variável de ambiente EDICAO_CONFIG (caminho completo);
  2. ./config.json (na pasta de onde você roda o comando).

Qualquer chave que faltar usa o padrão abaixo. Veja `config.example.json`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PADRAO = dict(
    fps=60,                  # grade de tempo do projeto. 1 quadro tem sr/fps amostras de áudio (precisa dar número inteiro)
    sr=48000,                # taxa de amostragem do áudio de trabalho
    threads=2,               # threads do ffmpeg no "modo leve" (deixa a máquina respirar)
    ram_pausa_gb=1.0,        # abaixo disso o ffmpeg próprio é suspenso
    ram_retoma_gb=1.4,       # acima disso ele volta
    ram_min_render_gb=3.0,   # piso para começar um render pesado
    lufs_alvo=-14.0,         # loudness integrado final
    pico_db=-2.5,            # teto de pico da mistura (dBFS)
    pasta_cache=".cache-edicao",  # onde ficam sondas, RMS e energias já medidas
)


def carregar(caminho: str | os.PathLike | None = None) -> dict:
    cfg = dict(PADRAO)
    p = Path(caminho or os.environ.get("EDICAO_CONFIG") or "config.json")
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:  # config quebrado não derruba nada: avisa e segue com o padrão
            print(f"[edicao] aviso: {p} ilegível ({e}); usando valores padrão")
    return cfg


CFG = carregar()
FPS = int(CFG["fps"])
SR = int(CFG["sr"])
if SR % FPS:
    raise SystemExit(f"config inválida: sr ({SR}) precisa ser múltiplo de fps ({FPS}) para 1 quadro = N amostras exatas")
SPF = SR // FPS  # amostras por quadro
CACHE = Path(CFG["pasta_cache"])
