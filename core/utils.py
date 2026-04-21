from datetime import datetime


def hora_para_datetime(hora_str):
    """Converte uma string no formato HH:MM para um objeto datetime.

    Esta função centraliza a conversão de horários usada no motor e no
    desempate, evitando duplicação e mantendo o mesmo critério de parsing em
    todo o projeto.

    Args:
        hora_str (str): Horário esperado no padrão 24h, por exemplo "10:30".

    Returns:
        datetime: Objeto datetime correspondente ao horário informado.

    Raises:
        ValueError: Quando a string não está no formato esperado.
    """
    return datetime.strptime(hora_str, '%H:%M')