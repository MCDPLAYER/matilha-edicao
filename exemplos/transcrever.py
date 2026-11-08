"""Transcreve um áudio/vídeo com tempo por PALAVRA, no formato que o kit lê (`transcricao.json`).

  pip install faster-whisper
  python exemplos/transcrever.py midia/bruto-decupado.mp4 midia/transcricao.json

Notas de método:
 - rode LOCAL: serviços de nuvem costumam "engolir" trechos de fala (confira se a transcrição cobre 100% da duração);
 - `condition_on_previous_text=False` evita que um retake (a frase repetida) contamine a transcrição seguinte;
 - o tempo por palavra erra uns 100–200 ms: o kit usa a ENERGIA do áudio (edicao/fala.py) para achar o ponto exato de corte.
"""
import json
import sys

from faster_whisper import WhisperModel

entrada, saida = sys.argv[1], sys.argv[2]
modelo = WhisperModel("large-v3", device="auto", compute_type="auto")
segmentos, info = modelo.transcribe(entrada, language="pt", word_timestamps=True, condition_on_previous_text=False)
out = {"duracao": info.duration, "segments": []}
for s in segmentos:
    out["segments"].append({
        "start": s.start, "end": s.end, "text": s.text,
        "words": [{"start": w.start, "end": w.end, "word": w.word} for w in (s.words or [])],
    })
with open(saida, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"{len(out['segments'])} segmentos -> {saida} (duração do arquivo: {info.duration:.1f} s)")
