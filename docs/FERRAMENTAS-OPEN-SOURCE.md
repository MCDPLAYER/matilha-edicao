# Ferramentas open source — onde cada uma entra no método

O método do kit não substitui editor de vídeo: ele organiza o fluxo e mede o resultado. As ferramentas abaixo fazem o trabalho pesado
de cada etapa. Para cada uma: o que faz, onde entra no fluxo, como se liga ao kit e um exemplo.

> **Licenças:** conferi de memória o tipo de licença de cada projeto — **leia o `LICENSE` do repositório oficial antes de usar em
> trabalho comercial** (o ffmpeg, por exemplo, muda entre LGPL e GPL conforme as opções do build; o Remotion tem licença própria).
> Comandos de linha podem variar entre versões: confira com `--help`.

| Etapa do fluxo | Ferramenta | Em uma frase |
|---|---|---|
| Tudo | **ffmpeg / ffprobe** | a base: corta, junta, filtra, mede |
| Recebimento | **faster-whisper** | transcrição local com tempo por palavra |
| Decupagem | **auto-editor** | corta silêncio e quadro parado automaticamente |
| Plano / cenas | **PySceneDetect** | acha cortes de plano em qualquer vídeo |
| Cartelas e motion | **Remotion** · **HTML + navegador headless** · **MoviePy** | animação por código |
| Som | **demucs** · **Audacity** · **pyloudnorm** | separar voz/música, ouvir, medir |
| Entrega a outros editores | **OpenTimelineIO** · editores **Kdenlive / Shotcut / Blender** | levar a linha do tempo para onde o cliente edita |

---

## ffmpeg / ffprobe — a base de tudo

Licença: LGPL ou GPL, conforme o build. É o que o kit chama por baixo para sondar, decodificar, cortar, medir loudness e juntar imagem e som.

```bash
ffprobe -v error -show_streams -show_format -of json bruto.mp4        # ficha do bruto (o kit usa isto em `edicao sonda`)
ffmpeg -ss 90.5 -t 6 -i bruto.mp4 -c copy trecho.mp4                  # recorte rápido (corte no keyframe)
ffmpeg -i video.mp4 -af ebur128=peak=true -f null -                   # loudness integrado e pico verdadeiro (a caça faz isto)
ffmpeg -i video.mp4 -vf "freezedetect=n=-60dB:d=0.3" -an -f null -   # quadro congelado (edicao/freeze.py)
```

**Onde o método usa:** `comum.sonda` (ffprobe), `audio.pcm` (decodificação em float), `audio.ganho_para_lufs` (ebur128),
`demo.montar_video` (`trim` + `concat` com quadros exatos), `zoom.zoompan_filtro`.

**Dica de exatidão:** corte por **quadro**, não por segundo — `trim=start_frame=A:end_frame=B,setpts=PTS-STARTPTS`. Voz e imagem saem na
mesma grade (com 60 fps e 48 kHz, 1 quadro = 800 amostras) e a sincronia não deriva.

## faster-whisper — transcrição com tempo por palavra

Licença: MIT. Reimplementação do Whisper (CTranslate2), roda local e é rápida. Entra na **Fase 0**.

```bash
pip install faster-whisper
python exemplos/transcrever.py midia/bruto-decupado.mp4 midia/transcricao.json
```

O arquivo gerado é exatamente o que `fala.py` e a caça leem. Duas lições: transcrição de **nuvem** costuma engolir trechos (confira se
cobre 100% da duração) e, com **retake**, use `condition_on_previous_text=False` (já está no exemplo). O tempo por palavra erra uns
100–200 ms — por isso o kit mede a **energia** do áudio para decidir o ponto exato.

Alternativa leve: **whisper.cpp** (C++, também local).

## auto-editor — decupagem automática

Licença: de domínio público (Unlicense), conforme o repositório. Corta trechos de silêncio (e/ou parados) e **exporta a linha do tempo**
para editores como Premiere, DaVinci Resolve, Final Cut, Shotcut e Kdenlive. Entra na **Fase 0 / 3** quando a gravação chega crua.

```bash
pip install auto-editor
auto-editor gravacao-crua.mp4 --margin 0.2sec            # corta silêncios, deixa 0,2 s de folga
auto-editor gravacao-crua.mp4 --export kdenlive          # em vez de renderizar, gera projeto para editar à mão (veja --help)
```

**Combina com o método:** o auto-editor decupa *grosso* (tira silêncio longo); o kit cuida do *fino* (borda no silêncio exato,
`apos_fala`, retake) e do que vem depois (capítulos, trilha, loudness). Cuidado: decupar demais **tira o respiro natural da fala** —
confira com o bruto de controle (`freeze.py`).

## PySceneDetect — cortes de plano

Licença: BSD. Detecta cortes por conteúdo. Útil para (1) **cortar uma gravação longa de B-roll em cenas** antes de escolher clipes e
(2) **conferir independente** os "cortes relâmpago" da caça.

```bash
pip install scenedetect[opencv]
scenedetect -i master.mp4 detect-content list-scenes
```

## Cartelas e motion — três caminhos

### Remotion (React → vídeo)
Animação em **React/TypeScript**, renderizada quadro a quadro. Ótimo para cartelas, bolinhas de perfil, lower-thirds e vinhetas
parametrizáveis (o nome muda, a animação fica). **Licença própria (source-available):** é gratuito em certos casos e pago em outros —
leia a licença antes de usar comercialmente.

```bash
npx create-video@latest
npx remotion render src/index.ts BolinhaPerfil out/bolinha.mov --codec=prores --prores-profile=4444   # alfa (veja a doc da sua versão)
```

### HTML/CSS + navegador headless (Playwright ou Puppeteer, ambos open source)
Foi a técnica usada na série: a animação é uma página web; o script avança o relógio da página, tira uma foto por quadro e o ffmpeg
junta em **ProRes 4444 (com transparência)**. A cartela fica uma **sobreposição** com alfa que o master coloca por cima do apresentador.
Vantagem: CSS e fontes que você já conhece. Custo: é lento — veja [RENDER-RAPIDO.md](RENDER-RAPIDO.md) para as lições de desempenho.

### MoviePy (Python)
Licença MIT. Bom para **protótipos e composições curtas** (texto sobre clipe, fade, concatenação). Para vídeo longo em 4K, prefira ffmpeg
direto (como `demo.py`): o MoviePy carrega e recodifica mais do que o necessário. A API mudou entre as versões 1.x e 2.x — confira a sua.

## demucs — separar voz e música

Licença: MIT. Separa uma gravação em voz / bateria / baixo / outros. Entra na **Fase 0** quando o áudio do cliente tem música ou ruído
de fundo e você quer uma **voz limpa** (`"voz": "midia/voz-limpa.wav"` no `projeto.json`), ou para tirar a música de uma referência.

```bash
pip install demucs
demucs --two-stems=vocals gravacao.wav          # gera separated/htdemucs/gravacao/vocals.wav e no_vocals.wav
```

**Armadilha medida:** a voz limpa precisa ter a **mesma duração** do bruto (o kit confere ±50 ms e, se não bater, usa o bruto e avisa)
e, sendo mono, entra 3 dB abaixo se for convertida com `-ac 2` — por isso `audio.pcm(mono_cheio=True)`.

## Audacity e pyloudnorm — ouvir e medir

- **Audacity** (GPL): abra o `mix.wav` e ouça os trechos que a caça apontou. O `.niveis.json` que a mistura grava dá o nível de voz,
  trilha e efeitos a cada 0,1 s — com ele você sabe *onde* ouvir. "O ouvido não confirmou" não é revisão: ouça o ponto exato, no fone e na TV.
- **pyloudnorm** (MIT): loudness BS.1770 em Python, quando você quer medir sem chamar o ffmpeg:

```python
import soundfile as sf, pyloudnorm as pyln
dados, sr = sf.read("mix.wav"); print(pyln.Meter(sr).integrated_loudness(dados))
```

## OpenTimelineIO e editores — levar a linha do tempo para onde se edita

- **OpenTimelineIO** (Apache-2.0): formato aberto de linha do tempo, com adaptadores para vários editores. A `EDL.json` do kit é um mapa
  simples e legível; um passo de conversão para OTIO permite abrir o resultado num editor de verdade quando o cliente quiser ajustar à mão.
- **Kdenlive**, **Shotcut** (ambos GPL) e **Blender** (editor de sequência, GPL): onde um humano termina o que a automação deixou.
  O auto-editor exporta direto para vários deles.

---

## Como combinar (receita para quem está começando)

1. **Transcreva** (`faster-whisper`) → `transcricao.json`.
2. **Decupe grosso** (`auto-editor`) se a gravação veio crua; se veio decupada, rode `edicao emendas` para listar as emendas de 1 quadro.
3. **Descreva o vídeo** em `projeto.json` (cortes, inserções, trilha, efeitos em camadas). Modelo em `exemplos/`.
4. **Monte o áudio** (`edicao audio`) e a imagem (ffmpeg; cartelas por Remotion/HTML).
5. **Masterize** (`edicao master`): −14 LUFS + limitador.
6. **Cace** (`edicao caca`) e **corrija pela causa**.
7. **Retoque o áudio sem refazer a imagem** (`edicao remix`, `edicao trilha-delta`).
