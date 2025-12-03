"""
Serviço de telemetria para monitoramento e métricas.
"""

import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Serviço para enviar métricas e eventos de telemetria.
    Suporta múltiplos providers (Honeycomb, Sentry, etc.)
    """
    
    def __init__(self):
        self.enabled = os.getenv('TELEMETRY_ENABLED', 'true').lower() == 'true'
        self.provider = os.getenv('TELEMETRY_PROVIDER', 'log')  # log, honeycomb, sentry
        self.api_key = os.getenv('HONEYCOMB_API_KEY')
        self.dataset = os.getenv('HONEYCOMB_DATASET', 'docugen')
        
    def track_event(self, event_name: str, properties: Dict[str, Any], 
                   severity: str = 'info'):
        """
        Envia um evento de telemetria.
        
        Args:
            event_name: Nome do evento
            properties: Propriedades/atributos do evento
            severity: Nível de severidade (debug, info, warning, error)
        """
        if not self.enabled:
            return
        
        event_data = {
            'event': event_name,
            'timestamp': datetime.utcnow().isoformat(),
            'severity': severity,
            **properties
        }
        
        if self.provider == 'honeycomb' and self.api_key:
            self._send_to_honeycomb(event_data)
        elif self.provider == 'sentry':
            self._send_to_sentry(event_name, properties)
        else:
            # Fallback para log
            log_func = getattr(logger, severity, logger.info)
            log_func(f"Telemetry: {event_name}", extra=properties)
    
    def _send_to_honeycomb(self, event_data: Dict[str, Any]):
        """Envia evento para Honeycomb."""
        try:
            import requests
            response = requests.post(
                f'https://api.honeycomb.io/1/events/{self.dataset}',
                headers={
                    'X-Honeycomb-Team': self.api_key,
                    'Content-Type': 'application/json'
                },
                json=event_data,
                timeout=5
            )
            if response.status_code != 200:
                logger.warning(f'Erro ao enviar para Honeycomb: {response.status_code}')
        except Exception as e:
            logger.warning(f'Erro ao enviar telemetria para Honeycomb: {str(e)}')
    
    def _send_to_sentry(self, event_name: str, properties: Dict[str, Any]):
        """Envia evento para Sentry."""
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                for key, value in properties.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_message(event_name)
        except Exception as e:
            logger.warning(f'Erro ao enviar telemetria para Sentry: {str(e)}')
    
    def track_workflow_execution(self, workflow_id: str, object_type: str, 
                                object_id: str, execution_time: float, 
                                status: str, error: Optional[str] = None):
        """
        Rastreia execução de workflow.
        """
        self.track_event('workflow_executed', {
            'workflow_id': workflow_id,
            'object_type': object_type,
            'object_id': object_id,
            'execution_time_ms': int(execution_time * 1000),
            'status': status,
            'error': error
        }, severity='error' if status == 'error' else 'info')
    
    def track_document_generation(self, document_id: str, template_id: str,
                                  workflow_id: str, generation_time: float,
                                  format: str = 'docx', status: str = 'success'):
        """
        Rastreia geração de documento.
        """
        self.track_event('document_generated', {
            'document_id': document_id,
            'template_id': template_id,
            'workflow_id': workflow_id,
            'generation_time_ms': int(generation_time * 1000),
            'format': format,
            'status': status
        })
    
    def track_api_request(self, endpoint: str, method: str, status_code: int,
                         duration: float, user_id: Optional[str] = None,
                         organization_id: Optional[str] = None):
        """
        Rastreia requisição de API.
        """
        self.track_event('api_request', {
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'duration_ms': int(duration * 1000),
            'user_id': user_id,
            'organization_id': organization_id
        })
    
    def track_error(self, error_type: str, error_message: str,
                   workflow_id: Optional[str] = None,
                   object_id: Optional[str] = None,
                   stack_trace: Optional[str] = None):
        """
        Rastreia erro.
        """
        self.track_event('error_occurred', {
            'error_type': error_type,
            'error_message': error_message,
            'workflow_id': workflow_id,
            'object_id': object_id,
            'stack_trace': stack_trace
        }, severity='error')
    
    def track_hubspot_event(self, event_type: str, object_type: str,
                           object_id: str, success: bool,
                           error: Optional[str] = None):
        """
        Rastreia evento do HubSpot (timeline, etc.).
        """
        self.track_event('hubspot_event', {
            'hubspot_event_type': event_type,
            'object_type': object_type,
            'object_id': object_id,
            'success': success,
            'error': error
        }, severity='error' if not success else 'info')
    
    def track_integration(self, integration: str, action: str,
                         success: bool, error: Optional[str] = None):
        """
        Rastreia ação de integração (Google Drive, ClickSign, etc.).
        """
        self.track_event('integration_action', {
            'integration': integration,
            'action': action,
            'success': success,
            'error': error
        }, severity='error' if not success else 'info')


# Instância global do serviço de telemetria
telemetry = TelemetryService()

