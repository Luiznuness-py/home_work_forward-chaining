# Sistema de Triagem Inteligente

Sistema de triagem por encadeamento progressivo para uma UPA, inspirado no Protocolo de Manchester. O projeto separa a interface de linha de comando, o motor de inferência, a base declarativa de regras e o critério de desempate entre pacientes empatados.

## Visão Geral

O fluxo principal funciona assim:

1. O usuário cadastra um paciente com sua primeira leitura de sinais vitais.
2. O motor classifica a leitura usando regras clínicas declarativas.
3. Se o paciente pertence a um grupo vulnerável, a prioridade é ajustada em um grau.
4. Leituras subsequentes são reprocessadas em sequência para preservar o histórico clínico.
5. Regras de segunda ordem avaliam piora progressiva, SLA e outras conclusões derivadas.
6. Quando dois pacientes têm o mesmo nível, o sistema aplica uma cascata de desempate objetiva.

## Estrutura

```
home_work_forward-chaining/
├── main.py
├── core/
│   ├── base_conhecimento.py
│   ├── desempate.py
│   ├── motor.py
│   └── utils.py
└── test/
    └── test_sistema.py
```

## Componentes

### `main.py`
Interface de linha de comando do sistema. Expõe um menu interativo para cadastrar pacientes, adicionar leituras, visualizar o estado atual, desempatar pacientes e listar os registros carregados na sessão.

### `core/motor.py`
Motor de inferência do projeto. Ele:

1. Classifica a leitura pelas regras primárias.
2. Aplica a regra de vulnerabilidade para idosos, gestantes e pessoas com deficiência.
3. Compara leituras consecutivas para identificar piora simultânea.
4. Calcula SLA e tempo no nível atual.
5. Avalia as regras E1 a E5, que dependem do estado já calculado.
6. Registra tudo em log para auditoria.

### `core/base_conhecimento.py`
Base declarativa de conhecimento. Reúne:

- `SLA`: tempo máximo de espera por nível.
- `REGRAS_PRIMARIAS`: condições clínicas que mapeiam sinais vitais para níveis 1 a 5.
- `REGRA_VULNERAVEL`: elevação de prioridade para grupos vulneráveis.
- `REGRAS_SEGUNDA_ORDEM`: regras derivadas E1 a E5.
- `SINAIS_MONITORADOS`: campos usados na comparação entre leituras.

### `core/desempate.py`
Implementa o desempate entre dois pacientes no mesmo nível de prioridade. A decisão segue esta ordem:

1. Quantidade de sinais piorando simultaneamente.
2. Proporção do SLA já consumida.
3. Tempo no nível atual.
4. Hora de entrada na UPA.
5. ID do paciente.

### `core/utils.py`
Função utilitária compartilhada para converter horários no formato `HH:MM` em objetos `datetime`.

### `test/test_sistema.py`
Suíte de testes do projeto. Os cenários cobrem:

| Categoria | Cenários | O que verifica |
|---|---|---|
| Motor de inferência | T01–T05 | Cadastro, piora progressiva, vulnerabilidade e violações de SLA |
| Desempate | T06–T10 | Os cinco critérios da cascata de desempate |

## Como Executar

### Aplicação interativa

```bash
python main.py
```

### Testes

```bash
python -m unittest discover -s test -p "test_*.py"
```

Se preferir executar apenas a suíte principal:

```bash
python -m unittest test.test_sistema
```

## Regras de Negócio

O projeto trabalha com algumas premissas importantes:

- Nível 1 representa atendimento imediato.
- O sistema não rebaixa automaticamente um paciente quando novas leituras chegam.
- Pacientes vulneráveis podem ter prioridade elevada em um grau.
- Regras de segunda ordem avaliam o estado consolidado, não apenas os sinais vitais brutos.
- O log de execução serve como trilha de auditoria do que foi classificado e disparado.

## Formato das Leituras

Cada leitura usa campos como:

- `hora`
- `respirando`
- `pulso_presente`
- `spo2`
- `glasgow`
- `frequencia_cardiaca`
- `temperatura`
- `escala_dor`
- `vomitos_por_hora`

Campos adicionais podem aparecer nas regras, por exemplo `duracao_apneia`, `queixa_cronica` e `motivo_visita`.

## Observações

- O projeto não depende de banco de dados; o estado fica em memória durante a execução da CLI.
- O desempate só faz sentido quando os pacientes estão no mesmo nível de prioridade.
- Horários devem ser informados no formato `HH:MM`.
