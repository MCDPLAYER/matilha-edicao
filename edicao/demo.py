"""Demonstração de ponta a ponta, SEM nenhuma mídia sua: o kit gera um bruto sintético (tela de teste + "voz" feita de tom),
uma trilha, três sons de efeito, e roda o fluxo inteiro:

  1. mede o silêncio e escolhe o ponto exato onde a vinheta entra (fala.apos_fala);
  2. tira um respiro longo (corte) e abre tempo para um "capítulo" (mapa de tempo);
  3. mistura voz + trilha com curva + efeito em 3 camadas (audio.montar_audio);
  4. monta o vídeo de saída (corta o bruto e encaixa a cartela), normaliza para −14 LUFS e junta imagem e som;
  5. gera a EDL e roda a caça técnica no arquivo final.

  python -m edicao demo [PASTA]        (padrão: ./demo-edicao)

O vídeo de demonstração é feio de propósito: o que importa é o caminho. Leva ~1 minuto.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import audio, caca, edl
from .comum import quadros, rodar, salvar_json
from .config import FPS
from .fala import Fala
from .projeto import Projeto

DUR = 32
W, H = 1280, 720
VERDE = "0x2A5230"


def _ff(args, log):
    rodar(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args], log)


def gerar_insumos(pasta: Path):
    """Gera bruto.mp4, trilha.wav e três sons. O 'apresentador' é um tom que liga e desliga como fala, com dois silêncios longos."""
    mudo = r"(1-between(t\,16\,17.6))*(1-between(t\,24\,25.6))"
    voz = rf"aevalsrc=0.4*sin(2*PI*220*t)*between(mod(t\,4)\,0\,3.4)*{mudo}:s=48000:d={DUR}"
    log = pasta / "logs" / "insumos.log"
    _ff(["-f", "lavfi", "-i", f"testsrc2=s={W}x{H}:r={FPS}:d={DUR}", "-f", "lavfi", "-i", voz,
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
         "-shortest", str(pasta / "bruto.mp4")], log)
    _ff(["-f", "lavfi", "-i", "aevalsrc=0.3*sin(2*PI*110*t)+0.2*sin(2*PI*165*t)+0.15*sin(2*PI*220.5*t):s=48000:d=40",
         str(pasta / "trilha.wav")], log)
    _ff(["-f", "lavfi", "-i", "aevalsrc=random(0)*exp(-t*80):s=48000:d=0.25", str(pasta / "sfx-ataque.wav")], log)
    _ff(["-f", "lavfi", "-i", "aevalsrc=0.8*sin(2*PI*90*t)*exp(-t*14):s=48000:d=0.6", str(pasta / "sfx-corpo.wav")], log)
    _ff(["-f", "lavfi", "-i", "aevalsrc=0.3*random(0)*exp(-t*6):s=48000:d=1.0", str(pasta / "sfx-cauda.wav")], log)
    # transcrição sintética no mesmo formato do Whisper: duas "palavras" por surto de tom
    palavras = []
    for k in range(8):
        t0 = 4.0 * k
        for a, b in ((t0, t0 + 1.6), (t0 + 1.7, t0 + 3.4)):
            if not (16 <= a < 17.6 or 24 <= a < 25.6):
                palavras.append(dict(start=a, end=b, word="..."))
    salvar_json(pasta / "transcricao.json", dict(segments=[dict(words=palavras)]))


def escrever_projeto(pasta: Path) -> Path:
    fala = Fala(pasta / "bruto.mp4", pasta / "transcricao.json", cache=pasta / "cache" / "fala.json")
    fc, corte = fala.apos_fala(7.6)     # 7,4–8,0 é silêncio: a cartela entra logo depois da última palavra
    cortes = [[15.6, 17.5]]             # respiro longo (tom mudo de 15,4 a 17,7): sai
    if corte:
        cortes.append(list(corte))      # e o resto do silêncio onde a cartela entrou também
    sfx_cartela = [dict(arquivo="sfx-ataque.wav", ancora_ms=0, ganho_db=-8),
                   dict(arquivo="sfx-corpo.wav", ancora_ms=0, ganho_db=-12, atraso_ms=15),
                   dict(arquivo="sfx-cauda.wav", ancora_ms=0, ganho_db=-20, atraso_ms=60)]
    projeto = dict(
        bruto="bruto.mp4", transcricao="transcricao.json", cortes_s=cortes,
        insercoes=[dict(id="CAP1", em_s=fc, duracao_s=2.0, tipo="capitulo")],
        trilha=dict(blocos=[dict(bloco="A", arquivo="trilha.wav",
                                 curva_db=[[0, -60], [1, -34], [12, -34], [13, -27], [14.5, -27], [15.5, -34], [30, -34], [31.5, -60]])]),
        sfx=dict(eventos=[dict(nome="cartela", t_s=fc, camadas=sfx_cartela),
                          dict(nome="clique solto", t_s=20.0, camadas=sfx_cartela[:1])]),   # 1 camada só: o aviso do kit acusa
        saida=dict(lufs=-14, pico_db=-2.5))
    arq = pasta / "projeto.json"
    salvar_json(arq, projeto)
    return arq


def montar_video(proj: Projeto, pasta: Path, wav: Path) -> Path:
    """Vídeo de saída: cada segmento do mapa vira um pedaço (bruto cortado em quadros exatos, ou cartela verde); junta e masteriza."""
    segs = proj.mapa.segmentos()
    filtros, nomes = [], []
    for i, s in enumerate(segs):
        n = s["b"] - s["a"]
        if s["tipo"] == "base":
            a = s["bruto_a"]
            filtros.append(f"[0:v]trim=start_frame={a}:end_frame={a + n},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
        else:
            filtros.append(f"color=c={VERDE}:s={W}x{H}:r={FPS}:d={n / FPS:.6f},format=yuv420p[v{i}]")
        nomes.append(f"[v{i}]")
    filtros.append("".join(nomes) + f"concat=n={len(segs)}:v=1:a=0[out]")
    mudo = pasta / "saida-sem-som.mp4"
    rodar(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(proj.bruto), "-filter_complex", ";".join(filtros),
           "-map", "[out]", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p", str(mudo)], pasta / "logs" / "video.log")
    final = pasta / "demo-master.mp4"
    ganho = audio.masterizar(mudo, wav, final, proj.lufs, proj.pico_db - 0.1)
    print(f"  ganho de loudness aplicado: {ganho:+.2f} dB (alvo {proj.lufs:g} LUFS)")
    return final


def main(pasta: str = "demo-edicao"):
    pasta = Path(pasta).resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    print(f"[1/5] gerando insumos sintéticos em {pasta}")
    gerar_insumos(pasta)
    print("[2/5] medindo silêncio, escolhendo ponto da cartela e montando o projeto")
    proj = Projeto(escrever_projeto(pasta))
    m = proj.mapa
    print(f"  bruto {proj.n_bruto / FPS:.2f} s -> saída {m.n_saida / FPS:.2f} s "
          f"({len(m.cortes)} corte(s), {len(m.ins)} inserção(ões))")
    print("[3/5] misturando o áudio (voz + trilha com curva + efeito em camadas)")
    wav = pasta / "mix.wav"
    print("  " + audio.montar_audio(proj, wav))
    print("[4/5] montando o vídeo e masterizando")
    final = montar_video(proj, pasta, wav)
    print("[5/5] EDL + caça técnica no arquivo final")
    edl_arq = pasta / "EDL.json"
    salvar_json(edl_arq, edl.gerar_edl(proj))
    caca.cacar(final, edl=edl_arq, transcricao=pasta / "transcricao.json", bruto=proj.bruto, audio=wav,
               out=pasta / "demo-master.CACA.md")
    print(f"\nPronto. Abra {pasta / 'demo-master.mp4'} e leia {pasta / 'demo-master.CACA.md'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(*(sys.argv[1:2])))
