"""Áudio do vídeo: voz do bruto + locuções + trilha (curva em dB) + efeitos em camadas, em blocos de 30 s (pouca RAM).

Tudo em numpy float32 estéreo 48 kHz, na grade do vídeo (1 quadro = SR/FPS amostras): a voz e a imagem cortam no mesmo
ponto e a sincronia nunca deriva. Faltou um insumo (trilha, SFX, locução)? A mistura segue sem ele e AVISA — nunca derruba.

Etapas de um master de áudio:
  1. `montar_audio`  mistura tudo num WAV e grava `<wav>.niveis.json` (nível de voz/trilha/sfx a cada 0,1 s,
                     que a caça técnica usa para medir a trilha contra a voz);
  2. `ganho_para_lufs`  mede o loudness integrado (EBU R128) e calcula o ganho até o alvo (padrão −14 LUFS);
  3. `masterizar`    aplica o ganho + limitador de pico e junta com a imagem sem recodificar o vídeo.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .ajustes import envelope, ler as ler_ajustes
from .comum import FLAGS, NO_WINDOW, salvar_json, sonda
from .config import CACHE, FPS, SPF, SR
from .projeto import Projeto

CHUNK_Q = 30 * FPS             # 30 s por bloco
FADE_EMENDA = int(0.004 * SR)  # 4 ms nas emendas da voz: sem estalo
VO_PAUSA_MAX = 0.12            # pausa interna máxima de uma locução depois de enxugar (s)
VO_BORDA = 0.03                # silêncio que fica antes da 1ª e depois da última palavra da locução (s)
_PCM_SFX: dict = {}


def pcm(path, ss: float, dur: float, n: int | None = None, mono_cheio: bool = False) -> np.ndarray:
    """Decodifica [ss, ss+dur) do arquivo como float32 estéreo 48 kHz. Completa com silêncio se o arquivo acabar.
    `mono_cheio`: arquivo mono vira estéreo copiando o canal (o `-ac 2` comum cai 3 dB por canal)."""
    # `-ss` na entrada devolve alguns ms zerados no começo (atraso do decodificador): lê 100 ms antes e descarta esse pré-rolo
    pre = min(ss, 0.1)
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-threads", "1", "-ss", f"{ss - pre:.6f}",
           "-t", f"{dur + pre:.6f}", "-i", str(path), "-vn"] + \
          (["-af", "pan=stereo|c0=c0|c1=c0"] if mono_cheio else ["-ac", "2"]) + ["-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, creationflags=FLAGS).stdout
    a = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy() if len(raw) >= 8 else np.zeros((0, 2), np.float32)
    a = a[int(round(pre * SR)):]
    n = n if n is not None else int(round(dur * SR))
    if len(a) < n:
        a = np.vstack([a, np.zeros((n - len(a), 2), np.float32)])
    return a[:n]


def db_lin(db):
    return np.power(10.0, np.asarray(db, dtype=np.float64) / 20.0)


# ------------------------------------------------------------------ trilha
def rms_arquivo(path) -> float:
    """RMS (dBFS) do arquivo inteiro, em blocos de 20 s; cacheado por tamanho+mtime.
    A trilha é NORMALIZADA por esse valor antes de aplicar a curva: assim a curva em dB significa a mesma coisa
    para qualquer música, alta ou baixa, e você compara faixas diferentes sem refazer a conta."""
    arq = CACHE / "rms_trilha.json"
    try:
        cache = json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    p = Path(path)
    st = p.stat()
    chave = f"{p}|{st.st_size}|{int(st.st_mtime)}"
    if chave in cache:
        return cache[chave]
    dur = (sonda(p) or {}).get("dur") or 0
    soma, cnt, t = 0.0, 0, 0.0
    while t < dur:
        seg = min(20.0, dur - t)
        x = pcm(p, t, seg)
        soma += float(np.sum(x.astype(np.float64) ** 2))
        cnt += x.size
        t += seg
    r = 10 * np.log10(max(soma / max(cnt, 1), 1e-12))
    cache[chave] = round(float(r), 2)
    salvar_json(arq, cache)
    return cache[chave]


def _x_saida(proj: Projeto, t: float, lado: str) -> float:
    """Tempo da marca (s) -> amostra da saída, na régua escolhida em `tempo_das_marcas`."""
    if proj.tempo_das_marcas == "saida":
        return t * SR
    return proj.mapa.saida(t * FPS, lado) * SPF


def blocos_trilha(proj: Projeto, avisos: list) -> list:
    """Cada bloco: faixa + curva de volume (amostras da SAÍDA, dB)."""
    out = []
    for b in proj.trilha.get("blocos", []):
        arq = proj.resolver(b["arquivo"]) if b.get("arquivo") else None
        if not arq or not arq.exists():
            avisos.append(f"trilha bloco {b.get('bloco')}: faixa não encontrada ({b.get('arquivo')}); sem música nele")
            continue
        curva = b.get("curva_db") or []
        if len(curva) < 2:
            avisos.append(f"trilha bloco {b.get('bloco')}: curva com menos de 2 pontos; ignorado")
            continue
        pts = [(_x_saida(proj, t, "ini" if i < len(curva) // 2 else "fim"), db) for i, (t, db) in enumerate(curva)]
        xs = np.maximum.accumulate(np.array([p[0] for p in pts], dtype=np.float64))   # curva nunca anda para trás
        ys = np.array([p[1] for p in pts], dtype=np.float64)
        out.append(dict(bloco=b.get("bloco"), arquivo=arq, x=xs, db=ys, inicio=float(xs[0]), fim=float(xs[-1]),
                        rms=rms_arquivo(arq), longo=(sonda(arq) or {}).get("dur") or 0))
    return out


def trilha_chunk(bl: dict, a: int, n: int) -> np.ndarray | None:
    """Amostras [a, a+n) da trilha do bloco `bl` (zeros fora do trecho). A faixa repete (loop) se for mais curta que o bloco."""
    ini, fim = bl["inicio"], bl["fim"]
    lo, hi = max(a, int(ini)), min(a + n, int(fim))
    if hi <= lo:
        return None
    longo = bl["longo"]
    pos = np.arange(lo, hi, dtype=np.float64)
    ganho = db_lin(np.interp(pos, bl["x"], bl["db"]) - bl["rms"])
    off = (lo - ini) / SR
    fonte = np.zeros((hi - lo, 2), np.float32)
    feito = 0
    while feito < hi - lo:
        p = (off + feito / SR) % longo if longo > 1 else off + feito / SR
        q = min(hi - lo - feito, int((longo - p) * SR) if longo > 1 else hi - lo - feito)
        q = max(q, 1)
        fonte[feito:feito + q] = pcm(bl["arquivo"], p, q / SR, q)
        feito += q
    saida = np.zeros((n, 2), np.float32)
    saida[lo - a:hi - a] = fonte * ganho[:, None].astype(np.float32)
    return saida


# ------------------------------------------------------------------ efeitos (SFX em camadas)
def _sfx_amostras(path: Path):
    k = str(path)
    if k not in _PCM_SFX:
        d = (sonda(path) or {}).get("dur") if path.exists() else 0
        _PCM_SFX[k] = pcm(path, 0, d) if d else None
    return _PCM_SFX[k]


def eventos_sfx(proj: Projeto, avisos: list) -> list:
    """[(amostra_de_inicio_do_som, Path, ganho_db)] — um item por CAMADA de cada evento.
    A camada com `ancora_ms` coloca o ponto forte do som (o 'estalo') exatamente em t_s; `atraso_ms` empurra a camada."""
    ev = []
    for e in proj.sfx.get("eventos", []):
        x = _x_saida(proj, float(e["t_s"]), "ini")
        camadas = e.get("camadas") or []
        if len(camadas) < 2:
            avisos.append(f"sfx '{e.get('nome', e['t_s'])}': só {len(camadas)} camada — som seco sozinho fica 'cara de efeito pronto'; junte 2–3")
        for c in camadas:
            arq = proj.resolver(c["arquivo"])
            if not arq.exists():
                avisos.append(f"sfx '{e.get('nome')}': arquivo {c['arquivo']} não existe")
                continue
            ini = int(x + float(c.get("atraso_ms", 0)) * SR / 1000 - float(c.get("ancora_ms", 0)) * SR / 1000)
            ev.append((ini, arq, float(c.get("ganho_db", 0))))
    return ev


# ------------------------------------------------------------------ locução (voiceover) de inserções
def nivel_fala(x: np.ndarray) -> float:
    """dB RMS da fala: média das janelas de 50 ms acima da mediana (ignora os silêncios)."""
    m = x.mean(axis=1) if x.ndim == 2 else x
    h = int(0.05 * SR)
    k = len(m) // h
    if not k:
        return -90.0
    r = 20 * np.log10(np.sqrt(np.mean(m[:k * h].reshape(k, h) ** 2, axis=1)) + 1e-9)
    return float(np.mean(r[r > np.median(r)]))


def vo_enxuto(d: np.ndarray, limiar_db: float = -40.0) -> np.ndarray:
    """Locução SEM respiro: corta o silêncio antes e depois da fala e encolhe cada pausa interna para VO_PAUSA_MAX,
    com 5 ms de rampa na emenda. O defeito que isso resolve parece 'locução lenta', mas é o respiro sobrando —
    a velocidade da gravação fica intacta."""
    if len(d) < SR // 10:
        return d
    h = SR // 100
    k = len(d) // h
    e = 20 * np.log10(np.sqrt(np.mean(d[:k * h].mean(axis=1).reshape(k, h).astype(np.float64) ** 2, axis=1)) + 1e-9)
    fala = np.where(e > limiar_db)[0]
    if not len(fala):
        return d
    blocos, ini, ant = [], fala[0], fala[0]
    for i in fala[1:]:
        if (i - ant - 1) * h > VO_PAUSA_MAX * SR:
            blocos.append((ini, ant + 1))
            ini = i
        ant = i
    blocos.append((ini, ant + 1))
    rampa = int(0.005 * SR)
    pedacos = []
    for j, (i0, i1) in enumerate(blocos):
        a = max(0, i0 * h - int((VO_BORDA if j == 0 else VO_PAUSA_MAX / 2) * SR))
        b = min(len(d), i1 * h + int((VO_BORDA if j == len(blocos) - 1 else VO_PAUSA_MAX / 2) * SR))
        x = d[a:b].copy()
        r = min(rampa, len(x) // 2)
        if r:
            x[:r] *= np.linspace(0, 1, r, dtype=np.float32)[:, None]
            x[-r:] *= np.linspace(1, 0, r, dtype=np.float32)[:, None]
        pedacos.append(x)
    return np.vstack(pedacos)


def locucoes(proj: Projeto, voz: Path, avisos: list) -> list:
    """(amostra de início na saída, pcm) de cada locução de inserção, já enxuta e no nível da voz do apresentador."""
    alvo = [s for s in proj.mapa.segmentos() if s["tipo"] == "ins" and s.get("vo")]
    if not alvo:
        return []
    dur = (sonda(voz) or {}).get("dur") or 0
    ref = nivel_fala(pcm(voz, max(0.0, min(300.0, dur / 2 - 30)), 60.0, mono_cheio=voz != proj.bruto))
    out = []
    for s in alvo:
        arq = proj.resolver(s["vo"])
        if not arq.exists():
            avisos.append(f"{s['slot']}: locução {s['vo']} não existe")
            continue
        d = vo_enxuto(pcm(arq, 0, (sonda(arq) or {}).get("dur") or 0))
        d = d * float(db_lin(ref - nivel_fala(d)))
        ini = int((s["a"] + float(s.get("vo_em_s", 0.3)) * FPS) * SPF)
        if ini + len(d) > s["b"] * SPF:
            avisos.append(f"{s['slot']}: locução passa {(ini + len(d) - s['b'] * SPF) / SR:.2f} s do fim da inserção (inserção curta)")
        out.append((ini, d))
    return out


# ------------------------------------------------------------------ mistura
def montar_audio(proj: Projeto, wav, qa: int = 0, qb: int | None = None, ajustes=None) -> str:
    """Mistura o trecho [qa, qb) quadros da saída num WAV 16-bit estéreo e devolve um resumo (com os avisos)."""
    avisos: list = []
    segs = proj.mapa.segmentos()
    qb = proj.mapa.n_saida if qb is None else qb
    trilhas = blocos_trilha(proj, avisos)
    if not trilhas:
        avisos.append("sem trilha: voz sozinha")
    eventos = eventos_sfx(proj, avisos)
    voz = proj.arquivo_voz()
    avisos.append(f"voz = {voz.name}")
    vos = locucoes(proj, voz, avisos)
    aj = ler_ajustes(ajustes or proj.raiz / "ajustes.json")
    if aj["audio"]:
        avisos.append(f"{len(aj['audio'])} ajuste(s) de volume travados à mão")
    wav = Path(wav)
    wav.parent.mkdir(parents=True, exist_ok=True)
    lim = float(db_lin(proj.pico_db))
    pico_max = 0.0
    niveis = {"passo_s": 0.1, "q_ini": qa, "voz": [], "trilha": [], "sfx": []}
    janela = int(0.1 * SR)

    def _nivel(x):
        k = len(x) // janela
        if not k:
            return []
        r = np.sqrt(np.mean(x[:k * janela].reshape(k, janela, 2).astype(np.float64) ** 2, axis=(1, 2)) + 1e-12)
        return [round(float(v), 1) for v in 20 * np.log10(r)]

    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        for q0 in range(qa, qb, CHUNK_Q):
            q1 = min(qb, q0 + CHUNK_Q)
            a, n = q0 * SPF, (q1 - q0) * SPF
            mix = np.zeros((n, 2), np.float32)
            so_trilha = np.zeros((n, 2), np.float32)
            for sg in segs:                                   # voz: os pedaços de bruto que caem neste bloco
                if sg["tipo"] != "base" or sg["b"] <= q0 or sg["a"] >= q1:
                    continue
                x0, x1 = max(sg["a"], q0), min(sg["b"], q1)
                ini_br = sg["bruto_a"] + (x0 - sg["a"])
                v = pcm(voz, ini_br / FPS, (x1 - x0) / FPS, (x1 - x0) * SPF, mono_cheio=voz != proj.bruto)
                if x0 == sg["a"] and FADE_EMENDA:
                    v[:FADE_EMENDA] *= np.linspace(0, 1, FADE_EMENDA, dtype=np.float32)[:, None]
                if x1 == sg["b"] and FADE_EMENDA:
                    v[-FADE_EMENDA:] *= np.linspace(1, 0, FADE_EMENDA, dtype=np.float32)[:, None]
                mix[(x0 - q0) * SPF:(x1 - q0) * SPF] += v
            for s0, d in vos:                                 # locuções entram como voz
                lo, hi = max(a, s0), min(a + n, s0 + len(d))
                if hi > lo:
                    mix[lo - a:hi - a] += d[lo - s0:hi - s0]
            for bl in trilhas:
                t = trilha_chunk(bl, a, n)
                if t is not None:
                    so_trilha += t
            ev_voz, ev_tr = envelope(aj, "voz", a, n, SR, SPF), envelope(aj, "trilha", a, n, SR, SPF)
            if ev_voz is not None:
                mix *= ev_voz[:, None]
            if ev_tr is not None:
                so_trilha *= ev_tr[:, None]
            niveis["voz"] += _nivel(mix)
            niveis["trilha"] += _nivel(so_trilha)
            mix += so_trilha
            antes_sfx = mix.copy()
            for (s0, arq, g) in eventos:
                d = _sfx_amostras(arq)
                if d is None:
                    continue
                lo, hi = max(a, s0), min(a + n, s0 + len(d))
                if hi > lo:
                    mix[lo - a:hi - a] += d[lo - s0:hi - s0] * float(db_lin(g))
            ev_fx = envelope(aj, "sfx", a, n, SR, SPF)
            if ev_fx is not None:
                mix = antes_sfx + (mix - antes_sfx) * ev_fx[:, None]
            niveis["sfx"] += _nivel(mix - antes_sfx)
            # limite de pico: dobra suave acima do teto (nada de estalo por corte seco)
            ab = np.abs(mix)
            pico_max = max(pico_max, float(ab.max()) if ab.size else 0.0)
            acima = ab > lim
            if acima.any():
                mix = np.where(acima, np.sign(mix) * (lim + (1 - lim) * np.tanh((ab - lim) / (1 - lim))), mix).astype(np.float32)
            w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    Path(str(wav) + ".niveis.json").write_text(json.dumps(niveis), encoding="utf-8")
    resumo = (f"{len(trilhas)} bloco(s) de trilha · {len(eventos)} camada(s) de SFX · {len(vos)} locução(ões) · "
              f"pico {20 * np.log10(max(pico_max, 1e-9)):.1f} dBFS antes do limitador")
    return resumo + " · AVISOS: " + " | ".join(avisos) if avisos else resumo


# ------------------------------------------------------------------ loudness e master
def ganho_para_lufs(wav, alvo: float = -14.0) -> float:
    """Mede o loudness integrado (ebur128) e devolve o ganho em dB até o alvo. Medida falhou = 0 dB."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return round(alvo - float(m[-1]), 2) if m else 0.0


def filtro_master(ganho_db: float, pico_db: float = -2.6) -> str:
    return f"volume={ganho_db:.2f}dB,alimiter=limit={10 ** (pico_db / 20):.4f}:attack=5:release=60:level=disabled"


def masterizar(video_in, wav, saida, lufs: float = -14.0, pico_db: float = -2.6) -> float:
    """Junta a imagem de `video_in` (copiada, sem recodificar) com o `wav` ajustado ao alvo de loudness + limitador.
    Devolve o ganho aplicado em dB."""
    ganho = ganho_para_lufs(wav, lufs)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video_in), "-i", str(wav), "-map", "0:v", "-map", "1:a",
           "-af", filtro_master(ganho, pico_db), "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(saida)]
    subprocess.run(cmd, check=True)
    return ganho
