"""
Workers Dedicados do Temporal.

Cada worker escuta uma queue específica e processa apenas
as activities relacionadas ao seu domínio.

Uso:
    # Rodar todos os workers
    python -m app.temporal.workers

    # Rodar worker específico
    python -m app.temporal.workers.workflow_worker
    python -m app.temporal.workers.email_worker
    python -m app.temporal.workers.document_worker
    python -m app.temporal.workers.signature_worker
    python -m app.temporal.workers.webhook_worker
"""

import asyncio
import logging
from typing import List, Optional

from temporalio.client import Client

from ..config import get_config

logger = logging.getLogger(__name__)


async def run_all_workers(app=None):
    """
    Inicia todos os workers em paralelo.

    Args:
        app: Flask app para contexto
    """
    from .workflow_worker import run_workflow_worker
    from .email_worker import run_email_worker
    from .document_worker import run_document_worker
    from .signature_worker import run_signature_worker
    from .webhook_worker import run_webhook_worker
    from .approval_worker import run_approval_worker

    config = get_config()

    logger.info(f"Conectando ao Temporal Server: {config.address}")
    logger.info(f"Namespace: {config.namespace}")

    # Conectar ao Temporal
    client = await Client.connect(
        config.address,
        namespace=config.namespace
    )

    logger.info("Conexão estabelecida com sucesso!")

    # Iniciar todos os workers em paralelo
    await asyncio.gather(
        run_workflow_worker(client, app),
        run_email_worker(client, app),
        run_document_worker(client, app),
        run_signature_worker(client, app),
        run_webhook_worker(client, app),
        run_approval_worker(client, app),
    )


def main():
    """Entry point para execução via CLI"""
    import os
    import sys

    # Adicionar diretório raiz ao path
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()

    # Criar app Flask para contexto
    from app import create_app
    app = create_app()

    # Rodar workers dentro do contexto Flask
    with app.app_context():
        try:
            asyncio.run(run_all_workers(app))
        except KeyboardInterrupt:
            logger.info("Workers interrompidos pelo usuário")
        except Exception as e:
            logger.exception(f"Erro nos workers: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
