"""Configurações centralizadas do pipeline MtM."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SAMPLE_DIR = DATA_DIR / "sample"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"

DB_PATH = GOLD_DIR / "mtm_rf.db"

# Pasta publicada no GitHub Pages: o painel web lê (e oferece para download) os CSVs daqui
SITE_DADOS_DIR = ROOT_DIR / "docs" / "dados"

POSICOES_PATH = SAMPLE_DIR / "posicoes_clientes.csv"
SAMPLE_PRECOS_PATH = SAMPLE_DIR / "precos_tesouro_sample.csv"

TESOURO_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv"
)

# Parâmetros de negócio e qualidade de dados (Data Quality)
TIPO_TITULO_ALVO = "Tesouro Prefixado"  # LTN
VALOR_FACE_LTN = 1000.0
DIAS_UTEIS_ANO = 252
MESES_HISTORICO = 12

# Regras de Data Quality
DQ_TAXA_MIN = 0.0        # 0% a.a.
DQ_TAXA_MAX = 0.50       # 50% a.a.
DQ_REPRICE_TOL = 0.50    # Diferença máxima aceita (R$) entre PU calculado e publicado
