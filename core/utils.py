from datetime import datetime

def hora_para_datetime(hora_str):
    """Converte 'HH:MM' em datetime para calculos de diferenca de tempo."""
    return datetime.strptime(hora_str, '%H:%M')