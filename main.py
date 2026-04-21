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
                'frequencia_cardiaca': 145,
                'temperatura': 36.8,
                'escala_dor': 0,
                'vomitos_por_hora': 0,
            }],
        }

    test = motor.cadastrar_paciente(paciente=paciente)

    print()