import re


def is_valid_plate(placa: str) -> bool:
    """
    Valida placas mexicanas comunes:
    - ABC123
    - ABC1234
    - ABC123D
    - ABC12D
    """
    placa = placa.upper()
    return re.fullmatch(r"^[A-Z]{3}\d{2,4}[A-Z]?$", placa) is not None
