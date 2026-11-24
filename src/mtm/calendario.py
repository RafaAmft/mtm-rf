"""Calendário de dias úteis ANBIMA (feriados nacionais brasileiros)."""

from datetime import date, timedelta
from functools import lru_cache
from typing import Set

import numpy as np


def _pascoa(ano: int) -> date:
    """Calcula a data da Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=64)
def feriados_anbima(ano: int) -> Set[date]:
    """Retorna os feriados nacionais do calendário ANBIMA para um ano."""
    pascoa = _pascoa(ano)
    feriados = {
        date(ano, 1, 1),                      # Confraternização Universal
        pascoa - timedelta(days=48),          # Carnaval (segunda)
        pascoa - timedelta(days=47),          # Carnaval (terça)
        pascoa - timedelta(days=2),           # Sexta-feira Santa
        date(ano, 4, 21),                     # Tiradentes
        date(ano, 5, 1),                      # Dia do Trabalho
        pascoa + timedelta(days=60),          # Corpus Christi
        date(ano, 9, 7),                      # Independência
        date(ano, 10, 12),                    # Nossa Senhora Aparecida
        date(ano, 11, 2),                     # Finados
        date(ano, 11, 15),                    # Proclamação da República
        date(ano, 12, 25),                    # Natal
    }
    if ano >= 2024:
        feriados.add(date(ano, 11, 20))       # Dia Nacional de Zumbi e da Consciência Negra
    return feriados


@lru_cache(maxsize=16)
def _lista_feriados_np(ano_inicio: int, ano_fim: int) -> tuple:
    """Lista ordenada de feriados no formato YYYY-MM-DD para o numpy.busday_count."""
    datas = []
    for ano in range(ano_inicio, ano_fim + 1):
        datas.extend(feriados_anbima(ano))
    return tuple(sorted(d.isoformat() for d in datas))


def contar_dias_uteis(data_inicio: date, data_fim: date) -> int:
    """
    Conta dias úteis entre data_inicio (inclusive) e data_fim (exclusive),
    seguindo a convenção do mercado brasileiro (calendário ANBIMA).
    """
    if data_fim <= data_inicio:
        return 0
    feriados = _lista_feriados_np(data_inicio.year, data_fim.year)
    return int(np.busday_count(data_inicio.isoformat(), data_fim.isoformat(), holidays=feriados))


def eh_dia_util(data: date) -> bool:
    """Retorna True se a data for dia útil segundo o calendário ANBIMA."""
    return data.weekday() < 5 and data not in feriados_anbima(data.year)
