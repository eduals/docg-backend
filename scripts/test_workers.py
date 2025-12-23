#!/usr/bin/env python
"""
Script de teste para verificar se os workers estão configurados corretamente.

Uso:
    python scripts/test_workers.py
    python scripts/test_workers.py --worker workflow
    python scripts/test_workers.py --check-imports
"""

import sys
import os
import argparse

# Adicionar diretório raiz ao path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


def check_imports():
    """Verifica se todos os imports necessários funcionam"""
    print("=" * 60)
    print("Verificando imports...")
    print("=" * 60)

    errors = []

    # Test Engine imports
    try:
        from app.engine import Engine, GlobalVariable, compute_parameters
        print("✓ app.engine - OK")
    except Exception as e:
        print(f"✗ app.engine - ERRO: {e}")
        errors.append(("app.engine", str(e)))

    # Test Apps imports
    try:
        from app.apps import AppRegistry
        apps = AppRegistry.list_all()
        print(f"✓ app.apps - OK ({len(apps)} apps registrados)")
    except Exception as e:
        print(f"✗ app.apps - ERRO: {e}")
        errors.append(("app.apps", str(e)))

    # Test Temporal imports
    try:
        from app.temporal import get_temporal_client, WORKFLOW_QUEUE, EMAIL_QUEUE
        print("✓ app.temporal - OK")
    except Exception as e:
        print(f"✗ app.temporal - ERRO: {e}")
        errors.append(("app.temporal", str(e)))

    # Test Queues imports
    try:
        from app.temporal.queues import (
            WORKFLOW_QUEUE, EMAIL_QUEUE, DOCUMENT_QUEUE,
            SIGNATURE_QUEUE, WEBHOOK_QUEUE, APPROVAL_QUEUE,
            get_queue_for_node_type
        )
        print("✓ app.temporal.queues - OK")
        print(f"  - WORKFLOW_QUEUE: {WORKFLOW_QUEUE}")
        print(f"  - EMAIL_QUEUE: {EMAIL_QUEUE}")
        print(f"  - DOCUMENT_QUEUE: {DOCUMENT_QUEUE}")
    except Exception as e:
        print(f"✗ app.temporal.queues - ERRO: {e}")
        errors.append(("app.temporal.queues", str(e)))

    # Test Workers imports
    try:
        from app.temporal.workers import run_all_workers
        from app.temporal.workers.workflow_worker import run_workflow_worker
        from app.temporal.workers.email_worker import run_email_worker
        from app.temporal.workers.document_worker import run_document_worker
        from app.temporal.workers.signature_worker import run_signature_worker
        from app.temporal.workers.webhook_worker import run_webhook_worker
        from app.temporal.workers.approval_worker import run_approval_worker
        print("✓ app.temporal.workers - OK (6 workers)")
    except Exception as e:
        print(f"✗ app.temporal.workers - ERRO: {e}")
        errors.append(("app.temporal.workers", str(e)))

    # Test Activities imports
    try:
        from app.temporal.activities import (
            ALL_ACTIVITIES,
            create_execution_step,
            apply_compute_parameters,
            with_execution_step
        )
        print(f"✓ app.temporal.activities - OK ({len(ALL_ACTIVITIES)} activities)")
    except Exception as e:
        print(f"✗ app.temporal.activities - ERRO: {e}")
        errors.append(("app.temporal.activities", str(e)))

    # Test Controllers imports
    try:
        from app.controllers.api.v1 import workflows, templates, connections
        print("✓ app.controllers - OK")
    except Exception as e:
        print(f"✗ app.controllers - ERRO: {e}")
        errors.append(("app.controllers", str(e)))

    # Test Serializers imports
    try:
        from app.serializers import (
            WorkflowSerializer, TemplateSerializer, DocumentSerializer,
            ConnectionSerializer, ExecutionSerializer
        )
        print("✓ app.serializers - OK")
    except Exception as e:
        print(f"✗ app.serializers - ERRO: {e}")
        errors.append(("app.serializers", str(e)))

    # Test ExecutionStep model
    try:
        from app.models import ExecutionStep
        print("✓ app.models.ExecutionStep - OK")
    except Exception as e:
        print(f"✗ app.models.ExecutionStep - ERRO: {e}")
        errors.append(("app.models.ExecutionStep", str(e)))

    print()
    print("=" * 60)
    if errors:
        print(f"RESULTADO: {len(errors)} erro(s) encontrado(s)")
        for module, error in errors:
            print(f"  - {module}: {error}")
        return False
    else:
        print("RESULTADO: Todos os imports OK!")
        return True


def test_worker(worker_name: str):
    """Testa configuração de um worker específico"""
    print(f"\nTestando worker: {worker_name}")
    print("-" * 40)

    worker_map = {
        'workflow': ('app.temporal.workers.workflow_worker', 'WORKFLOW_ACTIVITIES'),
        'email': ('app.temporal.workers.email_worker', 'EMAIL_ACTIVITIES'),
        'document': ('app.temporal.workers.document_worker', 'DOCUMENT_ACTIVITIES'),
        'signature': ('app.temporal.workers.signature_worker', 'SIGNATURE_ACTIVITIES'),
        'webhook': ('app.temporal.workers.webhook_worker', 'WEBHOOK_ACTIVITIES'),
        'approval': ('app.temporal.workers.approval_worker', 'APPROVAL_ACTIVITIES'),
    }

    if worker_name not in worker_map:
        print(f"Worker desconhecido: {worker_name}")
        print(f"Workers disponíveis: {', '.join(worker_map.keys())}")
        return False

    module_name, activities_var = worker_map[worker_name]

    try:
        import importlib
        module = importlib.import_module(module_name)

        activities = getattr(module, activities_var, [])
        print(f"✓ Módulo carregado: {module_name}")
        print(f"  Activities: {len(activities)}")
        for act in activities:
            print(f"    - {act.__name__}")

        return True

    except Exception as e:
        print(f"✗ Erro ao carregar {module_name}: {e}")
        return False


def list_apps():
    """Lista todos os apps registrados"""
    print("\nApps Registrados:")
    print("-" * 40)

    try:
        from app.apps import AppRegistry

        for app in AppRegistry.list_all():
            actions = app.get_actions()
            triggers = app.get_triggers()
            print(f"\n{app.name} ({app.key})")
            print(f"  Actions: {len(actions)}")
            for action in actions:
                print(f"    - {action.key}: {action.name}")
            print(f"  Triggers: {len(triggers)}")
            for trigger in triggers:
                print(f"    - {trigger.key}: {trigger.name}")

        return True

    except Exception as e:
        print(f"Erro: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Testa configuração dos workers')
    parser.add_argument('--worker', '-w', help='Nome do worker específico para testar')
    parser.add_argument('--check-imports', '-c', action='store_true', help='Verificar imports')
    parser.add_argument('--list-apps', '-a', action='store_true', help='Listar apps registrados')
    args = parser.parse_args()

    # Carregar variáveis de ambiente
    from dotenv import load_dotenv
    load_dotenv()

    success = True

    if args.check_imports or not args.worker:
        success = check_imports() and success

    if args.worker:
        success = test_worker(args.worker) and success

    if args.list_apps:
        success = list_apps() and success

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
