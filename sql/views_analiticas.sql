-- Views analíticas prontas para consumo no Power BI (T-SQL / SQL Server)

CREATE OR ALTER VIEW dbo.vw_resumo_carteira AS
SELECT
    f.data_base,
    c.codigo_carteira,
    c.nome_carteira,
    c.tipo_cliente,
    CAST(SUM(f.valor_curva)  AS DECIMAL(18,2)) AS pl_curva,
    CAST(SUM(f.valor_mtm)    AS DECIMAL(18,2)) AS pl_mtm,
    CAST(SUM(f.agio_desagio) AS DECIMAL(18,2)) AS agio_desagio_total,
    CAST(SUM(f.pnl_dia)      AS DECIMAL(18,2)) AS pnl_dia_total,
    CAST(SUM(f.duration_mod * f.valor_mtm) / NULLIF(SUM(f.valor_mtm), 0) AS DECIMAL(10,4)) AS duration_ponderada,
    CAST(SUM(f.dv01)         AS DECIMAL(18,2)) AS dv01_total
FROM dbo.fato_posicao_mtm f
INNER JOIN dbo.dim_carteira c
    ON c.codigo_carteira = f.codigo_carteira
GROUP BY
    f.data_base,
    c.codigo_carteira,
    c.nome_carteira,
    c.tipo_cliente;
GO

CREATE OR ALTER VIEW dbo.vw_qualidade_dados AS
SELECT
    r.run_id,
    r.inicio_utc,
    r.status AS status_execucao,
    d.regra,
    d.severidade,
    d.status AS status_regra,
    d.linhas_afetadas,
    d.detalhe
FROM dbo.dq_log d
INNER JOIN dbo.etl_run_log r
    ON r.run_id = d.run_id;
GO
