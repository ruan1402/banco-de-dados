# Turbo Circuito

Jogo de corrida 2D visto de cima, feito para jogar no navegador, em português. Você dá **5 voltas** na pista contra **4 competidores controlados pelo computador**, ganha moedas conforme a posição final e gasta tudo na garagem para deixar o carro mais rápido.

## Para que serve
Diversão rápida em partidas curtas (cerca de 1 a 2 minutos cada), com uma progressão simples: correr, ganhar moedas, melhorar o carro e encarar dificuldades maiores.

## Funcionalidades
- **4 pistas** para escolher antes da largada: Super Oval (fácil), Trevo Verde, Pista da Pêra e Flor do Deserto (a mais difícil). Cada uma tem visual e traçado próprios.
- **5 voltas** por corrida, com contagem regressiva (3, 2, 1, VAI!), aviso de volta final e bandeirada.
- **4 rivais** com nomes, cores e níveis de habilidade diferentes. Eles freiam nas curvas, escolhem faixas distintas, usam nitro nas retas e podem bater uns nos outros e em você.
- **3 dificuldades**: Fácil, Médio e Difícil. Quanto maior, mais rápidos os rivais e maior o multiplicador de moedas (x1, x1,6 e x2,4). Os rivais têm um leve ajuste de ritmo para manter a disputa equilibrada.
- **Moedas por posição**: 1º lugar 150, 2º 90, 3º 55, 4º 30 e 5º 15, multiplicadas pela dificuldade.
- **Garagem**:
  - Motor (aceleração, +10% por nível, até o nível 5)
  - Câmbio (velocidade máxima, +7% por nível, até o nível 5)
  - Pneus (aderência e curvas mais fechadas, até o nível 5)
  - Nitro (compra de cargas, até 5; cada carga dá cerca de 1,7 segundo de turbo)
  - Escolha da cor do carro, com prévia
- **Painel da corrida**: volta atual, posição, tempo, melhor volta, velocímetro em km/h, cargas de nitro, classificação ao vivo e minimapa com a posição de todos.
- **Recordes pessoais** por pista (melhor volta e melhor tempo de corrida).
- **Efeitos**: fumaça fora da pista, chamas do nitro, sons de largada, volta, colisão e nitro, e motor que acompanha a velocidade (tecla M liga ou desliga o som).
- **Pausa** com opções de continuar, reiniciar a corrida ou sair para o menu.

## Como jogar
1. No menu, toque em **Jogar**, escolha a pista e a dificuldade e clique em **Largada!**.
2. Controles:
   - Acelerar: seta para cima ou **W**
   - Frear e dar ré: seta para baixo ou **S**
   - Virar: setas esquerda e direita ou **A** e **D**
   - Nitro: **Espaço** ou **Shift** (uma carga por uso)
   - Voltar para a pista: **R**
   - Pausar: **P** ou **Esc**
   - Som: **M**
3. Mantenha o carro no asfalto: na grama ele perde muita velocidade.
4. Ao terminar, veja a classificação e as moedas ganhas. Vá à **Garagem** para melhorar o carro.

## Tecnologias
HTML, CSS e JavaScript puro, com desenho em `canvas` e áudio pela Web Audio API. Não há bibliotecas externas além da fonte do Google Fonts (Russo One e Rajdhani).

## Estrutura de arquivos
```
codigo/
  index.html              versão em página única (jogo completo, tela cheia)
  canvas-design/
    Main.dc.html          versão no formato do Claude Design (artboard interativo)
    canvas.json           índice do canvas do Claude Design
```

## Como rodar ou publicar
- Abra `codigo/index.html` em qualquer navegador moderno, sem servidor.
- Também funciona como artefato (versão publicada: https://claude.ai/artifact/2s3CBUmr9aSYsMojeD9uJS).
- A versão `canvas-design/` serve para abrir dentro do Claude Design.

## Regras e detalhes importantes
- **Pistas**: geradas por fórmulas matemáticas (curvas fechadas), ajustadas ao mundo do jogo e com a largada colocada automaticamente no trecho mais reto. Há uma câmera que segue o seu carro.
- **Física**: o carro tem aceleração, freio, ré, derrapagem leve e perda de velocidade ao sair da pista. Colisões entre carros empurram e desaceleram.
- **IA dos rivais**: seguem a linha da pista com uma faixa própria, calculam a velocidade máxima segura para cada curva e frenam com antecedência.
- **Fim da corrida**: quando você cruza a linha, a corrida acaba em poucos segundos e quem ainda não terminou aparece como "não terminou".
- **Progresso salvo**: moedas, melhorias, nitro, cor, vitórias e recordes ficam no armazenamento do navegador. Em ambientes que bloqueiam esse armazenamento, o progresso volta ao início ao recarregar.

## Decisões de design
- Visual escuro e esportivo, com destaque em laranja e amarelo, fonte "Russo One" nos títulos.
- Progressão pensada para que o carro inicial ganhe do Fácil, dispute o Médio e só vença o Difícil com melhorias e bom uso do nitro.
- Interface toda em português.

## Limitações e ideias futuras
- Não há controles de toque para celular (só teclado).
- Ideias: mais pistas, modo contra o relógio, carros diferentes para comprar, campeonato com várias corridas, placar online e controle por toque.
