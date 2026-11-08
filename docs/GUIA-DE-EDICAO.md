# Guia de edição — boas práticas para vídeo longo de especialista

Este guia nasceu da edição de uma série de vídeos longos (10 a 20 minutos) em que um especialista em comportamento canino
fala para a câmera e a edição constrói em volta dele: mídia que ilustra, cartelas, capítulos, som. Cada regra abaixo
apareceu porque um defeito apareceu — e cada uma diz **por quê**, para você poder aplicar com juízo, não de cor.

> Como ler: **regra** em negrito → por que existe → (quando existe) onde o kit ajuda a conferir.
> Nada aqui é lei. É o que funcionou para esse tipo de vídeo: um rosto, uma voz, muita informação.

---

## 1 · Entrega

- **Entregue na resolução da fonte.** Se a gravação veio em 4K, a entrega é 4K. Full HD serve só para corte de revisão.
  *Por quê:* reduzir é irreversível e o cliente percebe quando compara com o bruto.
- **Se o vídeo chega pronto (centralizado, com cor, decupado), não mexa na imagem dele.** Só espaçamento e zoom.
  *Por quê:* correção de cor/enquadramento por cima de uma imagem já tratada costuma piorar.
- **Retake: corte o primeiro take e fique com o segundo.** Se quem gravou pediu "não corte nem reescreva o conteúdo", avise
  na entrega que retake foi cortado — retake não é conteúdo, mas ninguém gosta de descobrir sozinho.
  *Kit:* `cortes_s` no `projeto.json`; `fala.py` acha o silêncio exato para a emenda não morder palavra.
- **Abertura sem texto, só imagens fortes.** O gancho vem pela fala; não comece direto com o rosto. **Depois do gancho, uma vinheta
  da marca separa o gancho do vídeo.**
  *Por quê:* texto grande no quadro 0 compete com a fala; a vinheta dá ao espectador o "agora começou".
- **Confira a mixagem em três lugares:** fone, alto-falante do celular em volume baixo **e** na TV (muita gente assiste na TV).
  *Por quê:* uma mixagem que fecha no fone pode ter trilha forte demais na TV e voz sumida no celular.

## 2 · Mídia (B-roll)

Vídeo de especialista pede **muita** mídia — mas mídia que *prova* o que a frase diz, não enfeite.

- **Falou de um animal, de uma situação, de um lugar → mídia na tela.** A mídia mostra o que a **frase** diz, literalmente.
  Comparação = as duas situações na tela.
- **Dentro do tópico de uma raça (ou de um produto, de uma pessoa), só aquela raça aparece.** Sem clipe da raça: reaproveite
  outro trecho da mesma raça, ou tire o clipe e fique com o apresentador — **nunca outra raça no lugar**. Raça certa com ação
  aproximada pode ficar.
  *Por quê:* o público especialista nota na hora; um husky no meio do Border Collie derruba a credibilidade do resto.
- **Todo nome citado ganha mídia própria**: cada raça, organização, federação, pessoa. Enumeração → sequência rápida ou tela
  dividida, nunca um clipe só para a lista. Organização citada = ficha dela na tela, com mídia por baixo.
- **"Diferentes" na fala = animais diferentes na tela**, nunca um só.
- **Mídia sem texto queimado** (legenda, marca d'água, título), principalmente sob cartelas pequenas. **Recorte que corta pessoa
  ou animal na borda = refaça** (use o modo "inteiro sobre fundo borrado" para vertical).
- **Cite autoridade ou estudo → a autoridade/o estudo aparece** (foto em P&B no cantinho; estudo "paper like" com o trecho destacado).
- **Material ilustrativo nunca é apresentado como prova de um caso.** Faltou mídia boa → avise antes de inventar.
- **Direitos:** clipe de plataformas de vídeo só curto e ilustrativo; na dúvida, banco de licença livre (por exemplo Pexels,
  Pixabay, Mixkit — **leia a licença de cada um**) ou vídeo orgânico de gente comum. Cena parada → troque por uma mais agitada.
  Guarde **origem e licença de cada asset numa lista própria, fora do vídeo** (é o que protege você num pedido de remoção).
  Assinatura de banco pago vale para quem a assinou: não reutilize o asset em outro cliente.
- **A imagem do animal comunica sozinha → deixe ocupar a tela;** a janela do apresentador não cobre a ação.
- **Os primeiros 30 s têm ritmo:** nenhum plano de mídia passa de 3 s.
- **Higiene técnica da mídia** (é o que o público descreve como "frame solto" e "repetiu a cena"):
  - o trecho **usado** não tem corte interno a menos de 0,4 s das pontas;
  - cada painel de tela dividida dura pelo menos o mosaico inteiro;
  - nunca o mesmo arquivo a menos de 60 s, nem a mesma filmagem (mesmo autor/vídeo) a menos de 30 s.

  *Kit:* a caça técnica mede *corte relâmpago*, *cena repetida* e *mesma filmagem* ([CACA-TECNICA.md](CACA-TECNICA.md)).

## 3 · Texto e cartelas

- **Cartela no formato "programa de TV" entra na frente do apresentador**, sem ocupar a tela inteira.
- **Texto na tela = fala literal.** Nunca ele diz uma coisa e a tela mostra outra. Uma palavra destacada por ideia.
- **Texto grande, pensado para o celular.**
- **Nome falado = "bolinha de perfil"** (foto redonda + nome) no canto, por cima dos clipes; entra e sai animada; em enumeração
  as bolinhas se acumulam. Ocupa menos que um cartão e deixa o animal aparecer.
- **A cartela nunca tapa o que importa no fundo** (o animal). Mini-cartelas e CTAs menores, no canto. **Pergunta na tela leva "?".**
- **Frase de efeito, ou que merece atenção, é o apresentador na tela** — não cubra com mídia.
- **Transição que traz informação (uma sigla, uma instituição) leva locução** para quem só está ouvindo.
- **Toda cartela entra E sai animada**, de preferência num respiro da fala. Sumir seco é erro.
- **Tempo de leitura:** se você não consegue ler com calma, está rápido. Uma cartela de cada vez; não abra dos dois lados ao mesmo tempo.
- Apresentação do especialista ("sou o fulano, especialista em…") leva cartelinha de ficha.
- Texto em outro idioma na tela: traduza ou tire.

## 4 · Motion

- **Motion é raro e só onde a ideia pede** (conceito, número, processo). Metade do que você acha que precisa, com **qualidade acima**.
  Ideia que pede movimento **não** vira plaquinha de palavra; plaquinhas variam de lugar e de forma.
- **Fade não é motion.** Tem que ter movimento de verdade, profundidade, algo "se construindo" (e não uma máscara revelando).
- Profundidade com medida: não aplique em tudo.
- **Recorte do apresentador só se sair limpo.** Artefato no recorte → não recorta.
- Pouco tempo e muita animação → dê mais tempo ou simplifique. **Nem toda passagem precisa de animação complexa:** o foco é a história
  clara e o espaço para a personalidade de quem fala; o texto complementa a fala.
- Escolha uma animação de referência que o público já aprovou ("visual simples, ligado à fala, fácil de entender") e meça as novas contra ela.

## 5 · Ritmo, capítulos, zoom

- **Respiro ou pausa nunca é quadro parado.** A imagem continua andando (apresentador em movimento, mídia, zoom lento).
  Quadro congelado lê como "o vídeo travou". *Kit:* `freeze.py` mede, com controle no bruto.
- **Pausa curta entre exemplos: 0,2–0,4 s.** Entre capítulos, um espaço maior. **Sem respiro sobrando antes ou depois de clipe/transição.**
- **Toda borda cai na borda de PALAVRA, medida na forma de onda** — mídia, cartela, mini, capítulo, zoom.
  A transcrição erra 100–200 ms; a energia do áudio decide. **Mini/capítulo entra logo depois da última palavra, e a fala volta logo depois dela.**
  Nenhum trecho de imagem com menos de ~0,4 s entre dois planos; o apresentador não aparece por menos de 1 s entre duas peças.
  **Nada de "frame passado": a saída da vinheta revela o apresentador JÁ de volta, na pose em que ele fala** — nunca parado
  como antes, nem a emenda da gravação logo depois.
  *Kit:* `fala.py` (`vale`, `borda`, `apos_fala`), `vaos.py`, e na caça *respiro na emenda*, *apresentador solto*, *lasca na vinheta*.
- **Vinheta de capítulo** = identidade da marca **com som** (no nosso caso, o cachorrinho das folhas com latidinho), bem feita,
  separando os eixos do vídeo.
- **Viradas de tom dentro do capítulo ganham mini-intro** (mais leve que o capítulo). Intro simples, sem enfeite.
- **A troca de assunto precisa se sentir.** Se o espectador não sabe quando um assunto acabou e outro começou, falta sinal.
- **Zoom só com intenção clara (enfatizar uma fala), sempre com curva (nunca linear).** "Blablabla" normal fica aberto; "e atenção
  nisso" ganha zoom. No resto, o corte direto do plano aberto para um mais fechado já funciona. *Kit:* `zoom.py`.
- Mostre a mesa e o microfone: o take da mesa vale, dá contexto e autoridade.
- **Transição de mídia com "clique de câmera + shutter", só em ALGUMAS** — se está em tudo, é ruído. A cortina leitosa é a alternativa suave.

## 6 · Som

- **Música e efeitos são escolhidos À MÃO por quem edita.** O código não escolhe: entrega uma **lista de pedido** (cada efeito → que som
  ilustra, onde e quantas vezes; cada capítulo → do que fala, clima, duração da trilha), você garimpa no seu banco, e o kit só **encaixa**.
  Modelo: [PEDIDO-DE-SONS-MODELO.md](PEDIDO-DE-SONS-MODELO.md).
- **Efeito em CAMADAS, nunca um som seco sozinho.** Cada efeito junta 2–3 sons: um **ataque** (o "trok", que cobre o começo fraco do
  outro), um **corpo** e, se pedir, uma **cauda**. Juntar mais de um som por efeito faz parte da engenharia de som.
  **Só som FÍSICO (foley):** nada de som de interface sintético ("pling", "plong", "piu", "pop", bip). "Clique é clique físico":
  botão, interruptor, caneta, obturador real, papel, madeira, folha. Shutter e whoosh de ar/movimento valem. O som único e seco
  denuncia automatismo. *Kit:* `sfx.eventos[].camadas` — e o kit **avisa** quando um evento tem só 1 camada.
- **Efeito só quando ajuda a ação ou a transição**, e o som sai de onde a coisa acontece (latido da boca; folhas da vinheta = som de folha).
- **A trilha combina com o tema do capítulo** (pastoreio = rural; piano = afeto; folk = descoberta; eletrônica = ciência). Faixas vizinhas nunca repetem.
- **Locução de transição sem respiro, na velocidade gravada:** sem silêncio antes/depois e pausas internas curtas. A vinheta
  (imagem **e** som) entra no fim da última palavra do take anterior e sai logo depois da última palavra da locução.
  *Por quê:* o que parece "locução lenta" quase sempre é respiro sobrando, não velocidade. *Kit:* `audio.vo_enxuto`.
- **Volume dos efeitos discreto, nunca acima da voz;** o CTA é o mais baixo; equalize pensando na TV (sem agudo cortante).
  Ouça cada efeito sozinho — "meu ouvido não confirmou nada" não vale como revisão.
- **A música faz curvas:** abaixa em fala importante, em pausa e em humor; sobe nas pontes. Fundo baixo.
  **A subida tem teto:** numa TV, trilha +11 dB num CTA "subiu forte". A caça mede cada subida contra a voz (`trilha subindo`,
  `trilha encostando na voz`). *Kit:* `trilha.blocos[].curva_db`.
- **Voz:** limitador de pico, alvo **−14 LUFS** integrado, respiração duplicada → mute. Voz sem eco, "um pouco mais abafada",
  dentro do que a captação permitir. *Kit:* `audio.masterizar`.

## 7 · CTA e fechamento

- **CTAs ao longo do vídeo** (seguir, se inscrever, curtir): ~3 a 4 chamadas num vídeo de 13 min; mais longo, proporcional.
- **CTA sozinho na tela e com cor própria**, sem brigar com motion.
- **Tela final bonita**: musiquinha, logo, 2 vídeos sugeridos; o fechamento fica mais tempo na tela.

## 8 · Marca

- Use a paleta do manual como **base**, não como camisa de força; cada vídeo pode variar o acento.
- Títulos na fonte da marca em caixa alta; miúdo em fonte neutra.
- Movimento sem enfeite gratuito: nada gira ou pisca sozinho. Logo só sobre fundo escuro, sem redesenhar. Nome da marca sempre por extenso.

## 9 · Processo

- **Nada sai para o cliente sem aprovação interna.**
- **Todo render passa pela caça técnica no vídeo PRONTO inteiro.** Nota técnica do cliente vira vacina; conserto = medir o vídeo todo de novo.
- **Ordem da edição, no vídeo inteiro (mesma linguagem do começo ao fim):**
  1. feche a montagem das falas (estrutura e ritmo);
  2. marque as imagens de cada trecho;
  3. busque e monte as cenas (entrada e permanência pela fala);
  4. acabamento: textos, animações e efeitos.

  A trilha pode entrar antes, se ajudar o ritmo.
- **Feedback vira regra no mesmo dia, substituindo a linha que já falava do assunto.** Gosto de uma peça só não vira regra: vai para o caderno.
  Um documento de regras que só cresce deixa de ser lido — dê a ele um teto.

---

### Perguntas que ficaram em aberto (decida por vídeo e anote)

- Enquadramento do apresentador: regra dos terços trocando de lado, ou centralizado como ele entrega?
- Legenda queimada: sim ou não? (A escolha da série foi sem legenda, só texto-destaque.)
- Retake contra "não corte o conteúdo": avisar na entrega ou perguntar antes?
