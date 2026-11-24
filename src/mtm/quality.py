"""Quality Gate: 4 regras simples e auditáveis de Data Quality."""

from dataclasses import dataclass
from typing import List

import pandas as pd

from mtm.calendario import contar_dias_uteis
from mtm.config import DQ_REPRICE_TOL, DQ_TAXA_MAX, DQ_TAXA_MIN
from mtm.pricing import calcular_pu_ltn


@dataclass
class ResultadoDQ:
    regra: str
    severidade: str  # BLOQUEANTE ou ALERTA
    status: str      # OK ou FALHA
    linhas_afetadas: int
    detalhe: str


def executar_quality_gate(df_precos: pd.DataFrame, df_posicoes: pd.DataFrame) -> List[ResultadoDQ]:
    """
    Executa as 4 regras de Data Quality sobre a camada Silver:
      1. DQ_UNICIDADE   (BLOQUEANTE): sem duplicatas em (data_base, codigo_titulo)
      2. DQ_VALIDADE    (BLOQUEANTE): taxa dentro de [0%, 50%] e PU > 0
      3. DQ_COMPLETUDE  (BLOQUEANTE): todo título da carteira possui preço na data mais recente
      4. DQ_REPRICE     (ALERTA):     PU calculado pela fórmula bate com o PU oficial do Tesouro
    """
    resultados: List[ResultadoDQ] = []

    # 1. Unicidade
    duplicatas = int(df_precos.duplicated(subset=["data_base", "codigo_titulo"]).sum())
    resultados.append(
        ResultadoDQ(
            regra="DQ_UNICIDADE",
            severidade="BLOQUEANTE",
            status="OK" if duplicatas == 0 else "FALHA",
            linhas_afetadas=duplicatas,
            detalhe="Chave (data_base, codigo_titulo) única"
            if duplicatas == 0
            else f"{duplicatas} registros duplicados encontrados",
        )
    )

    # 2. Validade de faixa
    invalidos = df_precos[
        df_precos["taxa_mercado"].isna()
        | (df_precos["taxa_mercado"] < DQ_TAXA_MIN)
        | (df_precos["taxa_mercado"] > DQ_TAXA_MAX)
        | df_precos["pu_publicado"].isna()
        | (df_precos["pu_publicado"] <= 0)
    ]
    n_inv = len(invalidos)
    resultados.append(
        ResultadoDQ(
            regra="DQ_VALIDADE",
            severidade="BLOQUEANTE",
            status="OK" if n_inv == 0 else "FALHA",
            linhas_afetadas=n_inv,
            detalhe="Todas as taxas e PUs dentro da faixa esperada"
            if n_inv == 0
            else f"{n_inv} linhas com taxa ou PU fora da faixa",
        )
    )

    # 3. Completude dos títulos em carteira na última data disponível
    data_mais_recente = df_precos["data_base"].max()
    titulos_carteira = set(df_posicoes["codigo_titulo"].unique())
    titulos_com_preco = set(
        df_precos.loc[df_precos["data_base"] == data_mais_recente, "codigo_titulo"].unique()
    )
    faltantes = sorted(titulos_carteira - titulos_com_preco)
    resultados.append(
        ResultadoDQ(
            regra="DQ_COMPLETUDE",
            severidade="BLOQUEANTE",
            status="OK" if not faltantes else "FALHA",
            linhas_afetadas=len(faltantes),
            detalhe=f"Todos os títulos em carteira precificados em {data_mais_recente}"
            if not faltantes
            else f"Títulos sem preço em {data_mais_recente}: {', '.join(faltantes)}",
        )
    )

    # 4. Reprice: confere se nossa fórmula bate com o PU oficial do Tesouro
    diffs = []
    for row in df_precos.itertuples(index=False):
        du = contar_dias_uteis(row.data_base, row.data_vencimento)
        pu_calc = calcular_pu_ltn(row.taxa_mercado, du)
        if abs(pu_calc - row.pu_publicado) > DQ_REPRICE_TOL:
            diffs.append((row.data_base, row.codigo_titulo, pu_calc, row.pu_publicado))

    resultados.append(
        ResultadoDQ(
            regra="DQ_REPRICE",
            severidade="ALERTA",
            status="OK" if not diffs else "FALHA",
            linhas_afetadas=len(diffs),
            detalhe=f"PU calculado dentro da tolerância de R$ {DQ_REPRICE_TOL:.2f}"
            if not diffs
            else f"{len(diffs)} linhas com diferença > R$ {DQ_REPRICE_TOL:.2f}",
        )
    )

    return resultados


def tem_falha_bloqueante(resultados: List[ResultadoDQ]) -> bool:
    """Retorna True se alguma regra BLOQUEANTE falhou."""
    return any(r.severidade == "BLOQUEANTE" and r.status == "FALHA" for r in resultados)
