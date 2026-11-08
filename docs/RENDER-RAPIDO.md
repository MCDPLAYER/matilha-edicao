# Render mais rápido — o que mediu, o que ajudou, o que não valeu

Lições de uma investigação de desempenho num pipeline de vídeo longo em 4K a 60 fps com cartelas animadas por navegador.
✅ = medido naquela máquina (Ryzen de 6 núcleos, RTX 3060 12 GB, 32 GB de RAM) · 📐 = estimativa · ⏳ = não medido.
**Seus números vão variar** — o que vale é o método: medir primeiro, mexer depois, comparar bit a bit quando possível.

## Onde o tempo ia

| Etapa | Tempo (medido) | O que pesava |
|---|---|---|
| Vinheta animada (3–4 s, 200–250 quadros, 4K, alfa) | 8–17 min cada ✅ | ~2,3 s por quadro: 4 fotos 4K do navegador por quadro (borrão de movimento) + as contas do borrão em Python (metade do tempo!) |
| Cartela/bolinha (2–8 s) | 5–14 min cada ✅ | o mesmo mecanismo, mais 2 navegadores abertos |
| Master 4K de ~21 min (~560 trechos) | ~82 min quando refaz tudo ✅ | abrir o bruto 4K HEVC 10 bits no processador + gravar x264 4K |

Uma "leva" típica (17 vinhetas + 32 bolinhas + master) dava ~12 h de máquina, com pausas por falta de RAM.

## O que ajudou (em ordem de valor)

1. **Cache do master por CONTEÚDO, não por posição.** Se o nome do trecho em cache inclui *onde ele cai no vídeo*, trocar uma vinheta
   0,1 s mais longa muda a posição de todos os trechos depois dela e o master refaz quase tudo. Se o nome é o **comando que gera a imagem**
   (+ carimbo dos arquivos que ele lê), só o trecho que mudou é refeito: de ~536 trechos (~80 min) para 3 (~1 min) ✅.
   *No kit:* `comum.digest` e `comum.stamp` são os tijolos desse cache. Detalhe: o carimbo "tamanho + segundo da gravação" tem furos;
   arredondar tempo a 3 casas também. Corrija junto.
2. **Contas do borrão compiladas.** As mesmas contas, na mesma ordem, compiladas com **numba** para usar todos os núcleos:
   ~1.200 ms → ~75 ms por quadro 4K, **diferença zero em todos os pixels** ✅. (Na GPU com PyTorch dava a mesma velocidade, mas
   comia 800 MB de RAM — não compensou.)
3. **"PNG rápido" no navegador.** Pedir a foto de cada quadro com compressão mínima: 336 → 148 ms por foto, diferença máxima de 1 tom em 255 ✅.
   Pegadinha: a captura no jeito antigo devolve o fundo branco ao terminar; ligue o fundo transparente **uma vez** e não misture os dois jeitos
   na mesma página, ou o alfa estraga.
4. **Duas abas no mesmo navegador** (uma tira a foto enquanto a outra monta o quadro) — ⏳ a medir.
5. **Decodificar o bruto pela placa de vídeo** (NVDEC): 3 s de bruto 4K HEVC 10 bits em 1,6 s contra 4,9 s ✅ (3×). É só o "abrir"; o resto do master segue igual.
   Gravar o master pela placa (NVENC): ⏳ compare com x264 contra uma referência sem perda antes de adotar.

Resultado aplicado: vinheta de ~2,4 s/quadro para ~0,73 (≈3,3×) ✅; bolinha ~2,4 → 1,33 ✅ (e ~0,65 com 2 navegadores).

## RAM: o que estoura não é o que você mede

- **O limite é o "total reservável" do Windows (RAM + arquivo de paginação), não a RAM livre.** Houve `MemoryError` com 6,7 GB livres.
  Vigie o reservável (no Windows: contador `\Memory\Commit Limit` − `Committed Bytes`), não só `psutil.virtual_memory().available`.
- Aumente o **arquivo de paginação** (de 16 para ~32 GB, no disco com espaço): não deixa nada mais lento enquanto não é usado.
- O gravador **ProRes** de cada vinheta segura ~2,4 GB sozinho; limitar a 4 threads leva a ~1,7 GB, quase sem custo, porque a gravação corre em paralelo com as fotos.
- `comum.rodar` **suspende** o ffmpeg próprio quando a RAM cai e retoma depois — o render sobrevive a picos.
- **Uma trava de render pesado por vez** (`comum.pegar_trava`), senão duas filas brigam pela mesma RAM.

## Formato intermediário das sobreposições (30 quadros reais)

| Formato | Gravar | RAM do gravador | Abrir de novo | Fiel à entrada? |
|---|---|---|---|---|
| ProRes 4444 | 11,9 s | 2.387 MB | 1,3 s | ±2 tons |
| ProRes 4444 (4 threads) | 14,5 s | 1.714 MB | 1,4 s | ±2 tons |
| FFV1 (sem perda) | 3,3 s | 877 MB | 1,4 s | idêntico |
| QuickTime Animation (sem perda) | 1,6 s | 632 MB | 0,4 s | idêntico |

Os sem perda são **mais fiéis** e mais leves, mas o master converte a cor deles de outro jeito (mediu-se 38 dB de diferença, não por piorar a peça, e sim
pela conversão de cor). Para trocar sem mudar o vídeo final, **fixe a conversão de cor no master e meça de novo**.

## O que NÃO ajudou (medido, saiu da lista)

- **Pular quadro parado:** 0–1% dos quadros se repetem. Sempre tem algo se mexendo.
- **Ligar GPU no navegador:** ele já usava a RTX (ANGLE/D3D11); as flags extras não mudaram o tempo (101 ms × 98 ms).
- **WebP no lugar de PNG:** mais lento (295 ms × 98 ms).
- **ProRes pela placa (Vulkan):** o ffmpeg testado tem, mas recusa o formato com alfa.
- **Captura por screencast / timecut / puppeteer-screen-recorder:** não respeita o avanço quadro a quadro; perde precisão.
- **`beginFrame` determinístico do Chrome:** só numa versão "casca", sem suporte claro a 4K com alfa; ganho menor que o resto, risco alto.

## Regras de bolso

1. **Meça antes** (ffmpeg `-benchmark`, cronômetro por etapa). Metade do tempo costuma estar numa conta, não na ferramenta que você culpa.
2. **Troque uma coisa por vez e compare quadros** (`numpy.abs(a - b).max()`): "bit a bit igual" é a melhor garantia que existe.
3. **Critério de qualidade escrito antes** ("≤ 3 tons, invisível") evita discutir gosto depois.
4. **Guarde o antigo ao lado** (`render.antes-rapido.py`): voltar = renomear.
5. Ganho que só vale da **leva seguinte** em diante (cache novo) não ajuda a leva atual — avise.
