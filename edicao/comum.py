"""Peças comuns: sonda de arquivos (ffprobe com cache), hash de cache, ffmpeg em modo leve e trava de render.

Três hábitos que vieram da prática e valem para qualquer projeto de vídeo longo:
 - ffmpeg SEMPRE com poucas threads e prioridade baixa: a máquina continua usável durante o render;
 - se a RAM acabar, o ffmpeg que NÓS abrimos é suspenso e depois retomado (nunca derruba o render nem o resto do PC);
 - cache por CONTEÚDO (hash do pedido + carimbo dos arquivos), nunca por posição na linha do tempo.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
import time
from fractions import Fraction
from pathlib import Path

import psutil

from .config import CACHE, CFG, FPS

BELOW_NORMAL = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)   # só existe no Windows
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)                  # idem
FLAGS = BELOW_NORMAL | NO_WINDOW


def digest(obj) -> str:
    """Impressão digital estável de qualquer estrutura JSON-izável (usada como nome de cache)."""
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]


def stamp(path) -> list:
    """Carimbo de um arquivo: caminho, tamanho, mtime. Se o arquivo mudar, o cache que o usa deixa de valer."""
    p = Path(path)
    try:
        st = p.stat()
        return [str(p), st.st_size, int(st.st_mtime)]
    except OSError:
        return [str(p), None, None]


def salvar_json(path, data):
    """Grava de forma atômica (arquivo temporário + rename): interrupção no meio nunca deixa JSON pela metade."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def ler_json(path, padrao=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return padrao


def tempo_txt(s: float) -> str:
    m, r = divmod(max(0.0, s), 60)
    return f"{int(m):02d}:{r:04.1f}"


def quadros(s: float, fps: int = FPS) -> int:
    """Segundos -> número do quadro na grade do projeto."""
    return int(round(s * fps))


# ---------------------------------------------------------------- sonda (ffprobe, com cache em disco)
_SONDAS: dict = {}
_ARQ_SONDA = CACHE / "sondas.json"
_ALFA = re.compile(r"^(yuva|gbra|ya)|^(argb|rgba|abgr|bgra)")


def sonda(path) -> dict | None:
    """Metadados normalizados de um arquivo de mídia, ou None se o ffprobe falhar. Só lê o cabeçalho (barato)."""
    if not _SONDAS and _ARQ_SONDA.exists():
        with contextlib.suppress(Exception):
            _SONDAS.update(json.loads(_ARQ_SONDA.read_text(encoding="utf-8")))
    p = Path(path)
    if not p.exists():
        return None
    st = p.stat()
    chave = f"{p}|{st.st_size}|{int(st.st_mtime)}"
    if chave in _SONDAS:
        return _SONDAS[chave]
    try:
        raw = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
                             capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=60)
        j = json.loads(raw.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    r = dict(video=None, audio=None, dur=float(j.get("format", {}).get("duration") or 0))
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rot = 0
        with contextlib.suppress(Exception):
            rot = int(float(v.get("tags", {}).get("rotate", 0)))
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if abs(rot) % 180 == 90:      # vídeo de celular gravado em pé: largura e altura trocam
            w, h = h, w
        try:
            fps = float(Fraction(v.get("r_frame_rate", "0/1")))
        except Exception:
            fps = 0.0
        nb = v.get("nb_frames")
        r["video"] = dict(codec=v.get("codec_name"), w=w, h=h, fps=fps, pix_fmt=v.get("pix_fmt", ""),
                          alfa=bool(_ALFA.match(v.get("pix_fmt", "") or "")),
                          nb_frames=int(nb) if nb and str(nb).isdigit() else None,
                          dur=float(v.get("duration") or r["dur"] or 0))
    if a:
        r["audio"] = dict(codec=a.get("codec_name"), sr=int(a.get("sample_rate") or 0), ch=int(a.get("channels") or 0),
                          dur=float(a.get("duration") or 0))
    _SONDAS[chave] = r
    return r


def gravar_cache_sondas():
    if _SONDAS:
        salvar_json(_ARQ_SONDA, _SONDAS)


# ---------------------------------------------------------------- RAM e trava
def ram_livre_gb() -> float:
    """RAM disponível (GB). No Windows, o limite real é o 'total reservável' (RAM + arquivo de paginação):
    se aparecer MemoryError com RAM livre sobrando, aumente o arquivo de paginação (veja docs/RENDER-RAPIDO.md)."""
    return round(psutil.virtual_memory().available / 2**30, 2)


def pegar_trava(caminho, frente: str = "render") -> tuple[bool, dict | None]:
    """Cria o arquivo-trava de forma atômica. Se já existe (de qualquer processo), não toca e devolve (False, dono).
    Serve para só um render pesado rodar por vez."""
    caminho = Path(caminho)
    dados = dict(frente=frente, pid=os.getpid(), hora=time.strftime("%Y-%m-%dT%H:%M:%S"), epoch=time.time())
    try:
        fd = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False, ler_json(caminho, dict(frente="?", pid=None))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(dados))
    return True, dados


def soltar_trava(caminho):
    """Só apaga a trava se for a MINHA (mesmo pid)."""
    d = ler_json(caminho)
    if d and d.get("pid") == os.getpid():
        with contextlib.suppress(OSError):
            Path(caminho).unlink()


# ---------------------------------------------------------------- ffmpeg em modo leve
def ffargs() -> list:
    th = str(os.environ.get("EDICAO_THREADS") or CFG["threads"])
    ft = "2" if int(th) > 2 else "1"
    return ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "warning",
            "-threads", th, "-filter_threads", ft, "-filter_complex_threads", ft]


def rodar(cmd, log, pausa_gb: float | None = None, retoma_gb: float | None = None) -> str:
    """Executa em prioridade baixa; suspende o filho se a RAM acabar e retoma quando voltar.
    Levanta RuntimeError com o fim do log se o ffmpeg falhar."""
    pausa_gb = CFG["ram_pausa_gb"] if pausa_gb is None else pausa_gb
    retoma_gb = CFG["ram_retoma_gb"] if retoma_gb is None else retoma_gb
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "wb") as err:
        filho = subprocess.Popen([str(x) for x in cmd], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                                 creationflags=FLAGS)
        proc = psutil.Process(filho.pid)
        parado = False
        try:
            while filho.poll() is None:
                livre = psutil.virtual_memory().available / 2**30
                if livre < pausa_gb and not parado:
                    proc.suspend()
                    parado = True
                elif parado and livre > retoma_gb:
                    proc.resume()
                    parado = False
                time.sleep(0.4 if parado else 0.2)
        finally:
            if parado and filho.poll() is None:
                proc.resume()
    texto = log.read_text(encoding="utf-8", errors="replace")
    if filho.returncode:
        raise RuntimeError(f"ffmpeg saiu com {filho.returncode}; log {log}\n" + texto[-2500:])
    return texto


def baixa_prioridade():
    with contextlib.suppress(Exception):
        if os.name == "nt":
            psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            psutil.Process().nice(10)
