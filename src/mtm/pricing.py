"""Motor de precificação e Marcação a Mercado (MtM) para LTN (Tesouro Prefixado)."""

from datetime import date
from typing import Dict

from mtm.calendario import contar_dias_uteis
from mtm.config import DIAS_UTEIS_ANO, VALOR_FACE_LTN


def calcular_pu_ltn(taxa_anual: float, dias_uteis: int, valor_face: float = VALOR_FACE_LTN) -> float:
    """
    Calcula o Preço Unitário (PU) de uma LTN (zero cupom):
        PU = valor_face / (1 + taxa_anual) ** (dias_uteis / 252)

    Args:
        taxa_anual: Taxa anual em decimal (ex.: 0.1555 para 15,55% a.a.).
        dias_uteis: Dias úteis (calendário ANBIMA) até o vencimento.
        valor_face: Valor de face no vencimento (padrão R$ 1.000,00).
    """
    if dias_uteis <= 0:
        return round(valor_face, 2)
    if taxa_anual <= -1.0:
        raise ValueError(f"Taxa anual inválida: {taxa_anual}")
    pu = valor_face / ((1.0 + taxa_anual) ** (dias_uteis / DIAS_UTEIS_ANO))
    return round(pu, 2)


def calcular_duration_modificada(taxa_anual: float, dias_uteis: int) -> float:
    """
    Duration modificada de uma LTN (em anos).
    Como a LTN não tem cupom, Duration de Macaulay = dias_uteis / 252.
    Duration Modificada = Duration de Macaulay / (1 + taxa_anual).
    """
    if dias_uteis <= 0:
        return 0.0
    duration_macaulay = dias_uteis / DIAS_UTEIS_ANO
    return round(duration_macaulay / (1.0 + taxa_anual), 4)


def calcular_dv01(pu: float, duration_mod: float) -> float:
    """
    DV01 (em R$ por título): variação aproximada do PU para +1 bp (0,01%) na taxa.
    """
    return round(duration_mod * pu * 0.0001, 4)


def precificar_posicao_ltn(
    data_base: date,
    data_vencimento: date,
    taxa_compra: float,
    taxa_mercado: float,
    quantidade: float,
) -> Dict[str, float]:
    """
    Precifica uma posição de LTN comparando Valor na Curva vs. Marcação a Mercado (MtM).
    """
    du = contar_dias_uteis(data_base, data_vencimento)

    pu_curva = calcular_pu_ltn(taxa_compra, du)
    pu_mtm = calcular_pu_ltn(taxa_mercado, du)

    valor_curva = round(pu_curva * quantidade, 2)
    valor_mtm = round(pu_mtm * quantidade, 2)
    agio_desagio = round(valor_mtm - valor_curva, 2)

    dur_mod = calcular_duration_modificada(taxa_mercado, du)
    dv01_unit = calcular_dv01(pu_mtm, dur_mod)
    dv01_posicao = round(dv01_unit * quantidade, 2)

    return {
        "dias_uteis": du,
        "pu_curva": pu_curva,
        "pu_mtm": pu_mtm,
        "valor_curva": valor_curva,
        "valor_mtm": valor_mtm,
        "agio_desagio": agio_desagio,
        "duration_mod": dur_mod,
        "dv01": dv01_posicao,
    }
