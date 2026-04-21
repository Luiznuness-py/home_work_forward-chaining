from core.utils import hora_para_datetime
from core.base_conhecimento import SLA


def calcular_proporcao_sla(estado):
    """Calcula a proporcao do SLA ja consumida pelo paciente.

    A proporcao e calculada como:

    tempo_desde_hora_nivel_atual / sla_do_nivel_atual

    Onde:
    - `tempo_desde_hora_nivel_atual` e medido em minutos;
    - `sla_do_nivel_atual` vem da tabela `SLA` na base de conhecimento.

    Regras especiais:
    - Se o SLA do nivel for 0 (nivel 1), retorna `inf` para indicar prioridade
      absoluta de atendimento.
    - Se houver erro de formato nas horas ou tipos invalidos, retorna `0.0`
      para manter o desempate resiliente.
    """
    nivel = estado.get('nivel_atual', 5)
    limite = SLA.get(nivel, 120)

    if limite == 0:
        return float('inf')

    try:
        tempo = (
            hora_para_datetime(estado.get('hora_leitura_atual', '00:00'))
            - hora_para_datetime(estado.get('hora_nivel_atual', '00:00'))
        ).total_seconds() / 60
        return tempo / limite
    except (ValueError, TypeError):
        return 0.0


def desempate(estado_a, estado_b):
    """Decide qual paciente deve ser atendido primeiro em caso de empate.

    Este metodo deve ser usado quando `estado_a` e `estado_b` ja estao no mesmo
    nivel de prioridade. A decisao e deterministica e segue uma cascata fixa de
    criterios, aplicada na ordem abaixo:

    1. Velocidade de piora (`sinais_piorados_simultaneos`): maior vence.
    2. Proporcao de SLA consumida: maior vence.
    3. Tempo no nivel atual (`hora_nivel_atual`): quem entrou antes vence.
    4. Hora de entrada na UPA (`hora_entrada`): quem chegou antes vence.
    5. ID do paciente (`paciente_id`): ordem lexicografica para desempate final.

    Parametros:
    - estado_a (dict): estado consolidado do primeiro paciente.
    - estado_b (dict): estado consolidado do segundo paciente.

    Cada estado deve conter ao menos `paciente_id`. Campos ausentes nos demais
    criterios sao tratados com valores padrao para evitar excecoes.

    Retorna:
    - tuple: (`vencedor`, `perdedor`, `nome_do_criterio`, `descricao_legivel`)
      onde `vencedor` e `perdedor` sao os dicionarios de estado originais.
    """
    id_a = estado_a['paciente_id']
    id_b = estado_b['paciente_id']

    # Passo 1: quem esta se deteriorando mais rapido?
    piora_a = estado_a.get('sinais_piorados_simultaneos', 0)
    piora_b = estado_b.get('sinais_piorados_simultaneos', 0)
    if piora_a != piora_b:
        vencedor = estado_a if piora_a > piora_b else estado_b
        perdedor = estado_b if piora_a > piora_b else estado_a
        desc = (
            f"{vencedor['paciente_id']} atendido antes de {perdedor['paciente_id']}: "
            f"mais sinais piorando ({max(piora_a, piora_b)} vs {min(piora_a, piora_b)})."
        )
        return vencedor, perdedor, 'velocidade_de_piora', desc

    # Passo 2: quem consumiu maior proporcao do SLA?
    prop_a = calcular_proporcao_sla(estado_a)
    prop_b = calcular_proporcao_sla(estado_b)
    if abs(prop_a - prop_b) > 1e-9:
        vencedor = estado_a if prop_a > prop_b else estado_b
        perdedor = estado_b if prop_a > prop_b else estado_a
        desc = (
            f"{vencedor['paciente_id']} atendido antes de {perdedor['paciente_id']}: "
            f"SLA mais consumido ({prop_a:.0%} vs {prop_b:.0%})."
        )
        return vencedor, perdedor, 'proporcao_sla_consumida', desc

    # Passo 3: quem entrou no nivel atual primeiro?
    hora_nivel_a = hora_para_datetime(estado_a.get('hora_nivel_atual', '00:00'))
    hora_nivel_b = hora_para_datetime(estado_b.get('hora_nivel_atual', '00:00'))
    if hora_nivel_a != hora_nivel_b:
        vencedor = estado_a if hora_nivel_a < hora_nivel_b else estado_b
        perdedor = estado_b if hora_nivel_a < hora_nivel_b else estado_a
        desc = (
            f"{vencedor['paciente_id']} atendido antes de {perdedor['paciente_id']}: "
            'entrou no nivel atual primeiro.'
        )
        return vencedor, perdedor, 'tempo_no_nivel_atual', desc

    # Passo 4: quem chegou primeiro na UPA?
    hora_entrada_a = hora_para_datetime(estado_a.get('hora_entrada', '00:00'))
    hora_entrada_b = hora_para_datetime(estado_b.get('hora_entrada', '00:00'))
    if hora_entrada_a != hora_entrada_b:
        vencedor = estado_a if hora_entrada_a < hora_entrada_b else estado_b
        perdedor = estado_b if hora_entrada_a < hora_entrada_b else estado_a
        desc = (
            f"{vencedor['paciente_id']} atendido antes de {perdedor['paciente_id']}: "
            'chegou primeiro na UPA.'
        )
        return vencedor, perdedor, 'hora_entrada_upa', desc

    # Passo 5: desempate final por ID (garante que o resultado nunca e aleatorio)
    vencedor = estado_a if id_a <= id_b else estado_b
    perdedor = estado_b if id_a <= id_b else estado_a
    desc = (
        f"{vencedor['paciente_id']} atendido antes de {perdedor['paciente_id']} "
        'por ordem de ID (todos os outros criterios empataram).'
    )
    return vencedor, perdedor, 'id_paciente', desc
