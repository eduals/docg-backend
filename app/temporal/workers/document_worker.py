"""
Document Worker - Worker para geração de documentos.

Processa:
- Google Docs
- Google Slides
- Microsoft Word
- Microsoft PowerPoint
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import get_config
from ..queues import DOCUMENT_QUEUE
from ..activities.document import execute_document_node

logger = logging.getLogger(__name__)

# Activities do Document Worker
DOCUMENT_ACTIVITIES = [
    execute_document_node,
]


async def run_document_worker(client: Client, app=None):
    """
    Inicia o Document Worker.

    Args:
        client: Cliente Temporal conectado
        app: Flask app para contexto
    """
    logger.info(f"Iniciando Document Worker na queue: {DOCUMENT_QUEUE}")

    async with Worker(
        client,
        task_queue=DOCUMENT_QUEUE,
        activities=DOCUMENT_ACTIVITIES,
    ):
        logger.info(f"Document Worker iniciado")
        logger.info(f"  Queue: {DOCUMENT_QUEUE}")
        logger.info(f"  Activities: {len(DOCUMENT_ACTIVITIES)}")

        # Manter worker rodando
        await asyncio.Future()


async def run_standalone(app=None):
    """Executa o worker standalone"""
    config = get_config()

    logger.info(f"Conectando ao Temporal Server: {config.address}")
    client = await Client.connect(
        config.address,
        namespace=config.namespace
    )

    await run_document_worker(client, app)


def main():
    """Entry point para execução via CLI"""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    from dotenv import load_dotenv
    load_dotenv()

    from app import create_app
    app = create_app()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    with app.app_context():
        try:
            asyncio.run(run_standalone(app))
        except KeyboardInterrupt:
            logger.info("Document Worker interrompido pelo usuário")
        except Exception as e:
            logger.exception(f"Erro no Document Worker: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
