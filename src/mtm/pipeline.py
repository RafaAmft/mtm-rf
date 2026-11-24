"""Orquestração ponta a ponta: Bronze -> Silver -> Quality Gate -> Pricing -> Gold."""

import logging
import pandas as pd

from mtm.ingest import ingerir_bronze, transformar_silver
from mtm.load import (
    carregar_gold,
    conectar,
    exportar_csvs_gold,
    finalizar_run_log,
    iniciar_run_log,
    salvar_dq_log,
)
from mtm.pricing import precificar_posicao_ltn
from mtm.quality import executar_quality_gate, tem_falha_bloqueante

logger = logging.getLogger(__name__)


def calcular_fato_mtm(df_precos: pd.DataFrame, df_posicoes: pd.DataFrame) -> pd.DataFrame:
    """Cruza posições com preços diários, calcula MtM vs. Curva e o P&L diário."""
    df_join = df_posicoes.merge(
        df_precos[["data_base", "codigo_titulo", "taxa_mercado", "pu_publicado"]],
        on="codigo_titulo",
        how="inner",
    )
    # Só precifica datas a partir da data de compra do ativo
    df_join = df_join[df_join["data_base"] >= df_join["data_compra"]].copy()

    linhas = []
    for row in df_join.itertuples(index=False):
        calc = precificar_posicao_ltn(
            data_base=row.data_base,
            data_vencimento=row.data_vencimento,
            taxa_compra=row.taxa_compra,
            taxa_mercado=row.taxa_mercado,
            quantidade=row.quantidade,
        )
        linhas.append(
            {
                "data_base": row.data_base,
                "codigo_carteira": row.codigo_carteira,
                "codigo_titulo": row.codigo_titulo,
                "quantidade": row.quantidade,
                "taxa_compra": row.taxa_compra,
                "taxa_mercado": row.taxa_mercado,
                **calc,
            }
        )

    df_fato = pd.DataFrame(linhas).sort_values(
        ["codigo_carteira", "codigo_titulo", "data_base"]
    ).reset_index(drop=True)

    # P&L diário = variação do valor MtM em relação ao dia útil anterior
    df_fato["pnl_dia"] = (
        df_fato.groupby(["codigo_carteira", "codigo_titulo"])["valor_mtm"]
        .diff()
        .fillna(0.0)
        .round(2)
    )
    return df_fato


def executar_pipeline(offline: bool = False) -> dict:
    """Executa o pipeline completo e retorna um resumo da execução."""
    conn = conectar()
    run_id = iniciar_run_log(conn, modo="OFFLINE" if offline else "ONLINE")
    hash_bronze = ""
    linhas_silver = 0

    try:
        # 1. Bronze
        caminho_bronze, hash_bronze = ingerir_bronze(offline=offline)

        # 2. Silver
        df_precos, df_posicoes = transformar_silver(caminho_bronze)
        linhas_silver = len(df_precos)

        # 3. Quality Gate
        resultados_dq = executar_quality_gate(df_precos, df_posicoes)
        salvar_dq_log(conn, run_id, resultados_dq)

        for r in resultados_dq:
            logger.info("DQ | %-14s | %-10s | %-5s | %s", r.regra, r.severidade, r.status, r.detalhe)

        if tem_falha_bloqueante(resultados_dq):
            msg = "Execução bloqueada pelo Quality Gate (regra BLOQUEANTE reprovada)."
            finalizar_run_log(conn, run_id, "BLOQUEADO_DQ", hash_bronze, linhas_silver, 0, msg)
            raise RuntimeError(msg)

        # 4. Motor de Precificação (MtM vs Curva)
        df_fato = calcular_fato_mtm(df_precos, df_posicoes)

        # 5. Carga Gold (SQLite) -> fecha run_log -> exporta CSVs Power BI
        linhas_gold = carregar_gold(conn, run_id, df_posicoes, df_fato)
        finalizar_run_log(conn, run_id, "SUCESSO", hash_bronze, linhas_silver, linhas_gold, "OK")
        exportar_csvs_gold(conn)

        return {
            "run_id": run_id,
            "status": "SUCESSO",
            "linhas_silver": linhas_silver,
            "linhas_gold": linhas_gold,
            "dq_ok": sum(1 for r in resultados_dq if r.status == "OK"),
            "dq_total": len(resultados_dq),
        }

    except Exception as exc:
        if "BLOQUEADO_DQ" not in str(exc):
            finalizar_run_log(conn, run_id, "ERRO", hash_bronze, linhas_silver, 0, str(exc))
        raise
    finally:
        conn.close()
