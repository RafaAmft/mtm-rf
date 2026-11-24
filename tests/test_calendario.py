from datetime import date

from mtm.calendario import contar_dias_uteis, eh_dia_util


def test_feriado_consciencia_negra_nao_eh_dia_util():
    assert eh_dia_util(date(2026, 11, 20)) is False
    assert eh_dia_util(date(2026, 11, 19)) is True


def test_fim_de_semana_nao_eh_dia_util():
    assert eh_dia_util(date(2026, 11, 21)) is False  # Sábado
    assert eh_dia_util(date(2026, 11, 22)) is False  # Domingo


def test_contar_dias_uteis_ltn_real():
    # Conferido contra Tesouro Direto (19/11/2026 -> 01/01/2032 = 1281 dias úteis)
    assert contar_dias_uteis(date(2026, 11, 19), date(2032, 1, 1)) == 1281
