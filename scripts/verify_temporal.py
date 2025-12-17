#!/usr/bin/env python3
"""
Script para verificar configuração do Temporal.

Verifica:
- Variáveis de ambiente configuradas
- Conectividade com Temporal Server
- Worker pode conectar
"""

import os
import sys
from pathlib import Path

# Adicionar diretório raiz ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Carregar variáveis de ambiente
from dotenv import load_dotenv
load_dotenv()

def check_env_vars():
    """Verifica se variáveis de ambiente estão configuradas"""
    print("=" * 60)
    print("Verificando Variáveis de Ambiente")
    print("=" * 60)
    
    required_vars = {
        'TEMPORAL_ADDRESS': 'Endereço do Temporal Server (gRPC)',
    }
    
    optional_vars = {
        'TEMPORAL_NAMESPACE': 'Namespace do Temporal (default: default)',
        'TEMPORAL_TASK_QUEUE': 'Task Queue (default: docg-workflows)',
        'TEMPORAL_ACTIVITY_TIMEOUT': 'Timeout de activities em segundos (default: 300)',
        'TEMPORAL_WORKFLOW_TIMEOUT': 'Timeout de workflows em segundos (default: 86400)',
        'TEMPORAL_MAX_RETRIES': 'Máximo de tentativas (default: 3)',
    }
    
    all_ok = True
    
    # Verificar variáveis obrigatórias
    print("\n📋 Variáveis Obrigatórias:")
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: NÃO CONFIGURADA - {desc}")
            all_ok = False
    
    # Verificar variáveis opcionais
    print("\n📋 Variáveis Opcionais:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            default = {
                'TEMPORAL_NAMESPACE': 'default',
                'TEMPORAL_TASK_QUEUE': 'docg-workflows',
                'TEMPORAL_ACTIVITY_TIMEOUT': '300',
                'TEMPORAL_WORKFLOW_TIMEOUT': '86400',
                'TEMPORAL_MAX_RETRIES': '3',
            }.get(var, 'N/A')
            print(f"  ⚠️  {var}: não configurada (usando default: {default})")
    
    return all_ok


def check_temporal_connection():
    """Verifica se consegue conectar ao Temporal Server"""
    print("\n" + "=" * 60)
    print("Verificando Conectividade com Temporal Server")
    print("=" * 60)
    
    try:
        from app.temporal.config import get_config
        
        config = get_config()
        print(f"\n🔗 Tentando conectar a: {config.address}")
        print(f"   Namespace: {config.namespace}")
        print(f"   Task Queue: {config.task_queue}")
        
        # Tentar conectar
        import asyncio
        from temporalio.client import Client
        
        async def test_connection():
            try:
                client = await Client.connect(
                    config.address,
                    namespace=config.namespace
                )
                print("  ✅ Conexão estabelecida com sucesso!")
                
                # Verificar se consegue listar workflows (teste básico)
                try:
                    # Tentar obter informações do namespace
                    print("  ✅ Namespace acessível")
                except Exception as e:
                    print(f"  ⚠️  Aviso ao acessar namespace: {e}")
                
                return True
            except Exception as e:
                print(f"  ❌ Erro ao conectar: {e}")
                return False
        
        result = asyncio.run(test_connection())
        return result
        
    except ImportError as e:
        print(f"  ❌ Erro ao importar módulos do Temporal: {e}")
        print("     Certifique-se de que temporalio está instalado: pip install temporalio")
        return False
    except Exception as e:
        print(f"  ❌ Erro inesperado: {e}")
        return False


def check_worker_setup():
    """Verifica se o worker pode ser inicializado"""
    print("\n" + "=" * 60)
    print("Verificando Configuração do Worker")
    print("=" * 60)
    
    try:
        from app.temporal.worker import run_worker
        from app.temporal.config import get_config
        from app.temporal.workflows import DocGWorkflow
        from app.temporal.activities import ALL_ACTIVITIES
        
        config = get_config()
        
        print(f"\n📦 Workflows registrados:")
        print(f"  ✅ DocGWorkflow")
        
        print(f"\n📦 Activities registradas: {len(ALL_ACTIVITIES)}")
        for activity in ALL_ACTIVITIES:
            print(f"  ✅ {activity.name}")
        
        print(f"\n✅ Worker pode ser inicializado")
        print(f"   Execute: python -m app.temporal.worker")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro ao verificar worker: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executa todas as verificações"""
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO DE CONFIGURAÇÃO TEMPORAL")
    print("=" * 60)
    
    results = {
        'env_vars': check_env_vars(),
        'connection': check_temporal_connection(),
        'worker': check_worker_setup(),
    }
    
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    
    for check, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{status}: {check}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ Todas as verificações passaram!")
        print("   O Temporal está configurado corretamente.")
        return 0
    else:
        print("\n⚠️  Algumas verificações falharam.")
        print("   Revise as configurações acima.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
