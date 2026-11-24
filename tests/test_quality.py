from datetime import date

import pandas as pd

from mtm.quality import executar_quality_gate, tem_falha_bloqueante


def _base_valida():
    df_precos = pd.DataFrame(
        [
            {
                "data_base": date(2026, 11, 19),
                "codigo_titulo": "LTN_2032-01-01",
                "data_vencimento": date(2032, 1, 1),
                "taxa_mercado": 0.1555,
                "pu_publicado": 479.64,
            }
        ]
    )
    df_posicoes = pd.DataFrame(
        [
            {
                "codigo_carteira": "CART_01",
                "nome_carteira": "Fundo Teste",
                "tipo_cliente": "Fundo",
                "codigo_titulo": "LTN_2032-01-01",
                "data_vencimento": date(2032, 1, 1),
                "data_compra": date(2026, 1, 1),
                "taxa_compra": 0.15,
                "quantidade": 100,
            }
        ]
    )
    return df_precos, df_posicoes


def test_quality_gate_aprovado():
    df_precos, df_posicoes = _base_valida()
    resultados = executar_quality_gate(df_precos, df_posicoes)
    assert tem_falha_bloqueante(resultados) is False
    assert all(r.status == "OK" for r in resultados)


def test_quality_gate_bloqueia_duplicata():
    df_precos, df_posicoes = _base_valida()
    df_dup = pd.concat([df_precos, df_precos], ignore_index=True)
    resultados = executar_quality_gate(df_dup, df_posicoes)
    assert tem_falha_bloqueante(resultados) is True
    dq_unic = next(r for r in resultados if r.regra == "DQ_UNICIDADE")
    assert dq_unic.status == "FALHA"


def test_quality_gate_bloqueia_taxa_invalida():
    df_precos, df_posicoes = _base_valida()
    df_precos.loc[0, "taxa_mercado"] = 0.99  # 99% a.a. (fora da faixa)
    resultados = executar_quality_gate(df_precos, df_posicoes)
    assert tem_falha_bloqueante(resultados) is True
    dq_val = next(r for r in resultados if r.regra == "DQ_VALIDADE")
    assert dq_val.status == "FALHA"
