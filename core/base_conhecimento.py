# SLA é o tempo de espera em minutos para o atendimento do paciente com base no 
# nivel de gravidade no caso do mesmo, utilizando o Protocolo de Mancheste. 
SLA = {
    1: 0,   # Emergecia (Vermelho)
    2: 10,  # Muito Urgente (Laranja)
    3: 30,  # Urgente (Amarelo)
    4: 60,  # Pouco Urgente (Verde)
    5: 120, # Não Urgente (Azul)
}

REGRAS_PRIMARIAS = [
    # Nível 1: Emergência
    {
        'nome': 'emergencia',
        'nivel': 1,
        'descricao': 'Parada cardiorrespiratoria',
        'condicoes': [
            {'campo': 'respirando', 'operador': '==', 'valor': False},
        ],
    },
    {
        'nome': 'emergencia',
        'nivel': 1,
        'descricao': 'Ausencia de pulso.',
        'condicoes': [
            {'campo': 'pulso_presente', 'operador': '==', 'valor': False},
        ]
    },
    {
        'nome': 'emergencia',
        'nivel': 1,
        'descricao': 'Apneia confirmada.',
        'condicoes': [
            'and', # Operador entre as condições
            {'campo': 'respirando', 'operador': '==', 'valor': False},
            {'campo': 'duracao_apneia', 'operador': '>=', 'valor': 10}
        ]
    },

    # Nível 2: Muito Urgente
    
    {
        'nome': 'muito_urgente',
        'nivel': 2,
        'descricao': 'SpO2 menor que 90',
        'condicoes': [
            {'campo': 'spo2', 'operador': '<', 'valor': 90}
        ]
    },
    {
        'nome': 'muito_urgente',
        'nivel': 2,
        'descricao': 'dor está maior ou igual que 8 em uma escala de 0 á 10.',
        'condicoes': [
            {'campo': 'escala_dor', 'operador': '>=', 'valor': 8}
        ]
    },
    {
        'nome': 'muito_urgente',
        'nivel': 2,
        'descricao': 'Glasgow menor que 14',
        'condicoes': [
            {'campo': 'glasgow', 'operador': '<', 'valor': 14}
        ]
    },
    {
        'nome': 'muito_urgente',
        'nivel': 2,
        'descricao': 'Frequencia Cardiaca maior que 150.',
        'condicoes': [
            'or', # Operador entre as condições
            {'campo': 'frequencia_cardiaca', 'operador': '>', 'valor': 150},
            {'campo': 'frequencia_cardiaca', 'operador': '<', 'valor': 40},
        ]
    },

    # Nível 3: Urgente

    {
        'nome': 'urgente',
        'nivel': 3,
        'descricao': 'Febre maior que 39.',
        'condicoes': [
            {'campo': 'temperatura', 'operador': '>', 'valor': 39}
        ]
    },
    {
        'nome': 'urgente',
        'nivel': 3,
        'descricao': 'A dor está entre 5 e 7 em uma escala de 0 á 10.',
        'condicoes': [
            'and', # Operador entre as condições
            {'campo': 'escala_dor', 'operador': '>=', 'valor': 5},
            {'campo': 'escala_dor', 'operador': '<=', 'valor': 7}
        ]
    },
    {
        'nome': 'urgente',
        'nivel': 3,
        'descricao': 'Paciente que tiver mais que 3 vomitos por hora.',
        'condicoes': [
            {'campo': 'vomitos_por_hora', 'operador': '>', 'valor': 3}
        ]
    },
    {
        'nome': 'urgente',
        'nivel': 3,
        'descricao': 'Paciente com frequencia cardiaca entre 120 e 150.',
        'condicoes': [
            'and', # Operador entre as condições
            {'campo': 'frequencia_cardiaca', 'operador': '>=', 'valor': 120},
            {'campo': 'frequencia_cardiaca', 'operador': '<=', 'valor': 150},
        ]
    },
    {
        'nome': 'urgente',
        'nivel': 3,
        'descricao': 'Paciente com frequencia cardiaca entre 40 e 50.',
        'condicoes': [
            'and', # Operador entre as condições
            {'campo': 'frequencia_cardiaca', 'operador': '>=', 'valor': 40},
            {'campo': 'frequencia_cardiaca', 'operador': '<=', 'valor': 50},
        ]
    },

    # Nível 4: Pouco Urgente

    {
        'nome': 'pouco_urgente',
        'nivel': 4,
        'descricao': 'Dor leve entre 1 e 4 em escala de 0 a 10.',
        'condicoes': [
            'and', # Operador entre as condições
            {'campo': 'escala_dor', 'operador': '>=', 'valor': 1},
            {'campo': 'escala_dor', 'operador': '<=', 'valor': 4},
        ]
    },
    {
        'nome': 'pouco_urgente',
        'nivel': 4,
        'descricao': 'Queixa cronica sem agravamento agudo e sinais vitais estaveis.',
        'condicoes': [
            {'campo': 'queixa_cronica', 'operador': '==', 'valor': True}
        ]
    },

    # Nível 5: Não Urgente
    {
        'nome': 'nao_urgente',
        'nivel': 5,
        'descricao': 'Sem queixa de dor.',
        'condicoes': [
            {'campo': 'escala_dor', 'operador': '==', 'valor': 0}
        ]
    },
    {
        'nome': 'nao_urgente',
        'nivel': 5,
        'descricao': 'Pedido administrativo ou renovacao de receita.',
        'condicoes': [
            {'campo': 'motivo_visita', 'operador': 'in', 'valor': ['administrativo', 'renovacao_receita']}
        ]
    },
]


# Resolução SUS 2017
# Eleva 1 nivel de prioridade; nunca rebaixa (nivel minimo = 1).
REGRA_VULNERAVEL = {
    'nome': 'grupo_vulneravel',
    'descricao': 'Paciente vulneravel e elevado 1 nivel acima do indicado clinicamente.',
    'elevacao': 1,
    'condicoes': [
        'or',
        {'campo': 'idade',       'operador': '>=', 'valor': 60},
        {'campo': 'gestante',    'operador': '==', 'valor': True},
        {'campo': 'deficiencia', 'operador': '==', 'valor': True},
    ]
}


# Regras de segunda ordem — disparam a partir de conclusões de outras regras, não de fatos brutos.
REGRAS_SEGUNDA_ORDEM = [
    {
        'id': 'E1',
        'descricao': 'Reclassificacao de Nivel 3 para Nivel 2 em menos de 30 minutos.',
        'condicoes': [
            'and',
            {'campo': 'nivel_anterior', 'operador': '==', 'valor': 3},
            {'campo': 'nivel_atual', 'operador': '==', 'valor': 2},
            {'campo': 'minutos_no_nivel_anterior', 'operador': '<',  'valor': 30},
        ],
        'acoes': ['registrar_evento_critico', 'notificar_medico_plantao'],
    },
    {
        'id': 'E2',
        'descricao': 'Dois ou mais sinais vitais pioraram simultaneamente na ultima leitura.',
        'condicoes': [
            {'campo': 'sinais_piorados_simultaneos', 'operador': '>=', 'valor': 2},
        ],
        'acoes': ['elevar_prioridade_1_grau', 'agendar_leitura_5_minutos'],
    },
    {
        'id': 'E3',
        'descricao': 'Paciente aguarda alem do SLA do seu nivel atual.',
        'condicoes': [
            {'campo': 'tempo_espera_excede_sla', 'operador': '==', 'valor': True},
        ],
        'acoes': ['gerar_alerta_violacao_sla', 'escalar_supervisor'],
    },
    {
        'id': 'E4',
        'descricao': 'Paciente vulneravel com temperatura subindo mais de 1 grau desde a ultima leitura.',
        'condicoes': [
            'and',
            {'campo': 'eh_vulneravel',        'operador': '==', 'valor': True},
            {'campo': 'variacao_temperatura', 'operador': '>',  'valor': 1.0},
        ],
        'acoes': ['reclassificar_nivel_2'],
    },
    {
        'id': 'E5',
        'descricao': 'Dois alertas de violacao de SLA gerados para o mesmo paciente.',
        'condicoes': [
            {'campo': 'alertas_violacao_sla', 'operador': '>=', 'valor': 2},
        ],
        'acoes': ['bloquear_novas_admissoes', 'acionar_protocolo_sobrecarga'],
    },
]
