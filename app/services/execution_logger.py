"""
ExecutionLogger Service - Helper para registrar logs estruturados.

Feature 5: Logs Estruturados
"""
from typing import Optional
from app.models.execution_log import ExecutionLog
from app.database import db


class ExecutionLogger:
    """
    Helper para registrar logs estruturados durante execução de workflows.

    Uso:
        logger = ExecutionLogger(execution_id, correlation_id)
        logger.ok('step', 'Documento gerado com sucesso', details_tech='...', step_id='...')
        logger.warn('preflight', 'Template não encontrado, usando padrão')
        logger.error('delivery', 'Falha ao enviar email', 'SMTPException: ...')
    """

    def __init__(self, execution_id: str, correlation_id: str):
        """
        Inicializa logger para uma execução.

        Args:
            execution_id: UUID da execução
            correlation_id: UUID de correlação
        """
        self.execution_id = execution_id
        self.correlation_id = correlation_id

    def ok(
        self,
        domain: str,
        message_human: str,
        details_tech: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        """
        Registra log de sucesso.

        Args:
            domain: 'preflight', 'step', 'delivery', 'signature', etc
            message_human: Mensagem para usuário
            details_tech: Detalhes técnicos (opcional)
            step_id: UUID do step (opcional)
        """
        self._log('ok', domain, message_human, details_tech, step_id)

    def warn(
        self,
        domain: str,
        message_human: str,
        details_tech: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        """
        Registra log de aviso.

        Args:
            domain: 'preflight', 'step', 'delivery', 'signature', etc
            message_human: Mensagem para usuário
            details_tech: Detalhes técnicos (opcional)
            step_id: UUID do step (opcional)
        """
        self._log('warn', domain, message_human, details_tech, step_id)

    def error(
        self,
        domain: str,
        message_human: str,
        details_tech: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        """
        Registra log de erro.

        Args:
            domain: 'preflight', 'step', 'delivery', 'signature', etc
            message_human: Mensagem para usuário
            details_tech: Detalhes técnicos (opcional)
            step_id: UUID do step (opcional)
        """
        self._log('error', domain, message_human, details_tech, step_id)

    def _log(
        self,
        level: str,
        domain: str,
        message_human: str,
        details_tech: Optional[str] = None,
        step_id: Optional[str] = None
    ):
        """
        Método interno para criar e persistir log.

        Args:
            level: 'ok', 'warn', 'error'
            domain: Categoria do log
            message_human: Mensagem para usuário
            details_tech: Detalhes técnicos
            step_id: UUID do step
        """
        log = ExecutionLog.create(
            execution_id=self.execution_id,
            correlation_id=self.correlation_id,
            level=level,
            domain=domain,
            message_human=message_human,
            details_tech=details_tech,
            step_id=step_id
        )

        db.session.add(log)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log to stdout as fallback (não pode falhar)
            print(f"[ExecutionLogger] Failed to persist log: {e}")
            print(f"  execution_id={self.execution_id}")
            print(f"  level={level}, domain={domain}")
            print(f"  message={message_human}")


# === Domains (constantes para uso consistente) ===

class LogDomain:
    """Domínios de log disponíveis"""
    PREFLIGHT = 'preflight'
    STEP = 'step'
    DELIVERY = 'delivery'
    SIGNATURE = 'signature'
    WEBHOOK = 'webhook'
    ENGINE = 'engine'
    TEMPORAL = 'temporal'


# === Helper functions ===

def create_logger(execution_id: str, correlation_id: str) -> ExecutionLogger:
    """
    Factory function para criar ExecutionLogger.

    Args:
        execution_id: UUID da execução
        correlation_id: UUID de correlação

    Returns:
        ExecutionLogger instance
    """
    return ExecutionLogger(execution_id, correlation_id)
