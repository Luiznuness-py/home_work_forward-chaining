# Reflexão — Critério de Desempate sob Pressão

## Comportamento com 40 pacientes no Nível 3

Com 40 pacientes simultâneos no mesmo nível, a cascata de critérios mantém estabilidade e previsibilidade. O Critério 1 (velocidade de piora) segmenta rapidamente o grupo: quem está piorando sobe para o topo da fila agora quem está estável é ordenado pelo tempo de SLA consumido. Na prática, formam-se dois subgrupos naturais: pacientes em agravamento ativo e pacientes estáveis em espera, cada um com sua própria ordenação interna.

O risco mais concreto nesse cenário é a **competição por prioridade**. Se novos pacientes chegam continuamente ao Nível 3 com sinais em deterioração, eles sempre vencem o Critério 1 sobre pacientes estáveis mais antigos. O sistema não paralisa — o Critério 2 (proporção de SLA) protege os pacientes que esperam há mais tempo, mas pode haver momentos em que um paciente estável fica repetidamente adiado até seu SLA se aproximar do limite.

## Onde o critério falha

**Falha 1 — Contagem sem ponderação clínica.** O Critério 1 conta quantos sinais pioraram, não a gravidade de cada piora. Um paciente com SpO2 caindo de 98 % para 89 % (um sinal, crítico) perde para um com temperatura subindo 0,3 °C e dor aumentando 1 ponto (dois sinais, leves). Em uma implantação real, cada sinal deveria ter peso clínico associado.

**Falha 2 — Granularidade de minutos.** O sistema usa horários no formato `HH:MM`. Dois pacientes que chegaram com 30 segundos de diferença são tratados como simultâneos e caem no desempate por ID — determinístico, mas arbitrário. A limitação está no dado de entrada, não no algoritmo.

**Falha 3 — Pressão de SLA em escala.** Quando muitos pacientes violam o SLA ao mesmo tempo, o supervisor é escalado para todos via E3 e o protocolo de sobrecarga é ativado via E5. O sistema sinaliza corretamente, mas a decisão de alocação de salas torna-se humana, o algoritmo resolve a fila, não a capacidade física.

## Perfis variados e ausência de viés sistemático

A suíte de testes (T01–T10) cobre intencionalmente perfis distintos: adulto jovem sem comorbidades (T01–T03), idoso vulnerável (T04), paciente com baixa urgência inicial e degradação de SLA (T05), e comparações diretas entre perfis vulneráveis e não vulneráveis (T08).

Nenhum critério de desempate utiliza atributos protegidos. Idade aparece no sistema apenas como entrada para a regra de vulnerabilidade (≥ 60 anos), critério clínico explícito da Resolução SUS 2017 — e mesmo assim só é usada na classificação de nível, não no desempate. Dois pacientes com perfis demográficos opostos, mesmos sinais vitais e mesmo tempo de espera recebem exatamente o mesmo tratamento do algoritmo.

O viés mais provável não é demográfico, mas clínico: condições que geram múltiplos sinais alterados simultaneamente (sepse, por exemplo) tendem a subir mais rápido na fila do que condições com uma única alteração severa. Isso reflete a lógica do Protocolo de Manchester, não uma discriminação do sistema.
