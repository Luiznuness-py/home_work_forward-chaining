from pprint import pprint

from core.base_conhecimento import REGRAS_PRIMARIAS, REGRA_VULNERAVEL

class Motor:
    def __init__(self):
        self.memory = {}
        self.log = []


    def processar_paciente(paciente: dict):
        pass
    

    def avaliar_condicao(self, condicao, dados):
        """Verifica se uma unica condicao e verdadeira nos dados do paciente."""
        campo    = condicao['campo']
        operador = condicao['operador']
        valor    = condicao['valor']

        # Se o campo nao foi informado, a condicao nao pode ser satisfeita
        if campo not in dados:
            return False

        dado = dados[campo]

        if operador == '==': return dado == valor
        if operador == '!=': return dado != valor
        if operador == '<':  return dado <  valor
        if operador == '<=': return dado <= valor
        if operador == '>':  return dado >  valor
        if operador == '>=': return dado >= valor
        if operador == 'in': return dado in valor

        return False


    def avaliar_lista_de_condicoes(self, condicoes, dados):
        """
        Avalia uma lista de condicoes contra os dados do paciente.
        Retorna True se o conjunto todo for satisfeito.
        """
        if not condicoes:
            return False

        # Verifica se o primeiro elemento e o operador logico ('and' ou 'or')
        if isinstance(condicoes[0], str):
            operador_logico = condicoes[0]
            lista = condicoes[1:]
        else:
            operador_logico = 'and'
            lista = condicoes

        resultados = [self.avaliar_condicao(condicao, dados) for condicao in lista]

        if operador_logico == 'or':
            return any(resultados)   # basta uma ser verdadeira
        else:
            return all(resultados)   # todas precisam ser verdadeiras


    def paciente_e_vulneravel(self, paciente):
        """Retorna True se o paciente se enquadra na regra de grupo vulneravel."""
        dados = {
            'idade':       paciente.get('idade', 0),
            'gestante':    paciente.get('gestante', False),
            'deficiencia': paciente.get('deficiencia', False),
        }
        return self.avaliar_lista_de_condicoes(REGRA_VULNERAVEL['condicoes'], dados)


    def aplicar_regra_vulneravel(self, nivel_clinico, paciente, log):
        """
        Se o paciente e vulneravel, eleva o nivel 1 grau acima do nivel clinico.
        Retorna (nivel_final, eh_vulneravel).
        """
        if not self.paciente_e_vulneravel(paciente):
            return nivel_clinico, False

        nivel_elevado = max(1, nivel_clinico - REGRA_VULNERAVEL['elevacao'])

        if nivel_elevado < nivel_clinico:
            log.append({
                'tipo':           'elevacao_vulnerabilidade',
                'nivel_anterior': nivel_clinico,
                'nivel_novo':     nivel_elevado,
                'descricao':      REGRA_VULNERAVEL['descricao'],
                'motivo':         REGRA_VULNERAVEL['nome'],
            })

        return nivel_elevado, True


    def classificar_pelo_protocolo(self, leitura, log):
        """
        Aplica as regras primarias e retorna o nivel mais grave encontrado.
        Padrao e Nivel 5 (nao urgente) se nenhuma regra disparar.
        """
        nivel_mais_grave = 5
        regra_que_disparou = None

        for regra in REGRAS_PRIMARIAS:
            if self.avaliar_lista_de_condicoes(regra['condicoes'], leitura):
                if regra['nivel'] < nivel_mais_grave:
                    nivel_mais_grave = regra['nivel']
                    regra_que_disparou = regra

        log.append({
            'tipo': 'classificacao_primaria',
            'nivel': nivel_mais_grave,
            'regra': regra_que_disparou['nome'] if regra_que_disparou else 'padrao',
            'descricao': regra_que_disparou['descricao'] if regra_que_disparou else 'Nenhum criterio clinico ativado; nivel padrao (5) aplicado.',
        })

        return nivel_mais_grave


    def cadastrar_paciente(self, paciente: dict):
        """
        Processa todas as leituras de sinais vitais de um paciente.

        Retorna:
            estado_final  — dicionario com o estado atual do paciente
            log           — lista com todas as inferencias realizadas
        """
        log = []
        leitura = paciente.get('leituras', [])

        if not leitura:
            return 'Leituras do paciente não encontradas, por favor informar leituras.'

        if len(leitura) > 1:
            return 'Esse paciente já está cadastrado, se for para adicionar novas leiturar utilize outro método.'

        leitura = leitura[0]

        # Etapa 1: classificar pelos sinais vitais
        nivel_clinico = self.classificar_pelo_protocolo(leitura, log)

        # Etapa 2: verificar se o paciente e vulneravel e ajustar o nivel
        nivel_final, _ = self.aplicar_regra_vulneravel(nivel_clinico, paciente, log)

        paciente['log'] = log

        self.memory[paciente['id']] = paciente

        pprint(paciente)

        return nivel_final
