"""Interface de linha de comando: python -m mtm run [--offline]."""

import argparse
import logging
import sys

from mtm.pipeline import executar_pipeline


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Motor de Marcação a Mercado (MtM) - Renda Fixa")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_run = sub.add_parser("run", help="Executa o pipeline completo (Bronze -> Silver -> Gold)")
    p_run.add_argument(
        "--offline",
        action="store_true",
        help="Usa a amostra versionada em data/sample/ sem baixar da internet",
    )

    args = parser.parse_args()
    if args.comando == "run":
        resumo = executar_pipeline(offline=args.offline)
        print(
            f"\nPipeline concluído | run_id={resumo['run_id']} | "
            f"silver={resumo['linhas_silver']} | gold={resumo['linhas_gold']} | "
            f"DQ={resumo['dq_ok']}/{resumo['dq_total']} OK"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error("Falha na execução: %s", e)
        sys.exit(1)
