# Critério de Desempate — Documentação

## Contexto

O Protocolo de Manchester define cinco níveis de urgência, mas não estabelece como ordenar os pacientes **dentro do mesmo nível**. Em um UPA de alta demanda, essa problema precisa ser resolvido de forma explícita: deixar dois pacientes empatados sem critério é, na prática, delegar a decisão ao acaso ou ao julgamento individual de quem está na recepção, o que compromete a auditabilidade do sistema.

Nossa proposta é uma **cascata determinística de cinco critérios**, aplicados em ordem. Quando um critério resolve o empate, os seguintes não são consultados. Quando empata, passa para o próximo.

---

## Os Cinco Critérios

### 1. Velocidade de piora (`sinais_piorados_simultaneos`)

**Quem tem mais sinais vitais piorando simultaneamente tem prioridade.**

Um paciente cujos sinais estão piorando apresenta risco clínico imediato e crescente. A deterioração simultânea de dois ou mais sinais é o indicador mais objetivo de agravamento agudo, independente do nível atual. Este critério prioriza o **risco objetivo presente** em relação ao tempo de espera.

### 2. Proporção do SLA consumida

**Quem consumiu maior fração do tempo máximo permitido no seu nível tem prioridade.**

Calculada como `tempo_no_nivel_atual / sla_do_nivel`. Um paciente no Nível 3 esperando 28 dos 30 minutos permitidos (93 %) tem prioridade sobre outro que acabou de entrar no mesmo nível. Este critério garante que nenhum paciente seja esquecido enquanto o sistema atendia outros com piora ativa — é o mecanismo contra inação.

### 3. Tempo no nível atual (`hora_nivel_atual`)

**Quem entrou no nível atual há mais tempo tem prioridade.**

Casos com a mesma proporção de SLA (por exemplo, dois pacientes que chegaram ao Nível 3 ao mesmo instante) são resolvidos pela hora exata de entrada no nível. Este critério é especialmente relevante após reclassificações: um paciente que subiu de Nível 4 para Nível 3 agora perde para quem já estava no Nível 3 há 15 minutos.

### 4. Hora de entrada na UPA (`hora_entrada`)

**Quem chegou primeiro à UPA tem prioridade.**

Se dois pacientes entraram no nível atual ao mesmo tempo (por exemplo, foram admitidos e classificados juntos), quem chegou à unidade primeiro é atendido antes. Reflete a lógica de fila justa para perfis idênticos.

### 5. Ordem lexicográfica do ID (`paciente_id`)

**Desempate final e puramente técnico.**

Quando todos os critérios anteriores resultam em empate exato — cenário raro, mas possível em testes e simulações — o ID do paciente garante que o sistema nunca retorne um resultado ambíguo. A escolha por ID é arbitrária por definição, mas é **determinística e auditável**: a mesma entrada sempre produz a mesma saída.

---

## Cobertura dos Cinco Cenários Obrigatórios

### C1 — Mesmo nível, mesma hora de chegada

**Cenário:** dois pacientes no Nível 3 chegaram com menos de 1 minuto de diferença, nenhum é vulnerável.

**Resolução:** o sistema trabalha com granularidade de minutos (`HH:MM`). Uma diferença de 30 segundos é tratada como chegada simultânea. Com todos os critérios anteriores empatados, o Critério 5 (ID) decide.

**Limitação documentada:** a precisão de minutos impede distinguir chegadas com menos de 60 segundos de diferença. Isso é uma limitação do dado de entrada, não do algoritmo. Em uma implantação real, o horário poderia ser coletado com precisão de segundos.

---

### C2 — Mesmo nível, velocidade de piora diferente

**Cenário:** Paciente A no Nível 3 há 25 minutos, estável. Paciente B no Nível 3 há 5 minutos, com dois sinais piorando.

**Resolução:** Critério 1 — B tem `sinais_piorados_simultaneos = 2`, A tem `0`. B vence.

**Justificativa:** deterioração ativa representa risco imediato crescente. Esperar mais tempo não compensa sinais em queda.

---

### C3 — Vulnerável estável vs. piora clínica objetiva

**Cenário:** A tem 62 anos (vulnerável), Nível 3, aguarda 28 minutos, estável. B tem 35 anos, Nível 3, SpO2 caiu 3 pontos.

**Resolução:** Critério 1 — B tem `sinais_piorados_simultaneos = 1`, A tem `0`. B vence.

**Justificativa:** a vulnerabilidade de A **já foi considerada** ao elevar seu nível clínico em 1 grau na classificação. No desempate, o critério é clínico-objetivo. A proteção contra inação de A ocorre pelo Critério 2: após 28 dos 30 minutos do SLA (93 %), A venceria qualquer paciente que não estivesse em deterioração ativa.

---

### C4 — Violação de SLA iminente simultânea

**Cenário:** dois pacientes no Nível 3 vão violar o SLA em 2 minutos. Apenas uma sala disponível.

**Resolução:** se as proporções de SLA forem idênticas, passa para os Critérios 3, 4 e 5. O sistema **sempre escolhe um** — nunca paralisa.

**Justificativa:** a ausência de inação é garantida pela cascata. Quando E3 dispara para ambos (alerta de violação), o supervisor já foi escalado; a fila do desempate trata quem entra na sala, não quem recebe atenção clínica — que pode ser simultânea via equipe de enfermagem.

---

### C5 — Empate após reclassificação

**Cenário:** Paciente A foi de Nível 4 para Nível 3 agora. Paciente B está no Nível 3 há 15 minutos.

**Resolução:** Critério 2 — B consumiu 50 % do SLA (15/30 min), A consumiu 0 %. B vence.

**Justificativa:** a proporção de SLA captura naturalmente "quem espera há mais tempo no nível atual". O Critério 3 (hora_nivel_atual) chegaria à mesma conclusão, mas o Critério 2 resolve antes.

---

## Propriedades Formais Satisfeitas

| Propriedade | Como é satisfeita |
|-------------|-------------------|
| **Ausência de inação** | O Critério 5 (ID) garante um vencedor sempre; o Critério 2 (SLA) salva pacientes que perdem repetidamente o Critério 1 |
| **Determinismo** | Para a mesma entrada, a mesma saída — todos os critérios são funções puras dos dados do estado |
| **Auditabilidade** | Cada chamada a `desempate()` retorna o nome do critério usado e uma descrição em linguagem natural |
| **Equidade** | Nenhum atributo protegido (gênero, raça, origem, renda) é usado em nenhum dos cinco critérios |
| **Coerência** | O critério documentado aqui é exatamente o implementado em `core/desempate.py` |
