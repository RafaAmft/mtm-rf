"""Camada Gold: modelo estrela em SQLite + views analíticas + CSVs para Power BI."""

import logging
import sqlite3
from pathlib import Path
from typing import List

import pandas as pd

from mtm.config import DB_PATH, GOLD_DIR
from mtm.quality import ResultadoDQ

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio_utc      TEXT NOT NULL,
    fim_utc         TEXT,
    modo            TEXT NOT NULL,
    hash_bronze     TEXT,
    linhas_silver   INTEGER DEFAULT 0,
    linhas_gold     INTEGER DEFAULT 0,
    status          TEXT NOT NULL,
    mensagem        TEXT
);

CREATE TABLE IF NOT EXISTS dq_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL,
    regra           TEXT NOT NULL,
    severidade      TEXT NOT NULL,
    status          TEXT NOT NULL,
    linhas_afetadas INTEGER NOT NULL,
    detalhe         TEXT,
    FOREIGN KEY (run_id) REFERENCES etl_run_log(run_id)
);

CREATE TABLE IF NOT EXISTS dim_carteira (
    codigo_carteira TEXT PRIMARY KEY,
    nome_carteira   TEXT NOT NULL,
    tipo_cliente    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_titulo (
    codigo_titulo   TEXT PRIMARY KEY,
    tipo_titulo     TEXT NOT NULL,
    indexador       TEXT NOT NULL,
    data_vencimento TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fato_posicao_mtm (
    data_base       TEXT NOT NULL,
    codigo_carteira TEXT NOT NULL,
    codigo_titulo   TEXT NOT NULL,
    quantidade      REAL NOT NULL,
    taxa_compra     REAL NOT NULL,
    taxa_mercado    REAL NOT NULL,
    dias_uteis      INTEGER NOT NULL,
    pu_curva        REAL NOT NULL,
    pu_mtm          REAL NOT NULL,
    valor_curva     REAL NOT NULL,
    valor_mtm       REAL NOT NULL,
    agio_desagio    REAL NOT NULL,
    pnl_dia         REAL NOT NULL,
    duration_mod    REAL NOT NULL,
    dv01            REAL NOT NULL,
    run_id          INTEGER NOT NULL,
    PRIMARY KEY (data_base, codigo_carteira, codigo_titulo),
    FOREIGN KEY (codigo_carteira) REFERENCES dim_carteira(codigo_carteira),
    FOREIGN KEY (codigo_titulo)   REFERENCES dim_titulo(codigo_titulo),
    FOREIGN KEY (run_id)          REFERENCES etl_run_log(run_id)
);

CREATE VIEW IF NOT EXISTS vw_resumo_carteira AS
SELECT
    f.data_base,
    c.codigo_carteira,
    c.nome_carteira,
    c.tipo_cliente,
    ROUND(SUM(f.valor_curva), 2) AS pl_curva,
    ROUND(SUM(f.valor_mtm), 2)   AS pl_mtm,
    ROUND(SUM(f.agio_desagio), 2) AS agio_desagio_total,
    ROUND(SUM(f.pnl_dia), 2)     AS pnl_dia_total,
    ROUND(SUM(f.duration_mod * f.valor_mtm) / NULLIF(SUM(f.valor_mtm), 0), 4) AS duration_ponderada,
    ROUND(SUM(f.dv01), 2)        AS dv01_total
FROM fato_posicao_mtm f
JOIN dim_carteira c ON c.codigo_carteira = f.codigo_carteira
GROUP BY f.data_base, c.codigo_carteira, c.nome_carteira, c.tipo_cliente;

CREATE VIEW IF NOT EXISTS vw_qualidade_dados AS
SELECT
    r.run_id,
    r.inicio_utc,
    r.status AS status_execucao,
    d.regra,
    d.severidade,
    d.status AS status_regra,
    d.linhas_afetadas,
    d.detalhe
FROM dq_log d
JOIN etl_run_log r ON r.run_id = d.run_id;
"""


def conectar(db_path: Path = DB_PATH) -> sqlite3.Connection:
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    return conn


def iniciar_run_log(conn: sqlite3.Connection, modo: str) -> int:
    cur = conn.execute(
        "INSERT INTO etl_run_log (inicio_utc, modo, status) VALUES (datetime('now'), ?, 'EM_EXECUCAO')",
        (modo,),
    )
    conn.commit()
    return int(cur.lastrowid)


def finalizar_run_log(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    hash_bronze: str = "",
    linhas_silver: int = 0,
    linhas_gold: int = 0,
    mensagem: str = "",
) -> None:
    conn.execute(
        """
        UPDATE etl_run_log
        SET fim_utc = datetime('now'),
            hash_bronze = ?,
            linhas_silver = ?,
            linhas_gold = ?,
            status = ?,
            mensagem = ?
        WHERE run_id = ?
        """,
        (hash_bronze, linhas_silver, linhas_gold, status, mensagem, run_id),
    )
    conn.commit()


def salvar_dq_log(conn: sqlite3.Connection, run_id: int, resultados: List[ResultadoDQ]) -> None:
    conn.executemany(
        """
        INSERT INTO dq_log (run_id, regra, severidade, status, linhas_afetadas, detalhe)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (run_id, r.regra, r.severidade, r.status, r.linhas_afetadas, r.detalhe)
            for r in resultados
        ],
    )
    conn.commit()


def carregar_gold(
    conn: sqlite3.Connection,
    run_id: int,
    df_posicoes: pd.DataFrame,
    df_fato: pd.DataFrame,
) -> int:
    """Carrega dimensões e fato de forma idempotente (UPSERT) e exporta CSVs para o Power BI."""
    with conn:
        # dim_carteira
        carteiras = df_posicoes[["codigo_carteira", "nome_carteira", "tipo_cliente"]].drop_duplicates()
        conn.executemany(
            """
            INSERT INTO dim_carteira (codigo_carteira, nome_carteira, tipo_cliente)
            VALUES (?, ?, ?)
            ON CONFLICT(codigo_carteira) DO UPDATE SET
                nome_carteira = excluded.nome_carteira,
                tipo_cliente  = excluded.tipo_cliente
            """,
            carteiras.itertuples(index=False, name=None),
        )

        # dim_titulo
        titulos = df_posicoes[["codigo_titulo", "data_vencimento"]].drop_duplicates()
        conn.executemany(
            """
            INSERT INTO dim_titulo (codigo_titulo, tipo_titulo, indexador, data_vencimento)
            VALUES (?, 'LTN', 'PREFIXADO', ?)
            ON CONFLICT(codigo_titulo) DO UPDATE SET
                data_vencimento = excluded.data_vencimento
            """,
            [(r.codigo_titulo, str(r.data_vencimento)) for r in titulos.itertuples(index=False)],
        )

        # fato_posicao_mtm (UPSERT idempotente)
        registros = [
            (
                str(r.data_base),
                r.codigo_carteira,
                r.codigo_titulo,
                float(r.quantidade),
                float(r.taxa_compra),
                float(r.taxa_mercado),
                int(r.dias_uteis),
                float(r.pu_curva),
                float(r.pu_mtm),
                float(r.valor_curva),
                float(r.valor_mtm),
                float(r.agio_desagio),
                float(r.pnl_dia),
                float(r.duration_mod),
                float(r.dv01),
                run_id,
            )
            for r in df_fato.itertuples(index=False)
        ]
        conn.executemany(
            """
            INSERT INTO fato_posicao_mtm (
                data_base, codigo_carteira, codigo_titulo, quantidade,
                taxa_compra, taxa_mercado, dias_uteis, pu_curva, pu_mtm,
                valor_curva, valor_mtm, agio_desagio, pnl_dia, duration_mod, dv01, run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_base, codigo_carteira, codigo_titulo) DO UPDATE SET
                quantidade   = excluded.quantidade,
                taxa_compra  = excluded.taxa_compra,
                taxa_mercado = excluded.taxa_mercado,
                dias_uteis   = excluded.dias_uteis,
                pu_curva     = excluded.pu_curva,
                pu_mtm       = excluded.pu_mtm,
                valor_curva  = excluded.valor_curva,
                valor_mtm    = excluded.valor_mtm,
                agio_desagio = excluded.agio_desagio,
                pnl_dia      = excluded.pnl_dia,
                duration_mod = excluded.duration_mod,
                dv01         = excluded.dv01,
                run_id       = excluded.run_id
            """,
            registros,
        )

    logger.info("Gold carregada no SQLite (%d linhas)", len(registros))
    return len(registros)


def exportar_csvs_gold(conn: sqlite3.Connection) -> None:
    """Exporta tabelas e views da camada Gold em CSV para consumo no Power BI."""
    for nome in ["dim_carteira", "dim_titulo", "fato_posicao_mtm", "vw_resumo_carteira", "vw_qualidade_dados"]:
        df_exp = pd.read_sql_query(f"SELECT * FROM {nome}", conn)
        df_exp.to_csv(GOLD_DIR / f"{nome}.csv", index=False, encoding="utf-8-sig")
    logger.info("CSVs Gold exportados em %s", GOLD_DIR)
