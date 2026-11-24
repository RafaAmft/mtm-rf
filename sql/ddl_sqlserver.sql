-- Modelo Estrela (Camada Gold) em T-SQL (SQL Server)
-- Equivalente ao schema SQLite usado na execução local do pipeline.

CREATE TABLE dbo.etl_run_log (
    run_id        INT IDENTITY(1,1) PRIMARY KEY,
    inicio_utc    DATETIME2      NOT NULL,
    fim_utc       DATETIME2      NULL,
    modo          VARCHAR(20)    NOT NULL,
    hash_bronze   VARCHAR(64)    NULL,
    linhas_silver INT            DEFAULT 0,
    linhas_gold   INT            DEFAULT 0,
    status        VARCHAR(20)    NOT NULL,
    mensagem      NVARCHAR(500)  NULL
);

CREATE TABLE dbo.dq_log (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    run_id          INT           NOT NULL REFERENCES dbo.etl_run_log(run_id),
    regra           VARCHAR(50)   NOT NULL,
    severidade      VARCHAR(20)   NOT NULL,
    status          VARCHAR(10)   NOT NULL,
    linhas_afetadas INT           NOT NULL,
    detalhe         NVARCHAR(300) NULL
);

CREATE TABLE dbo.dim_carteira (
    codigo_carteira VARCHAR(30)   PRIMARY KEY,
    nome_carteira   NVARCHAR(120) NOT NULL,
    tipo_cliente    VARCHAR(40)   NOT NULL
);

CREATE TABLE dbo.dim_titulo (
    codigo_titulo   VARCHAR(30) PRIMARY KEY,
    tipo_titulo     VARCHAR(20) NOT NULL,
    indexador       VARCHAR(20) NOT NULL,
    data_vencimento DATE        NOT NULL
);

CREATE TABLE dbo.fato_posicao_mtm (
    data_base       DATE          NOT NULL,
    codigo_carteira VARCHAR(30)   NOT NULL REFERENCES dbo.dim_carteira(codigo_carteira),
    codigo_titulo   VARCHAR(30)   NOT NULL REFERENCES dbo.dim_titulo(codigo_titulo),
    quantidade      DECIMAL(18,4) NOT NULL,
    taxa_compra     DECIMAL(10,6) NOT NULL,
    taxa_mercado    DECIMAL(10,6) NOT NULL,
    dias_uteis      INT           NOT NULL,
    pu_curva        DECIMAL(18,2) NOT NULL,
    pu_mtm          DECIMAL(18,2) NOT NULL,
    valor_curva     DECIMAL(18,2) NOT NULL,
    valor_mtm       DECIMAL(18,2) NOT NULL,
    agio_desagio    DECIMAL(18,2) NOT NULL,
    pnl_dia         DECIMAL(18,2) NOT NULL,
    duration_mod    DECIMAL(10,4) NOT NULL,
    dv01            DECIMAL(18,2) NOT NULL,
    run_id          INT           NOT NULL REFERENCES dbo.etl_run_log(run_id),
    CONSTRAINT pk_fato_posicao_mtm PRIMARY KEY (data_base, codigo_carteira, codigo_titulo)
);
