"""
Worker Temporal - Executa workflows e activities.

Para executar:
    python -m app.temporal.worker

Ou via módulo:
    from app.temporal.worker import run_worker
    asyncio.run(run_worker())
"""
import asyncio
import logging
import os
import sys
from typing import Optional

from temporalio.client import Client
from temporalio.worker import Worker

from .config import get_config
from .workflows import DocGWorkflow
from .workflows.flow_workflow import FlowWorkflow
from .activities import ALL_ACTIVITIES
from .activities import flow_activities

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_worker(app=None):
    """
    Inicia o worker Temporal.
    
    Args:
        app: Flask app (opcional, para contexto)
    """
    config = get_config()
    
    logger.info(f"Conectando ao Temporal Server: {config.address}")
    logger.info(f"Namespace: {config.namespace}")
    logger.info(f"Task Queue: {config.task_queue}")
    
    # Conectar ao Temporal
    client = await Client.connect(
        config.address,
        namespace=config.namespace
    )
    
    logger.info("Conexão estabelecida com sucesso!")
    
    # Se não temos app, criar um para contexto do Flask
    if app is None:
        from app import create_app
        app = create_app()
    
    # Criar worker com contexto do Flask
    async with Worker(
        client,
        task_queue=config.task_queue,
        workflows=[DocGWorkflow, FlowWorkflow],
        activities=ALL_ACTIVITIES,
    ):
        logger.info(f"Worker iniciado na task queue: {config.task_queue}")
        logger.info(f"Workflows registrados: DocGWorkflow, FlowWorkflow")
        logger.info(f"Activities registradas: {len(ALL_ACTIVITIES)}")
        
        # Manter worker rodando
        await asyncio.Future()


def main():
    """Entry point para execução via CLI"""
    # Adicionar diretório raiz ao path
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()
    
    # Criar app Flask para contexto
    from app import create_app
    app = create_app()
    
    # Rodar worker dentro do contexto Flask
    with app.app_context():
        try:
            asyncio.run(run_worker(app))
        except KeyboardInterrupt:
            logger.info("Worker interrompido pelo usuário")
        except Exception as e:
            logger.exception(f"Erro no worker: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()

