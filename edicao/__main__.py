"""Linha de comando do kit: `python -m edicao <comando> ...`"""
from __future__ import annotations

import argparse
import json
import sys

try:   # console do Windows: acento sem quebrar
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

COMANDOS = {
    "demo": "roda o fluxo inteiro num vídeo sintético (não precisa de mídia sua)",
    "sonda": "mostra resolução, fps, duração e áudio de um arquivo",
    "audio": "mistura o áudio de um projeto (voz + trilha + efeitos) num WAV",
    "master": "normaliza um WAV para o alvo de LUFS e junta com a imagem de um vídeo",
    "caca": "caça técnica no vídeo pronto (frame solto, cena repetida, trilha alta, respiro...)",
    "edl": "gera a EDL (mapa do vídeo) de um projeto",
    "emendas": "lista as emendas de 1 quadro que já vêm no bruto",
    "freeze": "mede quadros congelados (com controle no bruto)",
    "remix": "refaz só o áudio de um master pronto",
    "trilha-delta": "mexe só no volume da trilha num trecho de um master pronto",
    "vacinas": "confere se o caçador ainda acha os defeitos que já foram apontados",
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("uso: python -m edicao <comando> [...]\n\ncomandos:")
        for k, v in COMANDOS.items():
            print(f"  {k:<13} {v}")
        return 0
    cmd, resto = argv[0], argv[1:]
    if cmd == "demo":
        from .demo import main as m
        return m(*resto[:1])
    if cmd == "caca":
        from .caca import main as m
        return m(resto)
    if cmd == "sonda":
        from .comum import sonda
        print(json.dumps(sonda(resto[0]), ensure_ascii=False, indent=1))
        return 0
    ap = argparse.ArgumentParser(prog=f"edicao {cmd}")
    if cmd == "audio":
        ap.add_argument("projeto"); ap.add_argument("saida_wav"); ap.add_argument("--ajustes")
        a = ap.parse_args(resto)
        from .audio import montar_audio
        from .projeto import Projeto
        p = Projeto(a.projeto)
        print(montar_audio(p, a.saida_wav, 0, p.mapa.n_saida, a.ajustes))
    elif cmd == "master":
        ap.add_argument("video"); ap.add_argument("wav"); ap.add_argument("saida")
        ap.add_argument("--lufs", type=float, default=-14.0); ap.add_argument("--pico", type=float, default=-2.6)
        a = ap.parse_args(resto)
        from .audio import masterizar
        print(f"ganho aplicado: {masterizar(a.video, a.wav, a.saida, a.lufs, a.pico):+.2f} dB")
    elif cmd == "edl":
        ap.add_argument("projeto"); ap.add_argument("saida")
        a = ap.parse_args(resto)
        from .comum import salvar_json
        from .edl import gerar_edl
        from .projeto import Projeto
        salvar_json(a.saida, gerar_edl(Projeto(a.projeto)))
        print(f"EDL -> {a.saida}")
    elif cmd == "emendas":
        ap.add_argument("bruto"); ap.add_argument("saida")
        a = ap.parse_args(resto)
        from .emendas import main as m
        m(a.bruto, a.saida)
    elif cmd == "freeze":
        ap.add_argument("video"); ap.add_argument("--bruto"); ap.add_argument("--controle", nargs=2, type=float, metavar=("INI", "FIM"))
        a = ap.parse_args(resto)
        from .freeze import relatorio
        print(relatorio(a.video, a.bruto, a.controle))
    elif cmd == "remix":
        ap.add_argument("projeto"); ap.add_argument("video_in"); ap.add_argument("saida")
        a = ap.parse_args(resto)
        from .retoques import remix
        remix(a.projeto, a.video_in, a.saida)
    elif cmd == "trilha-delta":
        ap.add_argument("projeto"); ap.add_argument("wav_antigo"); ap.add_argument("wav_novo"); ap.add_argument("id")
        ap.add_argument("quadro_ini", type=int); ap.add_argument("quadro_fim", type=int); ap.add_argument("db", type=float)
        ap.add_argument("--nota", default="")
        a = ap.parse_args(resto)
        from .retoques import trilha_delta
        trilha_delta(a.projeto, a.wav_antigo, a.wav_novo, a.id, a.quadro_ini, a.quadro_fim, a.db, a.nota)
    elif cmd == "vacinas":
        from .vacinas import main as m
        return m(resto[0])
    else:
        print(f"comando desconhecido: {cmd}\nrode `python -m edicao --help`")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
