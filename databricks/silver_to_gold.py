# Databricks notebook source
# MAGIC %md
# MAGIC # MtM Renda Fixa (LTN) — Camada Silver -> Gold (PySpark + Delta Lake)
# MAGIC
# MAGIC Reproduz a lógica de precificação (Valor na Curva vs. Marcação a Mercado)
# MAGIC usando **PySpark** e carga idempotente via `MERGE INTO` em tabelas **Delta**.

# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from delta.tables import DeltaTable

# Caminhos de exemplo no Unity Catalog / DBFS
SILVER_PRECOS_PATH = "/mnt/mtm_rf/silver/precos_ltn"
SILVER_POSICOES_PATH = "/mnt/mtm_rf/silver/posicoes_clientes"
GOLD_TABLE = "gold.fato_posicao_mtm"

VALOR_FACE = 1000.0
DIAS_UTEIS_ANO = 252.0

# COMMAND ----------
# 1. Leitura da camada Silver
df_precos = spark.read.format("delta").load(SILVER_PRECOS_PATH)
df_posicoes = spark.read.format("delta").load(SILVER_POSICOES_PATH)

# 2. Join (broadcast na tabela pequena de posições evita shuffle)
df_base = (
    df_precos.join(F.broadcast(df_posicoes), on="codigo_titulo", how="inner")
    .filter(F.col("data_base") >= F.col("data_compra"))
)

# 3. Precificação LTN (assumindo dias_uteis já enriquecido na Silver via calendário ANBIMA)
df_calc = (
    df_base
    .withColumn(
        "pu_curva",
        F.round(VALOR_FACE / F.pow(1.0 + F.col("taxa_compra"), F.col("dias_uteis") / DIAS_UTEIS_ANO), 2),
    )
    .withColumn(
        "pu_mtm",
        F.round(VALOR_FACE / F.pow(1.0 + F.col("taxa_mercado"), F.col("dias_uteis") / DIAS_UTEIS_ANO), 2),
    )
    .withColumn("valor_curva", F.round(F.col("pu_curva") * F.col("quantidade"), 2))
    .withColumn("valor_mtm", F.round(F.col("pu_mtm") * F.col("quantidade"), 2))
    .withColumn("agio_desagio", F.round(F.col("valor_mtm") - F.col("valor_curva"), 2))
    .withColumn("duration_mod", F.round((F.col("dias_uteis") / DIAS_UTEIS_ANO) / (1.0 + F.col("taxa_mercado")), 4))
    .withColumn("dv01", F.round(F.col("duration_mod") * F.col("pu_mtm") * 0.0001 * F.col("quantidade"), 2))
)

# 4. P&L diário com Window Function (LAG)
w = Window.partitionBy("codigo_carteira", "codigo_titulo").orderBy("data_base")
df_gold = df_calc.withColumn(
    "pnl_dia",
    F.round(F.coalesce(F.col("valor_mtm") - F.lag("valor_mtm").over(w), F.lit(0.0)), 2),
)

# COMMAND ----------
# 5. Carga idempotente (UPSERT) em Delta Lake
if spark.catalog.tableExists(GOLD_TABLE):
    delta_target = DeltaTable.forName(spark, GOLD_TABLE)
    (
        delta_target.alias("tgt")
        .merge(
            df_gold.alias("src"),
            "tgt.data_base = src.data_base "
            "AND tgt.codigo_carteira = src.codigo_carteira "
            "AND tgt.codigo_titulo = src.codigo_titulo",
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
else:
    df_gold.write.format("delta").mode("overwrite").saveAsTable(GOLD_TABLE)
