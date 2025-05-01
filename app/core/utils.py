import string
import unicodedata


def normalizar_texto(texto: str) -> str:
    texto = texto.lower()
    texto = texto.translate(str.maketrans("", "", string.punctuation))
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto.strip()
