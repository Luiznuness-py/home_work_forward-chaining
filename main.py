"""CLI interativo do Sistema de Triagem UPA — SUS Brasil.

Fluxo principal:
  1. Cadastrar paciente com a primeira leitura de sinais vitais.
  2. Adicionar leituras subsequentes e acompanhar a reclassificação.
  3. Desempatar dois pacientes no mesmo nível de prioridade.
  4. Listar todos os pacientes cadastrados na sessão.
"""

from core.motor import Motor
from core.desempate import desempate


CORES = {1: 'VERMELHO', 2: 'LARANJA', 3: 'AMARELO', 4: 'VERDE', 5: 'AZUL'}


# ---------------------------------------------------------------------------
# Coleta de dados
# ---------------------------------------------------------------------------

def _pedir(prompt, tipo=str, padrao=None):
    """Lê um valor do terminal, converte para `tipo` e retorna `padrao` se vazio."""
    while True:
        raw = input(f"  {prompt}: ").strip()
        if not raw:
            return padrao
        try:
            return tipo(raw)
        except ValueError:
            print("  Valor inválido, tente novamente.")


def _pedir_bool(prompt, padrao=True):
    """Solicita uma resposta booleana no terminal.

    Aceita variações iniciadas por "s" como verdadeiro. Se o usuário apenas
    pressionar Enter, devolve o valor padrão informado.
    """
    simbolo = 'S/n' if padrao else 's/N'
    raw = input(f"  {prompt} ({simbolo}): ").strip().lower()
    return padrao if not raw else raw.startswith('s')


def _coletar_leitura():
    """Coleta uma leitura completa de sinais vitais via entrada interativa.

    Retorna um dicionário no formato esperado pelo motor de inferência para
    cadastro inicial ou leituras subsequentes.
    """
    print()
    print('--- Leitura ---')
    print()
    return {
        'hora': _pedir('Hora (HH:MM)', str, '00:00'),
        'respirando': _pedir_bool('Respirando'),
        'pulso_presente': _pedir_bool('Pulso presente'),
        'spo2': _pedir('SpO2 (%)', float),
        'glasgow': _pedir('Glasgow (3-15)', int),
        'frequencia_cardiaca': _pedir('Frequência cardíaca (bpm)', int),
        'temperatura': _pedir('Temperatura (°C)', float),
        'escala_dor': _pedir('Escala de dor (0-10)', int),
        'vomitos_por_hora': _pedir('Vômitos por hora', int, 0),
    }


def _coletar_paciente():
    """Coleta os dados cadastrais básicos de um paciente.

    O método não inclui as leituras; elas são coletadas separadamente para que
    o fluxo de cadastro e atualização reutilize a mesma estrutura de sinais.
    """
    print()
    return {
        'id': _pedir('ID do paciente'),
        'idade': _pedir('Idade', int, 30),
        'gestante': _pedir_bool('Gestante', False),
        'deficiencia': _pedir_bool('Deficiência grave', False),
        'hora_entrada': _pedir('Hora de entrada (HH:MM)', str, '00:00'),
    }


# ---------------------------------------------------------------------------
# Exibição
# ---------------------------------------------------------------------------

def _exibir_estado(estado):
    """Mostra um resumo do estado clínico atual do paciente.

    Exibe nível de prioridade, horário da última leitura e alertas relevantes
    disparados pelas regras de encadeamento (médico notificado, SLA e bloqueio).
    """
    nivel = estado.get('nivel_atual', '?')
    print(f"\n  Nível atual  : {nivel} — {CORES.get(nivel, '?')}")
    print(f"  Hora leitura : {estado.get('hora_leitura_atual', '-')}")
    if estado.get('eh_vulneravel'):
        print("  Grupo vulnerável: Sim")
    if estado.get('notificou_medico'):
        print("  [!] Médico de plantão notificado")
    if estado.get('proxima_leitura_em_minutos'):
        print(f"  [!] Nova leitura em {estado['proxima_leitura_em_minutos']} minutos")
    if estado.get('alertas_violacao_sla', 0):
        print(f"  [!] Alertas de SLA: {estado['alertas_violacao_sla']}")
    if estado.get('bloquear_admissoes'):
        print("  [!] SOBRECARGA — novas admissões bloqueadas")


def _exibir_log(log):
    """Renderiza no terminal as inferências registradas durante o processamento.

    O log mistura decisões de classificação, elevação por vulnerabilidade,
    disparo de regras de segunda ordem e ações executadas.
    """
    print("\n  --- Inferências ---")
    for e in log:
        tipo = e.get('tipo')
        if tipo == 'classificacao_primaria':
            print(f"  [Regra primária] Nível {e['nivel']}: {e['descricao']}")
        elif tipo == 'elevacao_vulnerabilidade':
            print(f"  [Vulnerabilidade] {e['nivel_anterior']} → {e['nivel_novo']}: {e['descricao']}")
        elif tipo == 'regra_segunda_ordem':
            print(f"  [{e['id']}] {e['descricao']}")
        elif tipo == 'acao':
            extra = f" → nível {e['nivel_novo']}" if 'nivel_novo' in e else ''
            extra += f" (total alertas: {e['total_alertas']})" if 'total_alertas' in e else ''
            print(f"      Ação: {e['acao']}{extra}")


# ---------------------------------------------------------------------------
# Estado mínimo para desempate (pacientes sem leituras adicionais)
# ---------------------------------------------------------------------------

def _estado_de(id_pac, motor, estados):
    """Retorna o estado completo se disponível, ou reconstrói um estado mínimo."""
    if id_pac in estados:
        return estados[id_pac]

    paciente = motor.memory.get(id_pac)
    if not paciente:
        return None

    log = paciente.get('log', [])
    classifs = [e for e in log if e.get('tipo') == 'classificacao_primaria']
    nivel = classifs[-1]['nivel'] if classifs else 5
    leituras = paciente.get('leituras', [])
    hora = leituras[-1].get('hora', '00:00') if leituras else '00:00'

    return {
        'paciente_id': id_pac,
        'nivel_atual': nivel,
        'hora_entrada': paciente.get('hora_entrada', hora),
        'hora_nivel_atual': paciente.get('hora_entrada', hora),
        'hora_leitura_atual': hora,
        'sinais_piorados_simultaneos': 0,
        'eh_vulneravel': False,
    }


# ---------------------------------------------------------------------------
# Ações do menu
# ---------------------------------------------------------------------------

def _acao_cadastrar(motor, estados):
    """Executa o fluxo de cadastro de um novo paciente.

    Coleta dados cadastrais e a primeira leitura, delega o processamento ao
    motor e atualiza o cache local de estados para futuras operações da CLI.
    """
    print("\n── Cadastrar Paciente ──")
    dados = _coletar_paciente()
    leitura = _coletar_leitura()

    paciente = {**dados, 'leituras': [leitura]}
    resultado = motor.cadastrar_paciente(paciente)

    if isinstance(resultado, str):
        print(f"\n  Erro: {resultado}")
    else:
        id_pac = dados['id']
        estados[id_pac] = _estado_de(id_pac, motor, estados)
        print(f"\n  Paciente {id_pac} cadastrado — Nível inicial: {resultado} ({CORES.get(resultado, '?')})")


def _acao_leitura(motor, estados):
    """Adiciona uma nova leitura para um paciente já cadastrado.

    Quando o processamento é bem-sucedido, atualiza o último estado conhecido e
    imprime estado consolidado e trilha de inferências da execução.
    """
    print("\n── Adicionar Leitura ──")
    id_pac = _pedir('ID do paciente')
    leitura = _coletar_leitura()

    resultado = motor.cadastrar_leitura_paciente(id_pac, leitura)

    if isinstance(resultado, str):
        print(f"\n  Erro: {resultado}")
    else:
        estado, log = resultado
        estados[id_pac] = estado
        _exibir_estado(estado)
        _exibir_log(log)


def _acao_ver_estado(motor, estados):
    """Exibe o estado atual de um paciente específico.

    Se não houver estado consolidado em memória local, tenta reconstruir um
    estado mínimo a partir das informações persistidas no motor.
    """
    print("\n── Estado do Paciente ──")
    id_pac = _pedir('ID do paciente')

    estado = _estado_de(id_pac, motor, estados)
    if not estado:
        print("  Paciente não encontrado.")
        return

    _exibir_estado(estado)


def _acao_desempatar(motor, estados):
    """Compara dois pacientes empatados no mesmo nível e decide prioridade.

    A função garante pré-condições de existência e igualdade de nível antes de
    chamar o algoritmo de desempate e apresentar o critério utilizado.
    """
    print("\n── Desempate entre Pacientes ──")
    id_a = _pedir('ID do paciente A')
    id_b = _pedir('ID do paciente B')

    est_a = _estado_de(id_a, motor, estados)
    est_b = _estado_de(id_b, motor, estados)

    if not est_a or not est_b:
        print("  Um ou ambos os pacientes não foram encontrados.")
        return

    if est_a['nivel_atual'] != est_b['nivel_atual']:
        print(f"  Pacientes em níveis diferentes ({est_a['nivel_atual']} e {est_b['nivel_atual']}). Desempate não aplicável.")
        return

    _, _, criterio, desc = desempate(est_a, est_b)
    print(f"\n  {desc}")
    print(f"  Critério usado: {criterio}")


def _acao_listar(motor, _estados):
    """Lista todos os pacientes cadastrados com um resumo operacional.

    Para cada paciente, mostra o último nível conhecido, a cor correspondente e
    a quantidade total de leituras já registradas.
    """
    print("\n── Pacientes Cadastrados ──")
    if not motor.memory:
        print("  Nenhum paciente cadastrado.")
        return

    for id_pac, pac in motor.memory.items():
        log = pac.get('log', [])
        classifs = [e for e in log if e.get('tipo') == 'classificacao_primaria']
        nivel = classifs[-1]['nivel'] if classifs else '?'
        leituras = len(pac.get('leituras', []))
        cor = CORES.get(nivel, '?')
        print(f"  {id_pac:15} | Nível: {nivel} ({cor:8}) | Leituras: {leituras}")


# ---------------------------------------------------------------------------
# REPL principal
# ---------------------------------------------------------------------------

MENU = [
    ('1', 'Cadastrar paciente', _acao_cadastrar),
    ('2', 'Adicionar leitura', _acao_leitura),
    ('3', 'Ver estado do paciente', _acao_ver_estado),
    ('4', 'Desempatar dois pacientes', _acao_desempatar),
    ('5', 'Listar pacientes', _acao_listar),
]


def main():
    """Inicializa e executa o loop principal da interface de linha de comando.

    Mantém uma sessão interativa com menu de ações para cadastro, atualização de
    leituras, visualização de estado, desempate e listagem de pacientes.
    """
    motor  = Motor()
    estados = {}  # id_paciente → último estado_atual completo

    print("=" * 42)
    print("  Sistema de Triagem UPA — SUS Brasil")
    print("=" * 42)

    while True:
        print()
        for chave, desc, _ in MENU:
            print(f"  {chave}. {desc}")
        print("  0. Sair")

        opcao = input("\nEscolha: ").strip()

        if opcao == '0':
            print("Encerrando.")
            break

        acao = next((fn for ch, _, fn in MENU if ch == opcao), None)

        if acao:
            try:
                acao(motor, estados)
            except (KeyboardInterrupt, EOFError):
                print("\n  Operação cancelada.")
        else:
            print("  Opção inválida.")


if __name__ == '__main__':
    main()
