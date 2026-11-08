"""Caça técnica: mede o vídeo PRONTO (pixels e som) atrás de defeitos que o público vê e o plano não mostra.

Por que olhar o arquivo final e não o plano: o plano pode estar "certo" e o render ainda assim nascer com defeito
(um pulo de 1 quadro depois do zoom, um painel que reinicia, o fundo de uma vinheta voltando no tempo). E cada conserto
pode criar defeito na emenda vizinha — por isso a regra é: **conserto = medir o vídeo INTEIRO de novo**.

Detectores (todos medem o arquivo; o EDL só serve para dizer O QUE havia ali):
  1 corte relâmpago    plano de imagem com menos de 0,4 s entre dois planos firmes (diferença quadro a quadro)
  2 cena repetida      o mesmo plano de mídia duas vezes, a mais de 20 s de distância (hash perceptual do quadro)
  3 volume pulando     fundo (trilha) ou voz mudando de nível de repente fora de vinheta (loudness em janelas)
  4 respiro sobrando   mais de 0,9 s sem fala fora de peça planejada
  5 respiro na emenda  tempo demais da última palavra até a vinheta / da vinheta até a próxima palavra
  6 apresentador solto apresentador sozinho < 1 s entre duas peças = "frame solto"
  7 lasca na vinheta   plano < 0,4 s colado na saída/entrada de capítulo ou mini = "frame passado"
  8 pulo no apresentador  pico isolado de diferença no meio de uma tomada contínua
  9 trilha subindo / encostando na voz   (lê `<wav>.niveis.json` que a mistura grava)
 10 mesma filmagem     duas mídias da mesma origem (mesmo autor / mesmo vídeo) a menos de 30 s
 11 loudness final     integrado fora do alvo, pico alto demais

Uso:
  python -m edicao caca VIDEO [--edl EDL.json] [--transcricao palavras.json] [--bruto bruto.mp4]
                              [--audio mix.wav] [--niveis mix.wav.niveis.json] [--zooms zooms.json] [--lufs -14] [--out CACA.md]

Sem EDL, os detectores de imagem e de som por transcrição seguem funcionando; os que dependem do plano ficam de fora.
Lê o vídeo UMA vez, em streaming (64x36 em cinza): nunca empilha o filme inteiro na memória.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from .config import CFG, FPS
from .comum import NO_WINDOW
from .fala import Fala

W, H = 64, 36
CORTE_DIF = 28.0      # diferença média (0-255) que conta como corte de plano
RELAMPAGO = 0.4       # plano visível menor que isso = achado
REPETE_MIN_S = 20.0   # mesma imagem de novo depois disso = cena repetida
HASH_DIST = 6         # bits diferentes no dHash de 64 bits que ainda contam como "o mesmo quadro"
RESPIRO = 0.9
RESPIRO_ANTES = 0.30   # da última palavra até a vinheta entrar
RESPIRO_DEPOIS = 0.40  # da vinheta sair até a próxima palavra
SOLTO = 1.0            # apresentador sozinho entre duas peças por menos que isso lê como "frame solto"
APRESENTADOR = "apresentador"
GENERICAS = {"pexels", "pixabay", "envato", "local", "mixkit", "tiktok", "instagram"}   # origens que não identificam uma filmagem
PLANEJADO = ("capitulo", "mini-intro", "motion", "shutter", "tela-final")               # peças que cortam rápido DE PROPÓSITO
PECAS = ("motion", "capitulo", "mini-intro", "shutter", "card", "cta", "selo", "tela-final")


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


# ------------------------------------------------------------------ EDL: o que havia em cada quadro
def no_quadro(trechos, q: int):
    return next((t for t in trechos if t["saida_quadros"][0] <= q < t["saida_quadros"][1]), None)


def descreve(t) -> str:
    if not t:
        return "?"
    partes = []
    for c in t["camadas"]:
        partes.append(c.get("fonte", APRESENTADOR) if c["camada"] == "base" else f"{c['camada']} {c.get('slot') or ''}".strip())
    return " + ".join(partes)


def _planejada(t) -> bool:
    return any(c["camada"] in PLANEJADO or "fundo" in c.get("fonte", "") for c in t["camadas"])


def planejado(trechos, q: int, margem: int = 0) -> bool:
    """Quadro dentro (ou a `margem` quadros) de uma peça que corta rápido de propósito."""
    return any(a - margem <= q < b + margem and _planejada(t) for t in trechos for a, b in [t["saida_quadros"]])


def dentro_planejado(trechos, a: int, b: int) -> bool:
    """[a, b) inteiro dentro de uma peça planejada, sem encostar no 1º quadro dela."""
    return any(ta < a and b <= tb + 1 and _planejada(t) for t in trechos for ta, tb in [t["saida_quadros"]])


# ------------------------------------------------------------------ 1 e 2: imagem
def dhash(f: np.ndarray) -> int:
    """Hash perceptual de 64 bits: compara a luminosidade de blocos vizinhos numa grade 8x9."""
    g = f.reshape(H, W).astype(np.float32)
    g = np.array([[blk.mean() for blk in np.array_split(row, 9, axis=1)] for row in np.array_split(g, 8, axis=0)])
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if x else "0" for x in bits), 2)


def varrer_video(video: Path):
    """Por quadro: diferença média de pixel com o anterior e o dHash. Cacheado ao lado do vídeo (.caca.npz)."""
    cache = video.with_name(video.stem + ".caca.npz")
    if cache.exists() and cache.stat().st_mtime > video.stat().st_mtime:
        z = np.load(cache)
        return z["dif"], z["dh"]
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(video), "-an",
           "-vf", f"fps={FPS},scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    log_arq = video.with_name(video.stem + ".caca-ffmpeg.log")
    n = W * H
    ant = None
    difs, dhs = [], []
    with open(log_arq, "wb") as log:    # stderr num arquivo: um aviso do decoder não derruba o ffmpeg calado
        pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        while True:
            buf = pr.stdout.read(n)
            if len(buf) < n:
                break
            f = np.frombuffer(buf, dtype=np.uint8).astype(np.int16)
            difs.append(0.0 if ant is None else float(np.mean(np.abs(f - ant))))
            dhs.append(dhash(f))
            ant = f
        pr.wait()
    if pr.returncode:    # leitura pela metade NUNCA vira cache: a caça diria "limpo" sobre um pedaço do vídeo
        raise SystemExit(f"leitura do vídeo parou em {len(difs)} quadros (ffmpeg {pr.returncode}); ver {log_arq}")
    dif, dh = np.array(difs, dtype=np.float32), np.array(dhs, dtype=np.uint64)
    np.savez(cache, dif=dif, dh=dh)
    return dif, dh


def ham(a, b) -> int:
    return bin(int(a) ^ int(b)).count("1")


def detectar_cortes(dif):
    """Corte = pico ISOLADO: a diferença salta acima do limiar E de 3x o movimento dos 8 quadros de cada lado
    (clipe de 30 fps com ação rápida dá picos seguidos, não isolados)."""
    cortes = []
    for i in range(1, len(dif)):
        if dif[i] <= CORTE_DIF:
            continue
        viz = max(np.median(dif[max(0, i - 8):i]), np.median(dif[i + 1:i + 9]) if i + 1 < len(dif) else 0)
        if dif[i] > 3 * viz:
            cortes.append(i)
    return cortes


def cortes_relampago(dif, dh, trechos):
    cortes = detectar_cortes(dif)
    achados = []
    lim, firme = round(RELAMPAGO * FPS), round(0.5 * FPS)
    bordas = [0] + cortes + [len(dif)]
    for k in range(1, len(bordas) - 2):
        a, b = bordas[k], bordas[k + 1]
        antes, depois = a - bordas[k - 1], bordas[k + 2] - b
        if b - a >= lim or antes < firme or depois < firme or dentro_planejado(trechos, a, b):
            continue
        volta = ham(dh[a - 1], dh[b]) <= HASH_DIST   # o plano de antes VOLTA depois do relâmpago = quadro intruso
        achados.append(dict(tipo="corte relâmpago", q=a, t=a / FPS,
                            det=f"{b - a} quadros ({(b - a) / FPS:.2f} s) entre dois planos firmes"
                                f"{' · o plano de antes VOLTA (quadro intruso)' if volta else ''} · ali: {descreve(no_quadro(trechos, a))}"))
    return achados, cortes


def pulo_no_apresentador(dif, trechos, zooms: dict):
    """O apresentador sozinho (sem mídia, motion, card) é UMA tomada contínua; um pico isolado de diferença no meio dela
    = pulo de tempo ou de enquadramento (1 quadro só: invisível para o detector de corte)."""
    bordas = {b + k for t in trechos for b in t["saida_quadros"] for k in range(-2, 3)}
    achados = []
    for t in trechos:
        cams = {c["camada"] for c in t["camadas"]}
        if t["camada_principal"] != APRESENTADOR or cams & (set(PECAS) | {"bolinha"}):
            continue
        a, b = t["saida_quadros"]
        for i in range(a + 1, min(b, len(dif) - 9)):
            if i in bordas or dif[i] <= 6:
                continue
            viz = max(np.median(dif[max(0, i - 8):i]), np.median(dif[i + 1:i + 9]), 0.3)
            if dif[i] > 8 * viz and not _zoom_seco_em(t, i, zooms):
                achados.append(dict(tipo="pulo no apresentador", q=i, t=i / FPS,
                                    det=f"diferença {dif[i]:.0f} num quadro (vizinhos {viz:.1f}) no meio de uma tomada contínua · ali: {descreve(t)}"))
    return achados


def _zoom_seco_em(t, q: int, zooms: dict) -> bool:
    """O trecho tem um zoom cuja curva troca de escala de uma vez (corte seco para o fechado) a até 3 quadros de q."""
    z = next((c for c in t["camadas"] if c["camada"] == "zoom"), None)
    if not z or z.get("slot") not in zooms or not t.get("bruto"):
        return False
    tb = t["bruto"][0] + (q - t["saida_quadros"][0]) / FPS
    ks = zooms[z["slot"]]["chaves"]
    return any(abs(k1["s0"] - k0["s1"]) > 0.02 and abs(k1["t0"] - tb) < 3 / FPS + 1e-6 for k0, k1 in zip(ks, ks[1:]))


def apresentador_retrocede(trechos):
    """Plano: o apresentador visível volta no tempo do bruto (fundo móvel de vinheta repetindo o que já passou) = pulo na imagem."""
    achados = []
    ant, ant_fundo = None, False
    for t in trechos:
        base = next((c for c in t["camadas"] if c["camada"] == "base"), None)
        if not base or not base.get("bruto") or not str(base.get("fonte", "")).startswith(APRESENTADOR):
            ant = None
            continue
        ba, bb = base["bruto"]
        fundo = "fundo" in str(base.get("fonte", ""))
        if ant is not None and ba < ant - 0.1 and not (fundo and ant_fundo):   # troca dentro da vinheta opaca não aparece
            q = t["saida_quadros"][0]
            achados.append(dict(tipo="apresentador volta no tempo", q=q, t=q / FPS,
                                det=f"o apresentador visível pula de {ant:.2f} s para {ba:.2f} s do bruto ({ant - ba:.1f} s atrás) · ali: {descreve(t)}"))
        ant, ant_fundo = bb, fundo
    return achados


def cenas_repetidas(dh, trechos):
    """Mesmo quadro de mídia duas vezes, a mais de 20 s (1 amostra a cada 6 quadros; o apresentador fica de fora)."""
    amostras = []
    for t in trechos:
        if t["camada_principal"] != "midia":
            continue
        a, b = t["saida_quadros"]
        for q in range(a + 3, b - 3, 6):
            h = int(dh[q])
            if 12 <= bin(h).count("1") <= 60:   # quadro liso (preto, cor chapada) não conta
                amostras.append((q, h, t))
    achados, ja = [], set()
    for i, (q, h, t) in enumerate(amostras):
        for q0, h0, t0 in amostras[:i]:
            if q - q0 < REPETE_MIN_S * FPS:
                break
            if ham(h, h0) <= HASH_DIST and (id(t0), id(t)) not in ja:
                ja.add((id(t0), id(t)))
                achados.append(dict(tipo="cena repetida", q=q, t=q / FPS,
                                    det=f"mesma imagem de {mmss(q0 / FPS)} · antes: {descreve(t0)} · agora: {descreve(t)}"))
                break
    return achados


def mesma_filmagem(trechos):
    """Plano: duas mídias a menos de 30 s com a mesma ORIGEM (mesmo autor no banco de imagens, mesmo vídeo do YouTube) parecem repetição.
    Lê o campo `origem` da camada de mídia do EDL, ex.: 'Pexels (autor Fulano)' ou 'https://youtu.be/XXXXXXXXXXX'."""
    vistos, achados, pares = [], [], set()
    for t in trechos:
        m = next((c for c in t["camadas"] if c["camada"] == "midia"), None)
        org = (m or {}).get("origem", "")
        if not org:
            continue
        autor = re.search(r"\(autor ([^)]+)\)", org)
        yt = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})", org)
        chave = autor.group(1).strip().lower() if autor else (f"youtube {yt.group(1)}" if yt else "")
        if not chave or chave in GENERICAS:
            continue
        sid, q = m.get("slot"), t["saida_quadros"][0]
        for q0, sid0, ch0 in vistos:
            if ch0 == chave and sid0 != sid and q - q0 < 30 * FPS and (sid0, sid) not in pares:
                pares.add((sid0, sid))
                achados.append(dict(tipo="mesma filmagem", q=q, t=q / FPS,
                                    det=f"{sid} e {sid0} ({mmss(q0 / FPS)}) vêm da mesma origem ({chave}) · pode ler como cena repetida"))
                break
        vistos.append((q, sid, chave))
    return achados


# ------------------------------------------------------------------ 3: volume
def _ebur128(audio: Path, extra: str = "") -> str:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(audio), "-vn", "-af", f"ebur128={extra}", "-f", "null", "-"]
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW,
                          encoding="utf-8", errors="replace").stderr


def loudness_momentanea(audio: Path):
    """(t, M) a cada 0,1 s; M = loudness de 400 ms (EBU R128)."""
    pts = []
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:\S+\s+LUFS\s+M:\s*(-?[\d.]+|-inf)", _ebur128(audio, "metadata=0")):
        v = m.group(2)
        pts.append((float(m.group(1)), -70.0 if v == "-inf" else float(v)))
    return np.array(pts)


def loudness_final(audio: Path, alvo: float):
    """Loudness integrado e pico verdadeiro do arquivo inteiro; sinaliza fora do alvo (±1,0 LU) ou pico acima de −1,0 dBTP."""
    err = _ebur128(audio, "peak=true")
    mi = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    mp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    if not mi:
        return [], None
    i, pico = float(mi[-1]), float(mp[-1]) if mp else None
    achados = []
    if abs(i - alvo) > 1.0:
        achados.append(dict(tipo="loudness final", q=0, t=0.0, det=f"integrado {i:.1f} LUFS, alvo {alvo:.1f} (±1,0)"))
    if pico is not None and pico > -1.0:
        achados.append(dict(tipo="pico alto", q=0, t=0.0, det=f"pico verdadeiro {pico:.1f} dBTP (acima de −1,0): risco de distorcer ao recomprimir"))
    return achados, (i, pico)


def volume_pulando(pts, ws, trechos):
    """Duas réguas, porque a voz esconde a música na loudness da mistura:
    fundo = loudness nos BURACOS da fala (o que sobra é trilha + SFX) contra os 60 s em volta;
    voz   = loudness no meio das palavras, média de 8 s contra os 60 s anteriores."""
    if len(pts) == 0 or not ws:
        return []
    t, M = pts[:, 0], pts[:, 1]

    def m_em(x):
        return M[min(int(np.searchsorted(t, x)), len(M) - 1)]
    achados = []
    fundo = []
    for (_, a1), (b0, _) in zip(ws, ws[1:]):
        if b0 - a1 >= 0.45:
            x = (a1 + b0) / 2 + 0.2   # a janela de 400 ms termina no fim do vão
            if not planejado(trechos, round(x * FPS), margem=FPS):
                fundo.append((x, m_em(x)))
    fundo = np.array(fundo)
    ult = -99
    for x, v in fundo:
        viz = fundo[(np.abs(fundo[:, 0] - x) < 30) & (np.abs(fundo[:, 0] - x) > 1.5), 1]
        if len(viz) >= 6 and v > -60 and v - np.median(viz) > 4.0 and x - ult > 8:
            ult = x
            q = round(x * FPS)
            achados.append(dict(tipo="trilha/fundo alto", q=q, t=float(x),
                                det=f"{v - np.median(viz):+.1f} LU acima do fundo dos 60 s em volta (no respiro da fala) · ali: {descreve(no_quadro(trechos, q))}"))
    voz = np.array([(c, m_em(c + 0.2)) for c in ((a + b) / 2 for a, b in ws if b - a >= 0.15)])
    if len(voz):
        voz = voz[voz[:, 1] > -45]
    ult = -99
    for x, _ in (voz[::5] if len(voz) else []):
        ag = voz[(voz[:, 0] >= x) & (voz[:, 0] < x + 8), 1]
        an = voz[(voz[:, 0] >= x - 60) & (voz[:, 0] < x), 1]
        if len(ag) >= 10 and len(an) >= 40:
            d = np.median(ag) - np.median(an)
            if abs(d) > 2.5 and x - ult > 20:
                ult = x
                q = round(x * FPS)
                achados.append(dict(tipo="voz mudou de nível", q=q, t=float(x),
                                    det=f"voz {d:+.1f} LU nos 8 s seguintes contra o minuto anterior · ali: {descreve(no_quadro(trechos, q))}"))
    return achados


def trilha_contra_voz(niveis_p: Path | None, trechos):
    """Lê `<wav>.niveis.json` (a mistura grava voz, trilha e SFX a cada 0,1 s).
    trilha subindo   = energia de 2 s da trilha 5 dB acima da mediana dela nos 30 s em volta, por 1,5 s ou mais;
    trilha encostando = trilha a menos de 8 dB da voz enquanto o apresentador fala, por 1 s ou mais.
    Medir a trilha CONTRA A VOZ é o que pega o "subiu forte" que na mistura final fica escondido pela voz."""
    if not niveis_p or not niveis_p.exists():
        return [dict(tipo="sem medida de trilha", q=0, t=0.0,
                     det=f"falta {niveis_p.name if niveis_p else 'o niveis.json'}: a trilha não foi medida (monte o áudio com `edicao audio`)")]
    n = json.loads(niveis_p.read_text(encoding="utf-8"))
    T, V = np.array(n["trilha"]), np.array(n["voz"])
    m = min(len(T), len(V))
    T, V = T[:m], V[:m]
    passo = round(n["passo_s"] * FPS)
    q_ini = n.get("q_ini", 0)
    Vs = np.array([np.median(V[max(0, i - 5):i + 5]) for i in range(m)])   # voz suavizada em 1 s
    achados = []

    def corre(cond, minimo, tipo, det):
        i = 0
        while i < m:
            if cond[i]:
                j = i
                while j < m and cond[j]:
                    j += 1
                q = q_ini + i * passo
                if j - i >= minimo and not planejado(trechos, q, margem=FPS):
                    achados.append(dict(tipo=tipo, q=q, t=q / FPS, det=det(i, j) + f" · ali: {descreve(no_quadro(trechos, q))}"))
                i = j
            else:
                i += 1
    Ts = 10 * np.log10(np.convolve(10 ** (T / 10), np.ones(20) / 20, mode="same") + 1e-12)   # energia em 2 s: a música tem batida
    viva = Ts > -70
    med = np.array([np.median(Ts[max(0, i - 150):i + 150][viva[max(0, i - 150):i + 150]]) if viva[max(0, i - 150):i + 150].any() else -90
                    for i in range(m)])
    corre(viva & (Ts - med > 5.0), 15, "trilha subindo",
          lambda i, j: f"trilha {np.max(Ts[i:j] - med[i:j]):+.1f} dB acima dela mesma nos 30 s em volta, por {(j - i) * 0.1:.1f} s")
    corre((Vs > -40) & (T > -70) & (T - Vs > -8.0), 10, "trilha encostando na voz",
          lambda i, j: f"trilha a {np.min(Vs[i:j] - T[i:j]):.1f} dB da voz com ele falando, por {(j - i) * 0.1:.1f} s")
    return achados


# ------------------------------------------------------------------ 4: respiro
def palavras_saida(transcricao: Path, trechos):
    """Palavras da transcrição (tempo do bruto) -> tempo da SAÍDA, só as que aparecem em trechos de apresentador."""
    t = json.loads(transcricao.read_text(encoding="utf-8"))
    ws = [(float(w["start"]), float(w["end"])) for s in t.get("segments", []) for w in s.get("words", [])]
    base = [x for x in trechos if x.get("bruto") and any(c["camada"] == "base" and str(c.get("fonte", "")).startswith(APRESENTADOR) for c in x["camadas"])]
    out = []
    for a, b in ws:
        for x in base:
            ba, bb = x["bruto"]
            if ba <= a < bb:
                o = x["saida"][0] + (a - ba)
                out.append((o, o + (min(b, bb) - a)))
                break
    return sorted(out)


def respiros(ws, trechos):
    achados = []
    for (_, a1), (b0, _) in zip(ws, ws[1:]):
        g = b0 - a1
        if g > RESPIRO:
            q = round((a1 + 0.05) * FPS)
            if any(planejado(trechos, round(x * FPS)) for x in np.arange(a1, b0, 0.1)):
                continue
            achados.append(dict(tipo="respiro sobrando", q=q, t=a1, det=f"{g:.2f} s sem fala · ali: {descreve(no_quadro(trechos, q))}"))
    return achados


# ------------------------------------------------------------------ 5, 6 e 7: emendas
def _inserida(t) -> bool:
    return not t.get("bruto") and any(c["camada"] in ("capitulo", "mini-intro") for c in t["camadas"])


def _blocos_inseridos(trechos, chave: str, tol):
    blocos = []
    for t in trechos:
        if _inserida(t):
            a, b = t[chave]
            if blocos and abs(blocos[-1][1] - a) <= tol:
                blocos[-1][1] = b
            else:
                blocos.append([a, b, next((c.get("slot") for c in t["camadas"] if c["camada"] in ("capitulo", "mini-intro")), "")])
    return blocos


def respiro_na_emenda(trechos, fala: Fala | None):
    """O respiro que o detector 4 pula por encostar numa vinheta: a inserção deve entrar logo depois da última palavra
    e a fala voltar logo depois que ela sai. Mede na forma de onda do bruto (precisa de --bruto)."""
    if fala is None:
        return []
    achados = []
    for a, b, slot in _blocos_inseridos(trechos, "saida", 0.02):
        ant = next((t for t in reversed(trechos) if t.get("bruto") and abs(t["saida"][1] - a) < 0.02), None)
        dep = next((t for t in trechos if t.get("bruto") and abs(t["saida"][0] - b) < 0.02), None)
        if ant:
            pb = ant["bruto"][1]
            s0, s1 = fala.silencio_em(round(pb - 0.03, 3), limiar_db=-42.0, raio=2.0)
            g = pb - s0 if s1 > s0 else 0.0
            if RESPIRO_ANTES < g < 3.0:
                achados.append(dict(tipo="respiro antes da vinheta", q=round((a - g) * FPS), t=a - g,
                                    det=f"{g:.2f} s da última palavra até {slot} entrar"))
        if dep:
            pb = dep["bruto"][0]
            s0, s1 = fala.silencio_em(round(pb + 0.03, 3), limiar_db=-42.0, raio=2.0)
            g = s1 - pb if s1 > s0 else 0.0
            if RESPIRO_DEPOIS < g < 3.0:
                achados.append(dict(tipo="respiro depois da vinheta", q=round(b * FPS), t=b,
                                    det=f"{g:.2f} s de {slot} sair até a próxima palavra · ali: {descreve(no_quadro(trechos, round(b * FPS) + 1))}"))
    return achados


def lasca_na_vinheta(dif, trechos):
    """Plano de menos de RELAMPAGO logo na saída (ou na entrada) de capítulo/mini inserida: a vinheta sai, o apresentador fica uns
    quadros parado e corta para a pose nova = "frame passado". O detector 1 não vê porque a borda da vinheta é planejada."""
    achados = []
    lim = round(RELAMPAGO * FPS)
    for a, b, slot in _blocos_inseridos(trechos, "saida_quadros", 1):
        # no quadro da saída as folhas ainda passam na frente e atenuam a troca: limiar pela metade ali
        corte = next((i for i in range(b - 1, min(b + lim, len(dif))) if dif[i] > (CORTE_DIF / 2 if i <= b + 1 else CORTE_DIF)), None)
        if corte is not None:
            achados.append(dict(tipo="lasca na vinheta", q=b, t=b / FPS,
                                det=(f"troca de plano no quadro em que {slot} sai (o fundo da saída era outro trecho do apresentador)" if corte <= b + 1
                                     else f"{(corte - b) / FPS:.2f} s de plano entre a saída de {slot} e o corte seguinte") + f" · ali: {descreve(no_quadro(trechos, b + 1))}"))
        antes = next((i for i in range(a - 2, max(a - lim, 0), -1) if dif[i] > CORTE_DIF), None)
        if antes is not None:
            achados.append(dict(tipo="lasca na vinheta", q=antes, t=antes / FPS,
                                det=f"{(a - antes) / FPS:.2f} s de plano entre o corte anterior e a entrada de {slot} · ali: {descreve(no_quadro(trechos, a - 1))}"))
    return achados


def apresentador_solto(trechos):
    """Apresentador sozinho (sem mídia nem peça por cima) por menos de SOLTO, com peça dos dois lados."""
    def so_ele(t):
        return t.get("bruto") and all(c["camada"] in ("base", "zoom") for c in t["camadas"]) and not any(c.get("coberto_por_midia") for c in t["camadas"])
    achados, i = [], 0
    while i < len(trechos):
        if not so_ele(trechos[i]):
            i += 1
            continue
        j = i
        while j + 1 < len(trechos) and so_ele(trechos[j + 1]):
            j += 1
        a, b = trechos[i]["saida"][0], trechos[j]["saida"][1]
        if 0 < b - a < SOLTO and i > 0 and j + 1 < len(trechos):
            achados.append(dict(tipo="apresentador solto", q=round(a * FPS), t=a,
                                det=f"{b - a:.2f} s sozinho entre {descreve(trechos[i - 1])} e {descreve(trechos[j + 1])}"))
        i = j + 1
    return achados


# ------------------------------------------------------------------ orquestração
def cacar(video, edl=None, transcricao=None, bruto=None, audio=None, niveis=None, zooms=None, lufs=None, out=None) -> Path:
    video = Path(video)
    trechos = json.loads(Path(edl).read_text(encoding="utf-8"))["trechos"] if edl and Path(edl).exists() else []
    zs = {}
    if zooms and Path(zooms).exists():
        zs = {z["id"]: z for z in json.loads(Path(zooms).read_text(encoding="utf-8")).get("slots", [])}
    print("imagem...", flush=True)
    dif, dh = varrer_video(video)
    rel, cortes = cortes_relampago(dif, dh, trechos)
    r = list(rel)
    if trechos:
        r += pulo_no_apresentador(dif, trechos, zs) + apresentador_retrocede(trechos) + cenas_repetidas(dh, trechos)
        r += mesma_filmagem(trechos) + apresentador_solto(trechos) + lasca_na_vinheta(dif, trechos)
    print("som...", flush=True)
    fonte_audio = Path(audio) if audio else video
    ws = palavras_saida(Path(transcricao), trechos) if transcricao and Path(transcricao).exists() and trechos else []
    r += volume_pulando(loudness_momentanea(fonte_audio), ws, trechos)
    r += respiros(ws, trechos) + respiro_na_emenda(trechos, Fala(bruto) if bruto else None)
    niv = Path(niveis) if niveis else (Path(str(audio) + ".niveis.json") if audio else None)
    if niv is None:
        cand = sorted(video.parent.glob("*.wav.niveis.json"), key=lambda p: p.stat().st_mtime)
        niv = cand[-1] if cand else None
    if trechos or (niv and niv.exists()):
        r += trilha_contra_voz(niv, trechos)
    alvo = float(lufs if lufs is not None else CFG["lufs_alvo"])
    ach_l, med = loudness_final(video, alvo)   # o ARQUIVO FINAL, não a mistura antes do master
    r += ach_l
    tudo = sorted(r, key=lambda x: x["q"])
    saida = Path(out) if out else video.with_name(video.stem + ".CACA.md")
    cont: dict = {}
    for x in tudo:
        cont[x["tipo"]] = cont.get(x["tipo"], 0) + 1
    linhas = [f"# Caça técnica · {video.name}", "",
              f"{len(dif)} quadros lidos · {len(cortes)} cortes de plano medidos · " + (" · ".join(f"{k}: {v}" for k, v in cont.items()) or "nenhum achado"),
              f"Loudness: {med[0]:.1f} LUFS integrado · pico verdadeiro {med[1]:.1f} dBTP" if med and med[1] is not None else "", "",
              "Mede o vídeo PRONTO (pixels e som), não o plano. Cada linha: tempo · quadro · o que mediu · o que o EDL diz que estava ali.",
              "Sem EDL, só entram os detectores que medem o arquivo.", ""]
    linhas += [f"- **{mmss(x['t'])}** (q {x['q']}) · {x['tipo']} · {x['det']}" for x in tudo]
    saida.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"{len(tudo)} achados -> {saida}")
    for k, v in cont.items():
        print(f"  {k}: {v}")
    return saida


def main(argv=None):
    ap = argparse.ArgumentParser(prog="edicao caca", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--edl")
    ap.add_argument("--transcricao")
    ap.add_argument("--bruto", help="vídeo/áudio bruto (forma de onda para medir respiro na emenda)")
    ap.add_argument("--audio", help="WAV da mistura (se omitido, mede o áudio do próprio vídeo)")
    ap.add_argument("--niveis", help="<wav>.niveis.json da mistura")
    ap.add_argument("--zooms", help="zooms.json (para não acusar corte seco de zoom como pulo)")
    ap.add_argument("--lufs", type=float)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cacar(a.video, a.edl, a.transcricao, a.bruto, a.audio, a.niveis, a.zooms, a.lufs, a.out)


if __name__ == "__main__":
    main()
