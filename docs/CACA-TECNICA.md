# Caça técnica — conferir o vídeo PRONTO

> Gosto e criativo ("motion demais", "mais mídia", "cena parada") **não** moram aqui. Aqui é **defeito que dá para medir**.

## Por que ela existe

Num dos vídeos da série o cliente achou dois "frames soltos", uma cena repetida e trilha subindo — e a checagem interna não viu nada.
O diagnóstico:

1. **A checagem olhava o PLANO, não o vídeo.** O plano mostrava o que a montagem *mandou* fazer. Os frames soltos nasceram no *render*
   (o apresentador pulando um quadro depois de um zoom, um painel da tela dividida reiniciando, o fundo da vinheta voltando 3 s no tempo).
2. **A única checagem do vídeo pronto media 4 coisas e gritava lobo.** Todo corte "não passava" por dois falsos positivos. Alarme que sempre
   toca vira ruído: ninguém lê.
3. **Cada conserto criava defeito na emenda vizinha e ninguém re-media o vídeo inteiro.**
4. **O som nunca era medido por camada.** A voz esconde a música no loudness da mistura: a regra "trilha +5 dB no CTA" passou sem ninguém
   medir quanto ela chegava perto da voz, e na TV do cliente ela "subiu bem forte".
5. **Repetição só era vista a olho.**

## A trava (prevenção, não remendo)

- **Todo render (revisão ou master) roda a caça no arquivo PRONTO** e grava `<video>.CACA.md`. Nada vai para o cliente com achado aberto
  sem alguém ter visto a lista.
- **Toda nota técnica do cliente vira VACINA:** um teste que acha aquele defeito, conferido no tempo exato da nota. Se o caçador não acha
  a nota do cliente, o teste está errado, não o cliente. (`python -m edicao vacinas`, formato em `exemplos/vacinas.exemplo.json`.)
- **Conserto = re-medir o vídeo INTEIRO**, não só o ponto da nota.
- **Alarme falso se conserta na hora ou sai da lista.** Checagem que sempre reprova não protege nada.
- **Leitura de vídeo que para no meio NÃO pode virar "limpo".** Os scripts recusam gravar resultado de leitura incompleta
  (aconteceu duas vezes com um bruto 4K).

## Os três níveis: impedir → pré-caça → caça

1. **Impedir:** a montagem não deixa o defeito nascer (`vaos.py` fecha vão curto; `fala.py` põe a borda no silêncio; `zoom.plano_estica`
   nunca deixa o clipe congelar).
2. **Pré-caça:** o plano acusa antes de gastar render (mesmo arquivo de mídia a < 60 s; mesma filmagem a < 30 s; mídia que mudou em relação
   à versão aprovada sem ninguém pedir).
3. **Caça:** `python -m edicao caca` mede o arquivo final. Achado real que passou pelas duas primeiras = falta uma linha de "impedir".

## Mapa: onde nasce, como se impede, como se mede

| Defeito (como o público fala) | Nasce em | Impedir na origem | Detector da caça |
|---|---|---|---|
| "frame solto" no apresentador | **emenda da decupagem no BRUTO** (1 quadro) | `emendas.py` lista uma vez; o plano cobre ou corta para o fechado ali | **pulo no apresentador** |
| apresentador "pulando" quando entra a vinheta | fundo móvel do capítulo voltando no tempo | na entrada o apresentador segue em frente; a troca de trecho fica no meio, com a vinheta opaca | **apresentador volta no tempo** |
| "2 ou 3 frames de outro trecho" | corte interno do próprio clipe de banco perto da ponta do trecho usado | conferir a folha do trecho USADO; corte da fonte a < 0,4 s da ponta = recorta | **corte relâmpago** |
| "repetiu a cena" | dois slots com o mesmo clipe | pré-caça: **mesmo arquivo** a < 60 s | **cena repetida** (hash, > 20 s) |
| "repetiu a cena" (mesma moça, mesmo cão) | dois buscadores no mesmo banco, mesma sessão de filmagem | pré-caça: **mesma filmagem** a < 30 s | **mesma filmagem** |
| painel da tela dividida reinicia | clipe de painel menor que o mosaico | cada painel ≥ duração do mosaico, ou lento/vai-e-volta | corte relâmpago (fraco) |
| clipe aprovado volta ao antigo | uma ferramenta reescreveu todos os prontos | `pedidos.json` = só esses slots podem mudar na rodada; EDL aprovada guardada | pré-caça **REGRESSÃO** |
| "trilha alta", "subiu forte" | curva da trilha (+5 dB virou +11 na energia) | curva com teto; a subida se mede contra a voz | **trilha subindo** / **encostando na voz** |
| "respiro sobrando" | corte de fala / mídia longa | `fala.apos_fala` corta o resto do silêncio | **respiro sobrando** (> 0,9 s sem fala) |
| quadro congelado ("travou") | clipe curto | `zoom.plano_estica` (lento ≤ 1,5×, senão vai-e-volta) | `freeze.py` |
| corte no meio da palavra | corte de retake / inserção | `fala.py` (vale de energia) | voz soando na borda da costura |
| loudness diferente do alvo | master sem medição | `audio.masterizar` | **loudness final** / **pico alto** |

## Os detectores, em uma linha

| Detector | Mede | Limiar padrão |
|---|---|---|
| corte relâmpago | plano de imagem muito curto entre dois planos firmes | < 0,4 s |
| cena repetida | hash perceptual do quadro (dHash 64 bits) igual a outro | > 20 s de distância |
| pulo no apresentador | pico isolado de diferença no meio de tomada contínua | 8× a vizinhança |
| volume pulando | loudness momentâneo (EBU R128) contra a mediana em volta | fundo +4 LU · voz ±2,5 LU |
| respiro sobrando | silêncio de fala | > 0,9 s |
| respiro na emenda | última palavra → vinheta / vinheta → próxima palavra | > 0,30 s / > 0,40 s |
| apresentador solto | apresentador sozinho entre duas peças | < 1 s |
| lasca na vinheta | plano curto colado na entrada/saída de capítulo | < 0,4 s |
| trilha subindo | energia de 2 s da trilha vs. a mediana dela nos 30 s em volta | +5 dB por ≥ 1,5 s |
| trilha encostando | trilha vs. voz enquanto ele fala | a menos de 8 dB por ≥ 1 s |
| loudness final | integrado e pico verdadeiro do arquivo | alvo ±1,0 LU · pico > −1,0 dBTP |

Todos os limiares são constantes no topo de `edicao/caca.py`. **Calibre com os SEUS defeitos conhecidos** (as vacinas existem para isso).

## O agente caçador (quando o script não basta)

O script **mede**; uma pessoa (ou um revisor que **não montou** o corte) **julga** o que ele levantou e olha o que não dá para medir:

1. Rode `python -m edicao caca VIDEO ...` e abra o `CACA.md`.
2. Para cada achado: extraia uma tira de quadros ±0,5 s do ponto (`ffmpeg -ss T -i video.mp4 -frames:v 15 tira_%02d.png`) e classifique
   como **real / falso / intencional**, com o porquê em uma linha.
3. Só depois varra o que não tem medida (por exemplo: nome falado sem texto na tela; locução faltando numa transição com informação).
4. Entregue só a lista final. **Quem revisa não conserta** — quem conserta é a montagem, na causa.

## Rodando

```bash
# com EDL e transcrição (todos os detectores):
python -m edicao caca saida/master.mp4 --edl EDL.json --transcricao midia/transcricao.json \
       --bruto midia/bruto.mp4 --audio saida/mix.wav

# só o arquivo (imagem + loudness):
python -m edicao caca saida/master.mp4
```

Sem EDL, os detectores que dependem do plano ficam de fora; os que medem o arquivo seguem funcionando.
O vídeo é lido uma vez em 64×36 cinza e o resultado fica em cache ao lado do arquivo (`.caca.npz`).
