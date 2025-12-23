"""
Webhook Worker - Worker para chamadas HTTP externas.

Processa:
- Webhooks de saída
- HTTP requests customizados
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import get_config
from ..queues import WEBHOOK_QUEUE
from ..activities.webhook import execute_webhook_node

logger = logging.getLogger(__name__)

# Activities do Webhook Worker
WEBHOOK_ACTIVITIES = [
    execute_webhook_node,
]


async def run_webhook_worker(client: Client, app=None):
    """
    Inicia o Webhook Worker.

    Args:
        client: Cliente Temporal conectado
        app: Flask app para contexto
    """
    logger.info(f"Iniciando Webhook Worker na queue: {WEBHOOK_QUEUE}")

    async with Worker(
        client,
        task_queue=WEBHOOK_QUEUE,
        activities=WEBHOOK_ACTIVITIES,
    ):
        logger.info(f"Webhook Worker iniciado")
        logger.info(f"  Queue: {WEBHOOK_QUEUE}")
        logger.info(f"  Activities: {len(WEBHOOK_ACTIVITIES)}")

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

    await run_webhook_worker(client, app)


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
            logger.info("Webhook Worker interrompido pelo usuário")
        except Exception as e:
            logger.exception(f"Erro no Webhook Worker: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
