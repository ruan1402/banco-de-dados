# Gato Faminto

Jogo de labirinto estilo arcade, original, feito no Claude Design. Um gato come todos os petiscos do labirinto enquanto foge de quatro cachorros perseguidores.

## Para que serve
Jogo casual para jogar no navegador (computador ou celular) e teste de um jogo interativo completo dentro de um artefato do Claude Design.

## Funcionalidades
- Labirinto próprio 21x25, simétrico, com casinha dos cachorros e túnel lateral que liga os dois lados.
- 4 cachorros (Rex, Bolt, Toby e Fido), cada um com um jeito de perseguir: direto, mirando à frente, emboscada e o que desiste quando chega perto.
- Alternância entre modo dispersar e modo perseguir, com tempos que mudam por fase.
- 4 peixes grandes (power-ups): os cachorros ficam assustados e podem ser comidos em sequência (200, 400, 800 e 1600 pontos). Quando comidos, voltam para a casinha só com os olhos.
- Peixe dourado de bônus que aparece duas vezes por nível (valor cresce com o nível, até 1000).
- Vidas (3), vida extra aos 5.000 e aos 15.000 pontos, níveis infinitos cada vez mais difíceis, recorde salvo no navegador.
- Animação de morte, tela de nível completo, pausa, sons sintetizados (liga/desliga).
- Três dificuldades ajustáveis no painel de tweaks do canvas: fácil, normal e difícil.

## Como jogar
1. Abra o artefato no Claude Design e clique em Play (ou use a tela cheia).
2. Clique em JOGAR (ou aperte Enter, espaço ou uma seta).
3. Mova o gato com as setas ou WASD. No celular, deslize na tela ou use os botões direcionais.
4. Coma todos os petiscos para passar de nível. Evite os cachorros; pegue um peixe grande para virar o jogo.
5. P ou Esc pausa, M liga/desliga o som.

## Pontuação
- Petisco: 10. Peixe grande: 50. Cachorro assustado: 200, 400, 800, 1600 em sequência. Peixe dourado: 100 x nível (máx. 1000).

## Tecnologias
HTML, CSS e JavaScript puro dentro de um componente do Claude Design (formato .dc.html). Sem bibliotecas externas; sons com Web Audio; fonte Press Start 2P (Google Fonts); recorde em localStorage.

## Estrutura de arquivos
- `codigo/project/canvas.json`: índice do canvas (artboard 640x940, interativo).
- `codigo/project/Main.dc.html`: marcação, estilos e toda a lógica do jogo.

## Como rodar ou publicar
Abra o artefato "Gato Faminto" no Claude Design e use o modo Play. O jogo roda inteiro no navegador.

## Decisões de design
Visual azul neon sobre fundo escuro, paredes só em contorno, personagens feitos de formas CSS (gato laranja, cachorros coloridos). Lógica em passos de 135 ms com movimento suave por transição. Tudo é original: personagens, nomes e labirinto.

## Limitações e ideias futuras
- Não foi testado em dispositivos reais; ajustes de velocidade podem ser necessários.
- Ideias: mais labirintos por nível, ranking online, skins do gato, modo dois jogadores.
