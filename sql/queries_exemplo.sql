-- Consultas analíticas de exemplo (compatíveis com SQLite e SQL Server)

-- 1. Posição consolidada na data mais recente (PL é semiaditivo: usa o último dia!)
SELECT
    data_base,
    nome_carteira,
    pl_curva,
    pl_mtm,
    agio_desagio_total,
    duration_ponderada,
    dv01_total
FROM vw_resumo_carteira
WHERE data_base = (SELECT MAX(data_base) FROM vw_resumo_carteira)
ORDER BY pl_mtm DESC;

-- 2. Variação diária do PL a mercado por carteira usando LAG()
SELECT
    data_base,
    codigo_carteira,
    pl_mtm,
    ROUND(
        pl_mtm - LAG(pl_mtm) OVER (PARTITION BY codigo_carteira ORDER BY data_base),
        2
    ) AS variacao_pl_dia
FROM vw_resumo_carteira
ORDER BY codigo_carteira, data_base DESC;

-- 3. Histórico de Data Quality da última execução
SELECT
    regra,
    severidade,
    status_regra,
    linhas_afetadas,
    detalhe
FROM vw_qualidade_dados
WHERE run_id = (SELECT MAX(run_id) FROM etl_run_log);
