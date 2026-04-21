"""Motor de inferência para triagem por encadeamento progressivo.

O motor recebe um paciente e suas leituras de sinais vitais, aplica regras
primárias, ajusta o resultado para grupos vulneráveis, mede a evolução entre
leituras e então dispara regras de segunda ordem. O mesmo módulo também contém
o critério de desempate entre pacientes no mesmo nível de urgência.

Fluxo geral de processamento:

1. Classificar a leitura atual pelas regras clínicas básicas.
2. Ajustar o nível caso o paciente pertença a um grupo vulnerável.
3. Comparar a leitura atual com a anterior para detectar piora simultânea.
4. Avaliar as regras E1 a E5, que dependem do estado já calculado.
5. Atualizar estado interno e histórico de logs para auditoria.

O foco do módulo é manter a lógica de negócio auditável e determinística,
usando a base declarativa definida em `core.base_conhecimento`.
"""

from core.utils import hora_para_datetime
from core.base_conhecimento import (
    SLA,
    REGRA_VULNERAVEL,
    REGRAS_PRIMARIAS,
    SINAIS_MONITORADOS,
    REGRAS_SEGUNDA_ORDEM,
)


class Motor:
    """Executa a inferência e o acompanhamento do paciente ao longo do tempo.

    A instância mantém um `memory` em memória para armazenar pacientes já
    cadastrados e um `log` de operações para auditoria. O motor foi desenhado
    para processar cada leitura de forma incremental, mas reavaliando o histórico
    quando necessário para preservar consistência clínica.
    """

    def __init__(self):
        """Inicializa o estado interno do motor.

        `memory` guarda pacientes cadastrados por id e `log` acumula eventos de
        execução, regras acionadas e ações disparadas. Ambos são estruturas em
        memória porque o projeto atual prioriza simplicidade e rastreabilidade.
        """
        self.memory = {}
        self.log = []


    def cadastrar_paciente(self, paciente: dict):
        """Registra um paciente novo com a primeira leitura disponível.

        O método valida se o identificador já existe, garante que ao menos uma
        leitura tenha sido informada e impede o cadastro de pacientes que já
        chegam com mais de uma leitura, porque essa situação deve ser tratada pelo
        fluxo incremental de atualização.

        A partir da leitura inicial, o método executa a classificação clínica
        primária, aplica a regra de vulnerabilidade e armazena o paciente na
        memória interna com um log inicial de auditoria.

        Retorna o nível final de prioridade ou uma string descritiva de erro.
        """
        if self.memory.get(paciente['id']):
            return 'Já existe um paciente com esse id'

        log = []
        leitura = paciente.get('leituras', [])

        if not leitura:
            return 'Leituras do paciente não encontradas, por favor informar leituras.'

        if len(leitura) > 1:
            return 'Esse paciente já está cadastrado, se for para adicionar novas leituras utilize outro método.'

        leitura = leitura[0]

        nivel_clinico = self._classificar_pelo_protocolo(leitura, log)
        nivel_final, _ = self._aplicar_regra_vulneravel(nivel_clinico, paciente, log)

        paciente['log'] = log
        self.memory[paciente['id']] = paciente

        return nivel_final


    def cadastrar_leitura_paciente(self, id_paciente: str, leitura: dict):
        """Adiciona uma leitura nova e recalcula o estado do paciente.

        O método recupera o paciente da memória, acrescenta a leitura ao
        histórico e percorre todas as leituras desde o início para garantir que o
        estado final reflita a sequência completa de observações.

        Em cada leitura são executadas, em ordem:

        - classificação clínica pelas regras primárias;
        - ajuste por vulnerabilidade;
        - comparação com a leitura anterior para medir piora;
        - cálculo de tempo no nível atual e verificação de SLA;
        - avaliação das regras de segunda ordem e execução das ações geradas.

        O retorno é uma tupla com o estado final consolidado e o log gerado, ou
        uma string descritiva de erro caso a entrada seja inválida.
        """
        log = []

        if not leitura or not id_paciente:
            return 'Leitura ou id não informado'

        paciente = self.memory.get(id_paciente)

        if not paciente:
            return 'Nenhum paciente encontrado com esse id'

        paciente.setdefault('leituras', []).append(leitura)

        leituras = paciente['leituras']
        hora_entrada = paciente.get('hora_entrada', leituras[0].get('hora', '00:00'))

        leitura_anterior = None
        nivel_da_leitura_anterior = None
        hora_do_nivel_atual = hora_entrada
        alertas_de_sla = 0
        eventos_criticos = 0
        estado_atual = {}

        for leitura_corrente in leituras:
            hora = leitura_corrente.get('hora', '00:00')
            log.append({'tipo': 'nova_leitura', 'hora': hora})

            nivel_clinico = self._classificar_pelo_protocolo(leitura_corrente, log)
            nivel_final, e_vulneravel = self._aplicar_regra_vulneravel(nivel_clinico, paciente, log)

            if nivel_da_leitura_anterior is None:
                nivel_da_leitura_anterior = nivel_final

            # O sistema nunca rebaixa o nivel automaticamente — so pode melhorar ou manter.
            nivel_final = min(nivel_final, nivel_da_leitura_anterior)

            qtd_sinais_piorados, variacao_temp = self._calcular_piora_entre_leituras(leitura_corrente, leitura_anterior)

            try:
                minutos_no_nivel_anterior = (
                    hora_para_datetime(hora) - hora_para_datetime(hora_do_nivel_atual)
                ).total_seconds() / 60
            except ValueError:
                minutos_no_nivel_anterior = 0

            estado_atual = {
                **leitura_corrente,
                'paciente_id': paciente.get('id'),
                'hora_entrada': hora_entrada,
                'hora_leitura_atual': hora,
                'hora_nivel_atual': hora_do_nivel_atual,
                'eh_vulneravel': e_vulneravel,
                'nivel_atual': nivel_final,
                'nivel_anterior': nivel_da_leitura_anterior,
                'minutos_no_nivel_anterior': minutos_no_nivel_anterior,
                'sinais_piorados_simultaneos': qtd_sinais_piorados,
                'variacao_temperatura': variacao_temp,
                'tempo_espera_excede_sla': self._paciente_excedeu_sla(hora_do_nivel_atual, hora, nivel_final),
                'alertas_violacao_sla': alertas_de_sla,
                'eventos_criticos': eventos_criticos,
            }

            log.append({
                'tipo': 'estado_pre_segunda_ordem',
                'nivel': nivel_final,
                'hora': hora,
                'sinais_piorados': qtd_sinais_piorados,
                'excedeu_sla': estado_atual['tempo_espera_excede_sla'],
            })

            self._verificar_regras_de_encadeamento(estado_atual, log)

            alertas_de_sla = estado_atual.get('alertas_violacao_sla', alertas_de_sla)
            eventos_criticos = estado_atual.get('eventos_criticos', eventos_criticos)

            nivel_apos_regras_e = estado_atual['nivel_atual']
            if nivel_apos_regras_e != nivel_da_leitura_anterior:
                hora_do_nivel_atual = hora

            nivel_da_leitura_anterior = nivel_apos_regras_e
            leitura_anterior = leitura_corrente

        estado_atual['historico_classificacoes'] = [
            entrada for entrada in log if entrada.get('tipo') == 'classificacao_primaria'
        ]

        paciente['log'] = log

        return estado_atual, log


    def _sinal_piorou(self, nome_sinal, valor_atual, valor_anterior):
        """Indica se um sinal vital se afastou do estado considerado melhor.

        A regra de piora depende do tipo de sinal:

        - `spo2` e `glasgow` pioram quando o valor diminui;
        - `escala_dor` e `temperatura` pioram quando o valor aumenta;
        - `frequencia_cardiaca` piora quando se afasta mais de 80 bpm, que é a
          referência simplificada adotada pelo projeto.

        Se o sinal não for monitorado por essa rotina, o método retorna `False`.
        """
        if nome_sinal in ('spo2', 'glasgow'):
            return valor_atual < valor_anterior

        if nome_sinal in ('escala_dor', 'temperatura'):
            return valor_atual > valor_anterior

        if nome_sinal == 'frequencia_cardiaca':
            # Piora se o valor se afastou mais de 80 bpm (referencia de normalidade).
            return abs(valor_atual - 80) > abs(valor_anterior - 80)

        return False


    def _calcular_piora_entre_leituras(self, leitura_atual, leitura_anterior):
        """Compara duas leituras consecutivas e resume a evolução clínica.

        O cálculo percorre todos os sinais monitorados pela base de conhecimento
        e contabiliza quantos deles pioraram ao mesmo tempo em relação à leitura
        anterior.

        Além disso, o método retorna a variação absoluta da temperatura, que é um
        indicador usado por regras derivadas para identificar piora relevante,
        principalmente em pacientes vulneráveis.

        Se não houver leitura anterior, o método devolve zero para ambos os
        valores, evitando que a primeira observação seja tratada como piora.
        """
        if leitura_anterior is None:
            return 0, 0.0

        quantidade_piorada = 0

        for sinal in SINAIS_MONITORADOS:
            valor_atual = leitura_atual.get(sinal)
            valor_anterior = leitura_anterior.get(sinal)

            if valor_atual is not None and valor_anterior is not None:
                if self._sinal_piorou(sinal, valor_atual, valor_anterior):
                    quantidade_piorada += 1

        temperatura_atual = leitura_atual.get('temperatura')
        temperatura_anterior = leitura_anterior.get('temperatura')

        variacao_temperatura = (
            temperatura_atual - temperatura_anterior
            if temperatura_atual is not None and temperatura_anterior is not None
            else 0.0
        )

        return quantidade_piorada, variacao_temperatura


    def _paciente_excedeu_sla(self, hora_entrada_nivel, hora_leitura, nivel):
        """Verifica se o tempo de espera ultrapassa o SLA do nível informado.

        A comparação usa o SLA configurado em `core.base_conhecimento`. Nível 1 é
        tratado como atendimento imediato, portanto não há violação de SLA nesse
        caso. Se a conversão de horário falhar, o método opta por retornar `False`
        para não interromper o fluxo por erro de formatação.
        """
        limite_em_minutos = SLA.get(nivel, 120)

        if limite_em_minutos == 0:
            return False  # Nivel 1 e atendimento imediato, SLA nao se aplica.

        try:
            tempo_esperando = hora_para_datetime(hora_leitura) - hora_para_datetime(hora_entrada_nivel)
            minutos_esperando = tempo_esperando.total_seconds() / 60
            return minutos_esperando > limite_em_minutos
        except ValueError:
            return False


    def _verificar_regras_de_encadeamento(self, estado_atual, log):
        """Avalia as regras de segunda ordem contra o estado consolidado.

        Essas regras não observam diretamente os sinais vitais brutos. Em vez
        disso, dependem de variáveis calculadas pelo próprio motor, como número de
        sinais piorados, tempo no nível atual, vulnerabilidade e quantidade de
        alertas de SLA.

        Para cada regra satisfeita, o método registra o disparo no log e executa
        todas as ações associadas, mantendo o fluxo auditável.
        """
        for regra in REGRAS_SEGUNDA_ORDEM:
            if self._avaliar_lista_de_condicoes(regra['condicoes'], estado_atual):
                log.append({
                    'tipo': 'regra_segunda_ordem',
                    'id': regra['id'],
                    'descricao': regra['descricao'],
                })
                for acao in regra['acoes']:
                    self._executar_acao(acao, estado_atual, log)


    def _executar_acao(self, acao, estado_atual, log):
        """Executa uma ação derivada de uma regra usando despacho explícito.

        O método centraliza o efeito colateral de cada ação em funções internas,
        preservando legibilidade e evitando espalhar mutações pelo restante do
        motor. Cada ação altera apenas os campos necessários do estado atual e
        adiciona uma entrada estruturada ao log.
        """
        entrada_log = {'tipo': 'acao', 'acao': acao}

        def _registrar_evento_critico():
            estado_atual['eventos_criticos'] = estado_atual.get('eventos_criticos', 0) + 1

        def _notificar_medico_plantao():
            estado_atual['notificou_medico'] = True

        def _elevar_prioridade_1_grau():
            nivel_novo = max(1, estado_atual['nivel_atual'] - 1)
            entrada_log['nivel_anterior'] = estado_atual['nivel_atual']
            entrada_log['nivel_novo'] = nivel_novo
            estado_atual['nivel_anterior'] = estado_atual['nivel_atual']
            estado_atual['nivel_atual'] = nivel_novo

        def _agendar_leitura_5_minutos():
            estado_atual['proxima_leitura_em_minutos'] = 5

        def _gerar_alerta_violacao_sla():
            estado_atual['alertas_violacao_sla'] = estado_atual.get('alertas_violacao_sla', 0) + 1
            entrada_log['total_alertas'] = estado_atual['alertas_violacao_sla']

        def _escalar_supervisor():
            estado_atual['escalonado_supervisor'] = True

        def _reclassificar_nivel_2():
            # Guarda de seguranca: so reclassifica se o nivel atual for menos urgente que 2.
            if estado_atual['nivel_atual'] > 2:
                entrada_log['nivel_anterior'] = estado_atual['nivel_atual']
                entrada_log['nivel_novo'] = 2
                estado_atual['nivel_anterior'] = estado_atual['nivel_atual']
                estado_atual['nivel_atual'] = 2

        def _bloquear_novas_admissoes():
            estado_atual['bloquear_admissoes'] = True

        def _acionar_protocolo_sobrecarga():
            estado_atual['protocolo_sobrecarga'] = True

        dispatch = {
            'registrar_evento_critico': _registrar_evento_critico,
            'notificar_medico_plantao': _notificar_medico_plantao,
            'elevar_prioridade_1_grau': _elevar_prioridade_1_grau,
            'agendar_leitura_5_minutos': _agendar_leitura_5_minutos,
            'gerar_alerta_violacao_sla': _gerar_alerta_violacao_sla,
            'escalar_supervisor': _escalar_supervisor,
            'reclassificar_nivel_2': _reclassificar_nivel_2,
            'bloquear_novas_admissoes': _bloquear_novas_admissoes,
            'acionar_protocolo_sobrecarga': _acionar_protocolo_sobrecarga,
        }

        handler = dispatch.get(acao)
        if handler:
            handler()

        log.append(entrada_log)


    def _avaliar_condicao(self, condicao, dados):
        """Avalia uma condição isolada do formato `{campo, operador, valor}`.

        O método serve como bloco básico para todas as regras do sistema. Ele
        valida se o campo existe nos dados, resolve o operador desejado e então
        aplica a comparação. Se o campo estiver ausente ou o operador não for
        reconhecido, a condição é considerada falsa.
        """
        campo = condicao['campo']
        operador = condicao['operador']
        valor = condicao['valor']

        if campo not in dados:
            return False

        dado = dados[campo]

        operadores = {
            '==': lambda a, b: a == b,
            '!=': lambda a, b: a != b,
            '<':  lambda a, b: a <  b,
            '<=': lambda a, b: a <= b,
            '>':  lambda a, b: a >  b,
            '>=': lambda a, b: a >= b,
            'in': lambda a, b: a in b,
        }

        fn = operadores.get(operador)
        return fn(dado, valor) if fn else False


    def _avaliar_lista_de_condicoes(self, condicoes, dados):
        """Avalia uma lista de condições com operador lógico opcional.

        A primeira posição da lista pode conter o operador textual `and` ou `or`.
        Quando isso acontece, o restante da lista é interpretado como conjunto de
        condições a serem combinadas. Se não houver operador explícito, o padrão é
        `and`.

        O retorno é booleano e reflete se a regra inteira foi satisfeita.
        """
        if not condicoes:
            return False

        if isinstance(condicoes[0], str):
            operador_logico = condicoes[0]
            lista = condicoes[1:]
        else:
            operador_logico = 'and'
            lista = condicoes

        resultados = [self._avaliar_condicao(condicao, dados) for condicao in lista]

        return any(resultados) if operador_logico == 'or' else all(resultados)


    def _paciente_e_vulneravel(self, paciente):
        """Determina se o paciente pertence a um grupo vulnerável.

        Os critérios considerados são idade igual ou superior a 60 anos, gestação
        ou presença de deficiência. O método só prepara os dados necessários para
        a avaliação declarativa da regra de vulnerabilidade, mantendo a política
        centralizada em `REGRA_VULNERAVEL`.
        """
        dados = {
            'idade': paciente.get('idade', 0),
            'gestante': paciente.get('gestante', False),
            'deficiencia': paciente.get('deficiencia', False),
        }
        return self._avaliar_lista_de_condicoes(REGRA_VULNERAVEL['condicoes'], dados)


    def _aplicar_regra_vulneravel(self, nivel_clinico, paciente, log):
        """Aplica o ajuste de prioridade para pacientes vulneráveis.

        Se o paciente não se enquadrar na regra de vulnerabilidade, o nível
        clínico é mantido. Caso contrário, o nível é elevado em um grau de
        prioridade, respeitando o mínimo 1. Quando há mudança efetiva, o evento é
        registrado no log para fins de auditoria.

        Retorna uma tupla com o nível final e um booleano indicando se o paciente
        foi tratado como vulnerável.
        """
        if not self._paciente_e_vulneravel(paciente):
            return nivel_clinico, False

        nivel_elevado = max(1, nivel_clinico - REGRA_VULNERAVEL['elevacao'])

        if nivel_elevado < nivel_clinico:
            log.append({
                'tipo': 'elevacao_vulnerabilidade',
                'nivel_anterior': nivel_clinico,
                'nivel_novo': nivel_elevado,
                'descricao': REGRA_VULNERAVEL['descricao'],
                'motivo': REGRA_VULNERAVEL['nome'],
            })

        return nivel_elevado, True


    def _classificar_pelo_protocolo(self, leitura, log):
        """Classifica uma leitura usando as regras clínicas primárias.

        O método percorre todas as regras declaradas em `REGRAS_PRIMARIAS` e
        seleciona o nível mais grave encontrado. Isso permite que mais de uma
        condição seja verdadeira na mesma leitura sem perder a prioridade clínica
        mais alta.

        Se nenhuma regra disparar, o comportamento padrão é retornar nível 5,
        que representa o caso não urgente.
        """
        nivel_mais_grave   = 5
        regra_que_disparou = None

        for regra in REGRAS_PRIMARIAS:
            if self._avaliar_lista_de_condicoes(regra['condicoes'], leitura):
                if regra['nivel'] < nivel_mais_grave:
                    nivel_mais_grave   = regra['nivel']
                    regra_que_disparou = regra

        log.append({
            'tipo': 'classificacao_primaria',
            'nivel': nivel_mais_grave,
            'regra': regra_que_disparou['nome'] if regra_que_disparou else 'padrao',
            'descricao': regra_que_disparou['descricao'] if regra_que_disparou else 'Nenhum criterio clinico ativado; nivel padrao (5) aplicado.',
        })

        return nivel_mais_grave
