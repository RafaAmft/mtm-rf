# Runbook Operacional — Sustentação do Pipeline `mtm-rf`

## 1. Execução normal (diária)
```bash
PYTHONPATH=src python -m mtm run
```
A execução é **idempotente** (usa `UPSERT` por chave primária). Reexecutar a mesma data não gera duplicatas.

## 2. Cenários de incidente e ação recomendada

| Incidente | Sintoma no Log | Ação |
|---|---|---|
| **Fonte do Tesouro fora do ar** | `status = ERRO` em `etl_run_log` (timeout/HTTP) | 1. Tentar novamente após 15 min.<br>2. Em contingência, rodar com `--offline` usando a última Bronze válida ou fonte secundária definida no Manual de MaM. |
| **Falha bloqueante no Quality Gate** | `status = BLOQUEADO_DQ` | 1. Consultar `SELECT * FROM vw_qualidade_dados ORDER BY run_id DESC;`.<br>2. Identificar a regra (`DQ_UNICIDADE`, `DQ_VALIDADE` ou `DQ_COMPLETUDE`).<br>3. Corrigir na origem ou no cadastro de posições e reprocessar. A camada Gold permanece intacta até a correção. |
| **Alerta de `DQ_REPRICE`** | `status_regra = FALHA` (severidade `ALERTA`) | 1. Verificar se houve feriado novo ou mudança no calendário ANBIMA em `src/mtm/calendario.py`.<br>2. Conferir arredondamento/metodologia do Tesouro. |
| **Novo título adicionado na carteira** | `DQ_COMPLETUDE` falha | Confirmar se o `codigo_titulo` em `posicoes_clientes.csv` segue o padrão `LTN_YYYY-MM-DD` e existe na base do Tesouro. |

## 3. Monitoramento mínimo
- Conferir diariamente na tabela `etl_run_log` se a última linha tem `status = 'SUCESSO'`.
- Conferir na `vw_qualidade_dados` se todas as 4 regras fecharam com `status_regra = 'OK'`.
