# Dicionário de Dados — Camada Gold (`mtm_rf.db`)

## 1. `fato_posicao_mtm`
**Grão:** 1 linha por `data_base` × `codigo_carteira` × `codigo_titulo`.

| Campo | Tipo | Descrição | Regra / Fórmula |
|---|---|---|---|
| `data_base` | DATE | Data de referência da precificação | Dia útil (calendário ANBIMA) |
| `codigo_carteira` | VARCHAR | Chave da carteira de terceiro | FK → `dim_carteira` |
| `codigo_titulo` | VARCHAR | Identificador do título (`LTN_YYYY-MM-DD`) | FK → `dim_titulo` |
| `quantidade` | DECIMAL | Quantidade de títulos em custódia | ≥ 0 |
| `taxa_compra` | DECIMAL | Taxa contratada na aquisição (decimal a.a.) | Ex.: `0.1420` = 14,20% a.a. |
| `taxa_mercado` | DECIMAL | Taxa de mercado do dia (Tesouro Direto) | `Taxa Venda Manha / 100` |
| `dias_uteis` | INT | Dias úteis entre `data_base` e vencimento | Calendário ANBIMA |
| `pu_curva` | DECIMAL | Preço Unitário na curva (taxa de compra) | `1000 / (1 + taxa_compra)^(du/252)` |
| `pu_mtm` | DECIMAL | Preço Unitário a mercado (taxa do dia) | `1000 / (1 + taxa_mercado)^(du/252)` |
| `valor_curva` | DECIMAL | Posição na curva (`pu_curva × quantidade`) | Semiaditivo (não somar no tempo) |
| `valor_mtm` | DECIMAL | Posição a mercado (`pu_mtm × quantidade`) | Semiaditivo (não somar no tempo) |
| `agio_desagio` | DECIMAL | Diferença `valor_mtm − valor_curva` | Ganho/perda não realizada |
| `pnl_dia` | DECIMAL | Variação diária do `valor_mtm` | Aditivo no tempo |
| `duration_mod` | DECIMAL | Sensibilidade do preço à taxa (anos) | `(du/252) / (1 + taxa_mercado)` |
| `dv01` | DECIMAL | Impacto em R$ na posição para +1 bp (0,01%) | `duration_mod × pu_mtm × 0,0001 × qtd` |
| `run_id` | INT | Identificador da execução que gravou a linha | FK → `etl_run_log` (linhagem) |

## 2. Dimensões e Governança
- **`dim_carteira`**: cadastro de carteiras de terceiros (`codigo_carteira`, `nome_carteira`, `tipo_cliente`).
- **`dim_titulo`**: cadastro de títulos (`codigo_titulo`, `tipo_titulo`, `indexador`, `data_vencimento`).
- **`etl_run_log`**: histórico de execuções (horários, modo, hash SHA-256 da Bronze, volumes e status).
- **`dq_log`**: resultado detalhado das 4 regras de Data Quality por `run_id`.

## 3. Views Analíticas (Power BI)
- **`vw_resumo_carteira`**: consolida por `data_base` e carteira o `pl_curva`, `pl_mtm`, `agio_desagio_total`, `pnl_dia_total`, `duration_ponderada` e `dv01_total`.
- **`vw_qualidade_dados`**: junta `dq_log` + `etl_run_log` para monitoramento de governança.
