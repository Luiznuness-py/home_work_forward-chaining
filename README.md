# Sistema de Triagem Inteligente — UPA SUS Brasil

Sistema de triagem baseado em encadeamento progressivo (forward chaining) seguindo o Protocolo de Manchester, desenvolvido como trabalho acadêmico.

---

## Arquitetura

```
home_work_forward-chaining/
│
├── main.py                        # Ponto de entrada da aplicação
│
├── core/
│   ├── motor.py                   # Motor de inferência (forward chaining)
│   └── base_conhecimento.py       # Base de regras e dados de exemplo
│
├── test/
```

---

## Responsabilidades

### `main.py`
Ponto de entrada da aplicação. 

---

### `core/`
Núcleo do sistema. Contém toda a lógica de negócio separada da interface.

#### `core/motor.py`
Motor de encadeamento progressivo. Para cada leitura de sinais vitais de um paciente, executa quatro etapas em sequência:

1. **Classificação primária** — aplica as regras clínicas e determina o nível de urgência pelos sinais vitais.
2. **Grupo vulnerável** — verifica se o paciente é idoso, gestante ou tem deficiência e, se sim, eleva o nível 1 grau acima do indicado clinicamente (Resolução SUS 2017).
3. **Cálculo de piora** — compara a leitura atual com a anterior e conta quantos sinais vitais pioraram simultaneamente.
4. **Regras de encadeamento (E1–E5)** — dispara regras de segunda ordem cujas condições dependem das conclusões das etapas anteriores, não dos sinais vitais brutos.

Também implementa o critério de **desempate** entre dois pacientes no mesmo nível, usando uma cascata de cinco critérios objetivos e auditáveis (velocidade de piora, proporção do SLA consumida, tempo no nível atual, hora de entrada e ID do paciente).

#### `core/base_conhecimento.py`
Repositório declarativo de todas as regras do sistema. Nenhuma regra está embutida no motor como bloco `if/elif`; todas vêm daqui como listas de dicionários. Contém:

- **`SLA`** — tempo máximo de espera por nível de urgência (Protocolo de Manchester).
- **`REGRAS_PRIMARIAS`** — regras que mapeiam sinais vitais para níveis de 1 a 5.
- **`REGRA_VULNERAVEL`** — regra de elevação de prioridade para grupos protegidos pela Resolução SUS 2017.
- **`REGRAS_SEGUNDA_ORDEM`** — regras E1 a E5, que disparam a partir de conclusões de outras regras.
- **`paciente`** — dicionário de exemplo usado pelo modo `--demo`.

---

### `test/`
Suite de testes unitários e de integração do motor.

| Categoria | Cenários | O que verifica |
|---|---|---|
| Classificação básica | C1–C4 | Níveis 1, 2 e 3 pelos sinais vitais |
| Regra E1 | E1 | Reclassificação rápida de nível 3 → 2 em menos de 30 min |
| Piora progressiva | P1, P2 | Deterioração ao longo de múltiplas leituras; nível nunca rebaixa |
| Violação de SLA | V1 | Dois alertas de SLA acionam bloqueio de admissões (E5) |
| Paciente vulnerável | T1 | Temperatura subindo em idoso aciona reclassificação (E4) |
| Desempate | D1–D5 | Os cinco critérios de desempate em ordem de prioridade |
| Robustez | R1 | Campos ausentes nas leituras não causam exceção |
