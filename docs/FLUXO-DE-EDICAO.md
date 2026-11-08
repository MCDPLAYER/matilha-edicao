# Fluxo de edição — fase por fase, com portões

Cada fase termina num **portão**: perguntas de sim/não. Fase que não passa no portão **não avança**, e todo feedback volta
para a fase **onde o erro nasceu**. Isso evita o ciclo mais caro da edição: descobrir na revisão final um problema que era
da recepção do material.

> Por que existe: um dos vídeos da série foi editado sem plano aprovado e sem regras fixas. Resultado: dezenas de notas de
> revisão, e mais da metade repetia o que um vídeo anterior já tinha resolvido (CTA, tela final, som na vinheta, 4K).
> Mais da metade dava para pegar **antes de renderizar**.

```
Recebimento ──▶ Exploração ──▶ Plano ──▶ Frentes ──▶ Montagem de revisão ──▶ Correção/entrega ──▶ Fechar o ciclo
   (medir)       (entender)   (aprovar)  (produzir)    (conferir)              (por causa)         (regras)
```

## Fase 0 · Recebimento (sem criatividade, só medir)

- **Ficha do bruto:** resolução, fps, duração, áudio — `python -m edicao sonda bruto.mp4`. A entrega sai na resolução da fonte.
- **Transcrição local com tempo por palavra** (`exemplos/transcrever.py`). A de nuvem costuma engolir trechos.
- **Emendas escondidas do bruto:** `python -m edicao emendas bruto.mp4 emendas.json` — pulos de 1 quadro que já vêm decupados.
- **Retakes marcados:** o apresentador repete a frase → fica o **2º take**.
- Material do cliente para este vídeo (áudios, referências citadas) — **transcreva tudo por inteiro**.
- **Portão 0:** o bruto foi medido? A transcrição cobre 100% da duração? Todo áudio do cliente foi transcrito?

## Fase 1 · Exploração (entender antes de decidir)

- Leia a transcrição inteira e o [guia](GUIA-DE-EDICAO.md).
- **Leitura do vídeo:** tese em 1 frase, partes, e **onde o tom do apresentador muda** (vira capítulo ou mini-intro).
- **Inventário de nomes:** toda raça, organização, pessoa ou objeto citado pelo nome. Cada um vira um **slot de mídia**.
- **Trechos difíceis:** frase abstrata, trecho longo só com o apresentador, enumeração com 5+ nomes.
- **Portão 1:** toda mudança de tom tem decisão? Todo nome citado está no inventário? Os trechos difíceis têm saída proposta?

## Fase 2 · Plano do vídeo (rascunho → refino → aprovação)

1. **Rascunho** do *o quê* por trecho (mídia, texto, nomes, retakes, CTA, viradas de tom), a partir da transcrição + guia.
2. **Refino:** confira palavra por palavra cada "texto literal" e cada tempo de retake contra a transcrição; tire todo fato que
   não está na fala e todo *como* de motion/som que brigue com as regras; transforme em **slots** numerados com tempo, dono
   e critério de pronto. Modelo: [PLANO-DO-VIDEO-MODELO.md](PLANO-DO-VIDEO-MODELO.md).
3. **Aprovação** do plano (a tabela) **antes de qualquer render**. Mudança de plano depois disso passa por quem dirige a edição.
- **Portão 2:** cada slot tem tempo do bruto, tipo, dono, mídia ou texto definido e critério de pronto? O plano cobre o vídeo
  inteiro sem buraco? Tem CTA ao longo do vídeo e tela final?

## Fase 3 · Frentes (podem andar em paralelo)

Cada frente entrega peças por slot e tem o seu portão de sim/não.

| Frente | Entrega | Portão |
|---|---|---|
| Mídia | clipe por slot, cortado no trecho certo, com origem e licença | o clipe mostra o que a **frase** diz? todo nome citado tem clipe? sem marca d'água nem cara de banco genérico? |
| Texto e cartelas | placas no formato "programa de TV" | texto = fala literal? entra **e sai** animado, num respiro? não cobre rosto nem ação? |
| Motion | só onde a ideia pede | tem movimento de verdade (não fade)? lê no celular? recorte sem artefato, ou sem recorte? |
| Capítulos e mini-intros | vinheta com identidade e som + mini-intro nas viradas | a vinheta tem marca, título e som? a mini é mais leve que o capítulo? |
| Zoom | in/out com motivo | tem curva (nunca linear)? ida e volta têm motivo? |
| Som | efeitos coletados (físicos), trilha discreta | nenhum som "genérico de interface"? voz na frente no celular em volume baixo? |

**Trabalhando em paralelo:** só **um render pesado por vez** (`comum.pegar_trava` — um arquivo-trava atômico) e **ninguém escreve
no mesmo arquivo**. Cada frente dona de uma pasta; o "diretor" é quem junta.

## Fase 4 · Montagem de revisão

- **Corte de revisão em 1080p** (rápido).
- **Checagem automática antes de mandar para revisão:** nenhum quadro parado > 0,3 s fora de pausa intencional; toda cartela com saída;
  CTAs presentes; tela final presente; retakes cortados; todo slot do plano preenchido. Ferramentas do kit:
  `python -m edicao freeze` (quadros congelados) e `python -m edicao caca` ([CACA-TECNICA.md](CACA-TECNICA.md)).
- **Folha de contato por slot** (um quadro de cada peça numa grade) e **revisão às cegas**: quem revisa não montou o corte.
- **Portão 4:** a checagem passou? A folha foi olhada por inteiro?

## Fase 5 · Correção e entrega

- Cada nota vira linha numa lista de correções, **agrupada por causa** (treze "travadas" eram uma causa só).
- **Conserto = medir o vídeo inteiro de novo.** O defeito novo nasce na emenda vizinha do conserto.
- Master final na resolução da fonte. `python -m edicao master` fecha o loudness em −14 LUFS e junta com a imagem.
- Retoque de áudio **sem refazer a imagem**: `python -m edicao remix` e `python -m edicao trilha-delta`.

## Fase 6 · Fechar o ciclo

- Todo feedback que vale para os próximos vídeos vira linha no [guia](GUIA-DE-EDICAO.md) **no mesmo dia**, *substituindo* a linha
  que já falava do assunto.
- Defeito técnico apontado pelo cliente vira **vacina** (`python -m edicao vacinas`): o caçador passa a ter que achá-lo para sempre.
- Gosto de uma peça só ("esse ficou feio") vai para o caderno, não para as regras.

---

## O que o kit automatiza (e o que é sempre seu)

| Etapa | O kit faz | Você decide |
|---|---|---|
| Recebimento | sonda, emendas do bruto | o que é retake |
| Ponto do corte/entrada | acha o silêncio exato (`fala.py`) | onde a cartela precisa entrar |
| Linha do tempo | mapa bruto → saída (`mapa.py`), EDL | a estrutura do vídeo |
| Vãos entre peças | fecha vãos curtos (`vaos.py`) | quando um vão é de propósito |
| Som | mistura, curva da trilha, camadas de efeito, LUFS | **qual** música, **qual** efeito |
| Conferência | caça técnica no vídeo pronto | se o achado é real, falso ou intencional |
