# Pedido de sons e músicas · <vídeo>

> O código **não escolhe** som. Ele entrega esta lista; quem edita garimpa no banco que tem licença e coloca os arquivos nas pastas;
> o kit só **encaixa** (posição, curva, nível). Princípios: [GUIA-DE-EDICAO.md §6](GUIA-DE-EDICAO.md).

## Regras do pedido

- **Efeito em camadas:** cada efeito pede 2–3 sons — **ataque** (começo nítido, cobre o começo fraco do outro), **corpo**, **cauda** (opcional).
- **Só som físico (foley):** clique, interruptor, caneta, obturador, papel, madeira, folha, ar/movimento. Nada de bip, "pling", "pop" de interface.
- O som sai **de onde a coisa acontece** (latido da boca; folhas da vinheta = som de folha).
- Cada arquivo com **origem e licença** anotadas.

## Efeitos

| ID | Onde (tempo no bruto) | Evento | Ataque | Corpo | Cauda | Quantas vezes | Ganho sugerido |
|---|---|---|---|---|---|---|---|
| E01 | 03:00.5 | entrada do capítulo 1 | clique de madeira | folhas secas | — | 1 | −8 / −12 dB |
| E02 | recorrente | cartela entra | clique de caneta | papel | — | ~20 | −10 / −14 dB |
| E03 | recorrente | foto/transição de mídia | obturador de câmera | — | — | só em algumas | −12 dB |

Arquivos entregues em `sfx/E01/ataque.wav`, `sfx/E01/corpo.wav` … e descritos em `projeto.json → sfx.eventos[].camadas`
(`ancora_ms` = onde, dentro do arquivo, está o "estalo" que deve cair no instante do evento; `atraso_ms` = defasagem entre as camadas).

## Músicas

| ID | Trecho (capítulo) | Do que fala | Clima | Duração mínima | Observação |
|---|---|---|---|---|---|
| M01 | abertura | gancho | tensão leve, pulsante | 1:00 | termina antes da vinheta |
| M02 | pastoreio | animais de trabalho no campo | rural, folk, violão | 6:30 | **vizinhas nunca repetem** |
| M03 | ciência | estudos, dados | eletrônica suave | 4:00 | — |

Curvas de volume (dB alvo, RMS) vão em `projeto.json → trilha.blocos[].curva_db`: abaixa em fala importante, pausa e humor;
sobe nas pontes **com teto** — a caça mede a subida contra a voz.
