"""Suite de testes do sistema de triagem com encadeamento progressivo.

Este módulo valida dois blocos centrais do projeto:

1. Motor de inferência (`Motor`): classificação inicial, evolução por leituras
    sucessivas e disparo de regras de segunda ordem (E2, E4, E5).
2. Critério de desempate (`desempate`): decisão determinística entre pacientes
    no mesmo nível de prioridade usando os cinco critérios definidos no projeto.

Os cenários seguem a nomenclatura T01-T10 e cobrem casos clínicos positivos,
restrições operacionais (SLA), robustez de decisão e estabilidade de prioridade.
"""

import unittest
from core.motor import Motor
from core.desempate import desempate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LEITURA_BASE = {
    'respirando': True,
    'pulso_presente': True,
    'glasgow': 15,
    'spo2': 98,
    'frequencia_cardiaca': 72,
    'temperatura': 36.8,
    'escala_dor': 1,
    'vomitos_por_hora': 0,
}


def montar_paciente(id, idade=30, gestante=False, deficiencia=False, hora='10:00', leitura_extra=None):
    """Monta um dicionário de paciente com leitura inicial padronizada.

    Permite sobrescrever campos da leitura base para construir cenários de teste
    de forma concisa e legível.
    """
    leitura = {**LEITURA_BASE, 'hora': hora, **(leitura_extra or {})}
    return {
        'id': id,
        'idade': idade,
        'gestante': gestante,
        'deficiencia': deficiencia,
        'hora_entrada': hora,
        'leituras': [leitura],
    }


def montar_estado(id, nivel, hora_entrada, hora_nivel, hora_leitura=None, piora=0):
    """Cria um estado sintético usado nos testes de desempate.

    O formato retornado imita o estado consolidado produzido pelo motor, com os
    campos mínimos necessários para a função de desempate.
    """
    return {
        'paciente_id': id,
        'nivel_atual': nivel,
        'hora_entrada': hora_entrada,
        'hora_nivel_atual': hora_nivel,
        'hora_leitura_atual': hora_leitura or hora_nivel,
        'sinais_piorados_simultaneos': piora,
        'eh_vulneravel': False,
    }


def regras_disparadas(log):
    """Extrai os IDs das regras de segunda ordem registradas no log."""
    return [e['id'] for e in log if e.get('tipo') == 'regra_segunda_ordem']


# ---------------------------------------------------------------------------
# T01 – T05: Motor de inferência
# ---------------------------------------------------------------------------

class TestMotor(unittest.TestCase):
    """Testes do fluxo de inferência clínica e regras derivadas do motor."""

    def setUp(self):
        """Cria uma instância limpa do motor antes de cada cenário."""
        self.motor = Motor()

    def test_t01_cadastro_basico_nivel_4(self):
        """T01 — Paciente com dor leve e sinais estáveis deve ser classificado no nível 4."""
        pac = montar_paciente('P01')
        nivel = self.motor.cadastrar_paciente(pac)
        self.assertEqual(nivel, 4)

    def test_t02_piora_progressiva_dois_sinais_dispara_e2(self):
        """T02 — Dois sinais vitais piorando simultaneamente devem disparar a regra E2."""
        pac = montar_paciente('P02')
        self.motor.cadastrar_paciente(pac)

        estado, log = self.motor.cadastrar_leitura_paciente('P02', {
            **LEITURA_BASE,
            'hora': '10:20',
            'spo2': 90,         # caiu de 98 → piorou
            'temperatura': 38.5,  # subiu de 36.8 → piorou
        })

        self.assertIn('E2', regras_disparadas(log))

    def test_t03_piora_progressiva_nivel_nunca_rebaixa(self):
        """T03 — Mesmo com sinais melhorando na leitura seguinte, o nível não pode subir."""
        pac = montar_paciente('P03')
        self.motor.cadastrar_paciente(pac)

        # 2ª leitura: SpO2 cai para 88 → nível clínico 2
        estado_2, _ = self.motor.cadastrar_leitura_paciente('P03', {
            **LEITURA_BASE,
            'hora': '10:20',
            'spo2': 88,
        })
        nivel_na_2a_leitura = estado_2['nivel_atual']

        # 3ª leitura: todos os sinais voltam ao normal
        estado_3, _ = self.motor.cadastrar_leitura_paciente('P03', {
            **LEITURA_BASE,
            'hora': '10:40',
        })
        nivel_na_3a_leitura = estado_3['nivel_atual']

        self.assertLessEqual(nivel_na_3a_leitura, nivel_na_2a_leitura)

    def test_t04_vulneravel_temperatura_sobe_dispara_e4(self):
        """T04 — Paciente vulnerável com temperatura subindo mais de 1 °C deve disparar E4 e ir para nível 2."""
        pac = montar_paciente('P04', idade=65, leitura_extra={'temperatura': 37.0})
        self.motor.cadastrar_paciente(pac)

        estado, log = self.motor.cadastrar_leitura_paciente('P04', {
            **LEITURA_BASE,
            'hora': '10:20',
            'temperatura': 38.5,  # subiu 1.5 °C > 1.0 °C
        })

        self.assertIn('E4', regras_disparadas(log))
        self.assertEqual(estado['nivel_atual'], 2)

    def test_t05_violacao_dupla_sla_dispara_e5(self):
        """T05 — Duas violações de SLA para o mesmo paciente devem disparar E5."""
        pac = montar_paciente('P05', hora='08:00')
        self.motor.cadastrar_paciente(pac)

        # 65 min depois do horário de entrada (SLA do nível 4 é 60 min)
        self.motor.cadastrar_leitura_paciente('P05', {
            **LEITURA_BASE,
            'hora': '09:05',
        })

        # 75 min depois: segunda violação
        estado, log = self.motor.cadastrar_leitura_paciente('P05', {
            **LEITURA_BASE,
            'hora': '09:15',
        })

        self.assertIn('E5', regras_disparadas(log))
        self.assertTrue(estado.get('bloquear_admissoes'))
        self.assertTrue(estado.get('protocolo_sobrecarga'))


# ---------------------------------------------------------------------------
# T06 – T10: Critério de desempate (5 cenários obrigatórios)
# ---------------------------------------------------------------------------

class TestDesempate(unittest.TestCase):
    """Testes dos cinco critérios de desempate entre pacientes empatados."""

    def test_t06_c1_mesma_hora_chegada_desempata_por_id(self):
        """T06 (C1) — Dois pacientes com a mesma hora de chegada e sem piora: desempate por ID."""
        a = montar_estado('PAC-A', 3, '10:00', '10:00')
        b = montar_estado('PAC-B', 3, '10:00', '10:00')

        _, _, criterio, _ = desempate(a, b)

        self.assertEqual(criterio, 'id_paciente')

    def test_t07_c2_velocidade_piora_decide_vencedor(self):
        """T07 (C2) — Paciente com mais sinais piorando tem prioridade."""
        a = montar_estado('PAC-A', 3, '10:05', '10:05', piora=0)
        b = montar_estado('PAC-B', 3, '10:05', '10:05', piora=2)

        vencedor, _, criterio, _ = desempate(a, b)

        self.assertEqual(criterio, 'velocidade_de_piora')
        self.assertEqual(vencedor['paciente_id'], 'PAC-B')

    def test_t08_c3_piora_clinica_supera_vulnerabilidade(self):
        """T08 (C3) — Piora clínica objetiva tem prioridade sobre paciente vulnerável estável."""
        a = montar_estado('PAC-A', 3, '10:02', '10:02', piora=0)
        b = montar_estado('PAC-B', 3, '10:25', '10:25', piora=1)
        a['eh_vulneravel'] = True

        vencedor, _, criterio, _ = desempate(a, b)

        self.assertEqual(criterio, 'velocidade_de_piora')
        self.assertEqual(vencedor['paciente_id'], 'PAC-B')

    def test_t09_c4_violacao_sla_simultanea_sempre_escolhe_um(self):
        """T09 (C4) — Violação iminente simultânea de SLA: o sistema deve sempre escolher um vencedor."""
        a = montar_estado('PAC-A', 3, '10:00', '10:00', hora_leitura='10:28')
        b = montar_estado('PAC-B', 3, '10:00', '10:00', hora_leitura='10:28')

        vencedor, perdedor, _, _ = desempate(a, b)

        self.assertNotEqual(vencedor['paciente_id'], perdedor['paciente_id'])

    def test_t10_c5_quem_entrou_no_nivel_primeiro_tem_prioridade(self):
        """T10 (C5) — Paciente há mais tempo no nível tem prioridade sobre o recém-reclassificado."""
        a = montar_estado('PAC-A', 3, '10:00', '10:30', hora_leitura='10:30')  # chegou ao nível 3 agora
        b = montar_estado('PAC-B', 3, '10:00', '10:15', hora_leitura='10:30')  # nível 3 há 15 min

        vencedor, _, _, _ = desempate(a, b)

        self.assertEqual(vencedor['paciente_id'], 'PAC-B')


if __name__ == '__main__':
    unittest.main(verbosity=2)
