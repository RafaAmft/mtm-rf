"""Camadas Bronze (ingestão bruta) e Silver (padronização e tipagem)."""

import hashlib
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd
import requests

from mtm.config import (
    BRONZE_DIR,
    MESES_HISTORICO,
    POSICOES_PATH,
    SAMPLE_PRECOS_PATH,
    SILVER_DIR,
    TESOURO_URL,
    TIPO_TITULO_ALVO,
)

logger = logging.getLogger(__name__)


def _sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()[:16]


def ingerir_bronze(offline: bool = False) -> Tuple[Path, str]:
    """
    Salva o arquivo bruto na camada Bronze e retorna (caminho_arquivo, sha256).
    Se offline=True, usa a amostra versionada em data/sample/.
    """
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    destino = BRONZE_DIR / f"tesouro_raw_{datetime.now().strftime('%Y%m%d')}.csv"

    if offline:
        if not SAMPLE_PRECOS_PATH.exists():
            raise FileNotFoundError(f"Amostra offline não encontrada: {SAMPLE_PRECOS_PATH}")
        shutil.copy2(SAMPLE_PRECOS_PATH, destino)
        logger.info("Bronze carregada via amostra offline: %s", destino.name)
    else:
        logger.info("Baixando CSV oficial do Tesouro Transparente...")
        resp = requests.get(TESOURO_URL, timeout=60)
        resp.raise_for_status()
        destino.write_bytes(resp.content)
        logger.info("Bronze salva (%d bytes): %s", len(resp.content), destino.name)

    return destino, _sha256_arquivo(destino)


def transformar_silver(caminho_bronze: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Limpa, tipa e filtra os dados do Tesouro Direto (LTN, últimos N meses)
    e carrega o cadastro de posições das carteiras de terceiros.
    """
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(caminho_bronze, sep=";", decimal=",", encoding="utf-8")

    # Filtra apenas LTN (Tesouro Prefixado)
    df = df[df["Tipo Titulo"] == TIPO_TITULO_ALVO].copy()

    # Converte datas e taxas (de % para decimal)
    df["data_base"] = pd.to_datetime(df["Data Base"], format="%d/%m/%Y").dt.date
    df["data_vencimento"] = pd.to_datetime(df["Data Vencimento"], format="%d/%m/%Y").dt.date
    df["taxa_mercado"] = pd.to_numeric(df["Taxa Venda Manha"], errors="coerce") / 100.0
    df["pu_publicado"] = pd.to_numeric(df["PU Base Manha"], errors="coerce")

    # Mantém apenas os últimos MESES_HISTORICO meses
    data_max = df["data_base"].max()
    data_corte = (pd.Timestamp(data_max) - pd.DateOffset(months=MESES_HISTORICO)).date()
    df = df[df["data_base"] >= data_corte].copy()

    # Identificador padronizado do título (ex.: LTN_2028-01-01)
    df["codigo_titulo"] = "LTN_" + df["data_vencimento"].astype(str)

    df_precos = (
        df[["data_base", "codigo_titulo", "data_vencimento", "taxa_mercado", "pu_publicado"]]
        .sort_values(["codigo_titulo", "data_base"])
        .reset_index(drop=True)
    )

    # Carrega posições de clientes (carteiras de terceiros)
    df_posicoes = pd.read_csv(POSICOES_PATH, encoding="utf-8")
    df_posicoes["data_compra"] = pd.to_datetime(df_posicoes["data_compra"]).dt.date
    df_posicoes["data_vencimento"] = pd.to_datetime(df_posicoes["data_vencimento"]).dt.date
    df_posicoes["taxa_compra"] = pd.to_numeric(df_posicoes["taxa_compra"], errors="coerce")
    df_posicoes["quantidade"] = pd.to_numeric(df_posicoes["quantidade"], errors="coerce")

    # Salva snapshots Silver
    df_precos.to_csv(SILVER_DIR / "precos_ltn_silver.csv", index=False)
    df_posicoes.to_csv(SILVER_DIR / "posicoes_silver.csv", index=False)

    logger.info(
        "Silver gerada: %d preços (%s a %s) | %d posições",
        len(df_precos),
        df_precos["data_base"].min(),
        df_precos["data_base"].max(),
        len(df_posicoes),
    )
    return df_precos, df_posicoes
