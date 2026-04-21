"""Ponto de entrada da aplicação de triagem.

Este módulo existe para demonstrar o uso do motor de inferência em um fluxo
mínimo de execução. Ele instancia o motor, cadastra um paciente com sua
primeira leitura e, em seguida, tenta processar uma nova leitura de exemplo.

O objetivo do arquivo é servir como porta de entrada para testes manuais e
execução local, sem misturar a apresentação com as regras de negócio que ficam
isoladas em `core.motor` e `core.base_conhecimento`.
"""

from core.motor import Motor

if __name__ == "__main__":
    motor = Motor()

    paciente = {
            'id': 'C1-PAC',
            'idade': 45,
            'gestante': False,
            'deficiencia': False,
            'hora_entrada': '10:00',
            'leituras': [{
                'hora': '10:00',
                'respirando': True,       # parada cardiorrespiratoria
                'pulso_presente': True,
                'glasgow': 15,
                'spo2': 98,
                'frequencia_cardiaca': 72,
                'temperatura': 36.8,
                'escala_dor': 1,
                'vomitos_por_hora': 0,
            }],
        }

    test = motor.cadastrar_paciente(paciente=paciente)

    leitura = {
        'hora': '11:30',
        'respirando': True,       # parada cardiorrespiratoria
        'pulso_presente': True,
        'glasgow': 15,
        'spo2': 100,
        'frequencia_cardiaca': 100,
        'temperatura': 37.8,
        'escala_dor': 7,
        'vomitos_por_hora': 3,
    }

    motor.processar_paciente(id_paciente='C1-PAC', leitura=leitura)

    print()