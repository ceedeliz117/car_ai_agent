import re


def es_placa_valida_cdMX(placa: str) -> bool:
    placa = placa.upper()
    return re.fullmatch(r"^[A-Z]{3}\d{3}[A-Z]?$", placa) is not None
