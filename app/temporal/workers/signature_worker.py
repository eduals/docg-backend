"""
Signature Worker - Worker para serviços de assinatura.

Processa:
- ClickSign
- ZapSign
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import get_config
from ..queues import SIGNATURE_QUEUE
from ..activities.signature import create_signature_request, expire_signature

logger = logging.getLogger(__name__)

# Activities do Signature Worker
SIGNATURE_ACTIVITIES = [
    create_signature_request,
    expire_signature,
]


async def run_signature_worker(client: Client, app=None):
    """
    Inicia o Signature Worker.

    Args:
        client: Cliente Temporal conectado
        app: Flask app para contexto
    """
    logger.info(f"Iniciando Signature Worker na queue: {SIGNATURE_QUEUE}")

    async with Worker(
        client,
        task_queue=SIGNATURE_QUEUE,
        activities=SIGNATURE_ACTIVITIES,
    ):
        logger.info(f"Signature Worker iniciado")
        logger.info(f"  Queue: {SIGNATURE_QUEUE}")
        logger.info(f"  Activities: {len(SIGNATURE_ACTIVITIES)}")

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

    await run_signature_worker(client, app)


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
            logger.info("Signature Worker interrompido pelo usuário")
        except Exception as e:
            logger.exception(f"Erro no Signature Worker: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
