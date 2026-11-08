# matilha-edicao

**Kit de edição de vídeo longo de especialista** — o método, as boas práticas e as ferramentas que usamos para editar a série de
vídeos longos da **Matilha Equilibrada** (comportamento canino), reunidos num repositório aberto e misturados com o melhor do
ecossistema open source de vídeo.

> Feito como presente para a Matilha Equilibrada e para quem edita conteúdo educativo: um rosto, uma voz, muita informação —
> e a edição construindo em volta.

---

## O que é (e o que não é)

É uma **caixa de ferramentas + um método**, não um editor "aperte o botão". Ela resolve a parte que mais dá retrabalho em vídeo longo:

| Problema | O que o kit faz |
|---|---|
| Corte e cartela caindo no meio da palavra | acha o silêncio exato pela forma de onda (`edicao/fala.py`) |
| Tempo bagunçado depois de cortar retake e inserir vinheta | mapa de tempo bruto → saída, em quadros inteiros (`edicao/mapa.py`) |
| "Frame solto", vão curto entre peças | regras que fecham o vão sem congelar imagem (`edicao/vaos.py`) |
| Música alta demais na TV, efeito "com cara de pronto" | mistura com curva de trilha, efeitos em camadas e **−14 LUFS** (`edicao/audio.py`) |
| Descobrir o defeito só depois do cliente | **caça técnica** no vídeo pronto: frame solto, cena repetida, trilha alta, respiro… (`edicao/caca.py`) |
| Zoom linear / clipe que reinicia com um pulo | curvas bézier e "vai-e-volta" (`edicao/zoom.py`) |
| Render de horas que derruba o PC | ffmpeg em modo leve, pausa por RAM, cache por conteúdo (`edicao/comum.py`) |

**Não é:** gerador de vídeo, escolhedor automático de música/efeito, nem substituto do seu olho. O código **mede e encaixa**; quem
decide é você (veja o [guia](docs/GUIA-DE-EDICAO.md)).

## O fluxo (em uma olhada)

```
Recebimento ─▶ Exploração ─▶ Plano ─▶ Frentes ─▶ Revisão ─▶ Correção/entrega ─▶ Fechar o ciclo
 medir          entender      aprovar   produzir   conferir    por causa            regras novas
                                                       ▲
                                  `edicao caca` no vídeo PRONTO (e de novo a cada conserto)
```

Decupagem → capítulos e viradas de tom → cartelas e bolinhas de nome → B-roll literal → som e trilha → ganho/LUFS → revisão.
Cada fase termina num **portão** de sim/não. Detalhes em [docs/FLUXO-DE-EDICAO.md](docs/FLUXO-DE-EDICAO.md).

## Requisitos

- **Python 3.10+** e **ffmpeg/ffprobe** no PATH (testado com ffmpeg 8.x e Python 3.14 no Windows; escrito para ser portável, mas só foi exercitado lá).
- `pip install -r requirements.txt` (numpy e psutil).
- Opcional: `faster-whisper` (transcrição), `auto-editor`, `demucs`… — veja [docs/FERRAMENTAS-OPEN-SOURCE.md](docs/FERRAMENTAS-OPEN-SOURCE.md).

```bash
git clone https://github.com/MCDPLAYER/matilha-edicao.git
cd matilha-edicao
pip install -r requirements.txt
python -m unittest discover -s tests          # 14 testes, sem mídia
```

## Experimente em 1 minuto (sem nenhuma mídia sua)

```bash
python -m edicao demo
```

O kit gera um bruto sintético (tela de teste + "voz" feita de tom), uma trilha e três sons, e roda o fluxo todo:
acha o ponto da cartela no silêncio → corta um respiro → abre tempo para um capítulo → mistura voz + trilha com curva + efeito em 3 camadas →
monta o vídeo → fecha em −14 LUFS → gera a EDL → **caça**. Saída em `demo-edicao/`: `demo-master.mp4` e `demo-master.CACA.md`.

O relatório da demo acusa de propósito (para você ver como se lê):

| Achado | Por que aparece |
|---|---|
| `respiro sobrando` ~2,3 s | deixamos um silêncio longo sem cortar |
| `trilha subindo` ~+7 dB | a curva da trilha tem uma "ponte" alta demais (a regra é: a subida tem teto) |
| `lasca na vinheta` | o corte do respiro na entrada da cartela faz o quadro saltar na saída (com vídeo real, a solução é o fundo móvel — veja o guia §5) |
| aviso `sfx 'clique solto': só 1 camada` | efeito seco sozinho "tem cara de efeito pronto" |

## Usando com o seu vídeo

1. **Transcreva** com tempo por palavra: `python exemplos/transcrever.py bruto.mp4 transcricao.json`.
2. **Descreva o vídeo** num `projeto.json` (copie `exemplos/projeto.exemplo.json`): bruto, cortes de retake, inserções (capítulo / mini-intro),
   curva da trilha, efeitos em camadas. Os caminhos são relativos à pasta do projeto.
3. **Veja o mapa:** `python -m edicao edl projeto.json EDL.json`.
4. **Monte o áudio:** `python -m edicao audio projeto.json saida/mix.wav` (grava também `mix.wav.niveis.json`).
5. **Monte a imagem** com ffmpeg (a `demo` mostra o caminho com `trim` por quadro + `concat`), cartelas por Remotion ou HTML.
6. **Masterize:** `python -m edicao master saida/sem-som.mp4 saida/mix.wav saida/master.mp4` (−14 LUFS + limitador).
7. **Cace:** `python -m edicao caca saida/master.mp4 --edl EDL.json --transcricao transcricao.json --bruto bruto.mp4 --audio saida/mix.wav`.
8. **Corrija pela causa** e cace de novo — o vídeo inteiro.
9. **Retoque o áudio sem refazer a imagem:** `python -m edicao remix …` · `python -m edicao trilha-delta …`.

### Comandos

```
python -m edicao <comando>
  demo          fluxo inteiro num vídeo sintético
  sonda         resolução, fps, duração e áudio de um arquivo
  audio         mistura voz + trilha + efeitos num WAV
  master        −14 LUFS + limitador + junta com a imagem (sem recodificar o vídeo)
  edl           mapa do vídeo (trechos, camadas) a partir do projeto
  caca          caça técnica no vídeo pronto
  emendas       lista as emendas de 1 quadro que já vêm no bruto
  freeze        quadros congelados (com controle no bruto)
  remix         refaz só o áudio de um master pronto
  trilha-delta  mexe só no volume da trilha num trecho de um master pronto
  vacinas       confere se o caçador ainda acha os defeitos já apontados
```

### Configuração

Valores padrão em `edicao/config.py`; para mudar, copie `config.example.json` para `config.json` (ou aponte `EDICAO_CONFIG`).
Nada de caminho fixo de máquina: tudo é relativo ao `projeto.json` ou passado por argumento.

## O que tem no repositório

```
edicao/               o código (Python)
  config.py comum.py  padrões, sonda, ffmpeg em modo leve, trava de render, cache por conteúdo
  fala.py             silêncio e borda de palavra pela forma de onda
  mapa.py vaos.py     mapa bruto→saída e regras de vão entre peças
  zoom.py             curva bézier, zoompan, esticar clipe sem pulo
  audio.py ajustes.py mistura, trilha com curva dB, efeitos em camadas, locução sem respiro, LUFS, ajustes à mão
  caca.py freeze.py   caça técnica e quadro congelado
  emendas.py          emendas de 1 quadro no bruto
  retoques.py         remix e ajuste de trilha em master pronto
  edl.py projeto.py   leitura do projeto.json e geração da EDL
  vacinas.py demo.py  vacinas do caçador e a demonstração
docs/                 o método e as lições
  GUIA-DE-EDICAO.md          boas práticas por área (entrega, mídia, texto, motion, ritmo, som, CTA, marca, processo)
  FLUXO-DE-EDICAO.md         fases e portões
  CACA-TECNICA.md            defeitos que dá para medir: onde nascem, como impedir, como medir
  FERRAMENTAS-OPEN-SOURCE.md ffmpeg, faster-whisper, auto-editor, demucs, MoviePy, Remotion e companhia
  RENDER-RAPIDO.md           o que mediu e o que ajudou no render
  PLANO-DO-VIDEO-MODELO.md   PEDIDO-DE-SONS-MODELO.md   modelos para copiar
exemplos/             projeto.json de exemplo, vacinas, transcrição
tests/                testes rápidos (sem mídia)
```

## O que ficou de fora de propósito

- **Nenhuma mídia** (vídeo, áudio, voz, rosto, fotos, thumbs) — o kit trabalha sobre arquivos que ficam na sua máquina. O `.gitignore` bloqueia mídia.
- **O render de cartelas animadas** (vinhetas, bolinhas) era específico da identidade da série; aqui há as lições de desempenho, não os arquivos.
- **A escolha de música e de efeitos**: é do editor, por princípio ([guia §6](docs/GUIA-DE-EDICAO.md)).

## Contribuindo

Defeito novo que o público percebeu e a caça não pegou? Abra uma issue com: o tempo, o que o espectador disse, e (se puder) o
trecho. A regra do repositório é a mesma do método: **nota técnica vira vacina antes do conserto**.

## Licença

[MIT](LICENSE). Use, modifique e distribua à vontade. As ferramentas citadas têm licenças próprias — leia antes de usar comercialmente.
