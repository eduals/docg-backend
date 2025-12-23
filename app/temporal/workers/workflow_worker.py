"""
Workflow Worker - Worker principal para execução de workflows.

Processa:
- DocGWorkflow
- Activities base (load, update, complete)
- Trigger activities
"""

import asyncio
import logging
import os
import sys
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from ..config import get_config
from ..queues import WORKFLOW_QUEUE
from ..workflows import DocGWorkflow
from ..activities.base import (
    load_execution,
    update_current_node,
    save_execution_context,
    pause_execution,
    resume_execution,
    complete_execution,
    fail_execution,
    add_execution_log,
)
from ..activities.trigger import execute_trigger_node

logger = logging.getLogger(__name__)

# Activities do Workflow Worker
WORKFLOW_ACTIVITIES = [
    load_execution,
    update_current_node,
    save_execution_context,
    pause_execution,
    resume_execution,
    complete_execution,
    fail_execution,
    add_execution_log,
    execute_trigger_node,
]


async def run_workflow_worker(client: Client, app=None):
    """
    Inicia o Workflow Worker.

    Args:
        client: Cliente Temporal conectado
        app: Flask app para contexto
    """
    logger.info(f"Iniciando Workflow Worker na queue: {WORKFLOW_QUEUE}")

    async with Worker(
        client,
        task_queue=WORKFLOW_QUEUE,
        workflows=[DocGWorkflow],
        activities=WORKFLOW_ACTIVITIES,
    ):
        logger.info(f"Workflow Worker iniciado")
        logger.info(f"  Queue: {WORKFLOW_QUEUE}")
        logger.info(f"  Workflows: DocGWorkflow")
        logger.info(f"  Activities: {len(WORKFLOW_ACTIVITIES)}")

        # Manter worker rodando
        await asyncio.Future()


async def run_standalone(app=None):
    """Executa o worker standalone (para execução individual)"""
    config = get_config()

    logger.info(f"Conectando ao Temporal Server: {config.address}")
    client = await Client.connect(
        config.address,
        namespace=config.namespace
    )

    await run_workflow_worker(client, app)


def main():
    """Entry point para execução via CLI"""
    # Adicionar diretório raiz ao path
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
            logger.info("Workflow Worker interrompido pelo usuário")
        except Exception as e:
            logger.exception(f"Erro no Workflow Worker: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
