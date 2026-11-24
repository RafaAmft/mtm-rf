from datetime import date

import pytest

from mtm.calendario import contar_dias_uteis
from mtm.pricing import calcular_duration_modificada, calcular_dv01, calcular_pu_ltn, precificar_posicao_ltn


@pytest.mark.parametrize(
    "vencimento, taxa_venda, pu_oficial",
    [
        (date(2027, 1, 1), 0.1368, 985.35),
        (date(2028, 1, 1), 0.1459, 859.57),
        (date(2029, 1, 1), 0.1516, 743.97),
        (date(2031, 1, 1), 0.1547, 555.79),
        (date(2032, 1, 1), 0.1555, 479.64),
    ],
)
def test_pu_ltn_bate_com_tesouro_oficial(vencimento, taxa_venda, pu_oficial):
    """Golden test: PU calculado deve bater com o PU Base publicado em 19/11/2026."""
    du = contar_dias_uteis(date(2026, 11, 19), vencimento)
    pu_calc = calcular_pu_ltn(taxa_venda, du)
    assert abs(pu_calc - pu_oficial) <= 0.10


def test_relacao_inversa_taxa_e_preco():
    """Quando a taxa sobe, o PU da LTN cai (e vice-versa)."""
    pu_taxa_menor = calcular_pu_ltn(0.12, 500)
    pu_taxa_maior = calcular_pu_ltn(0.15, 500)
    assert pu_taxa_maior < pu_taxa_menor


def test_precificar_posicao_desagio_quando_taxa_sobe():
    """Comprado a 12% e mercado a 14% deve gerar deságio (MtM < Curva)."""
    res = precificar_posicao_ltn(
        data_base=date(2026, 11, 19),
        data_vencimento=date(2029, 1, 1),
        taxa_compra=0.12,
        taxa_mercado=0.14,
        quantidade=100,
    )
    assert res["valor_mtm"] < res["valor_curva"]
    assert res["agio_desagio"] < 0
    assert res["duration_mod"] > 0
    assert res["dv01"] > 0


def test_duration_e_dv01_basicos():
    dur = calcular_duration_modificada(0.12, 252)
    assert abs(dur - (1.0 / 1.12)) < 0.001
    dv01 = calcular_dv01(892.86, dur)
    assert dv01 > 0
