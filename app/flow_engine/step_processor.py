"""
Step Processor - Executes individual flow steps (actions and triggers)

Handles:
- Loading pieces and their actions/triggers
- Resolving input parameters
- Executing handlers
- Capturing output
- Error handling
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import traceback
from uuid import uuid4

from app.pieces.base import (
    ExecutionContext,
    ActionResult,
    PieceRegistry,
)
from app.flow_engine.variable_resolver import VariableResolver
from app.models.app_connection import AppConnection
from app.utils.credentials_encryption import decrypt_credentials

logger = logging.getLogger(__name__)


class StepProcessor:
    """
    Processes individual steps in a flow.

    Responsibilities:
    - Resolve input parameters using VariableResolver
    - Load piece and action/trigger
    - Build ExecutionContext
    - Execute handler
    - Handle errors gracefully
    """

    def __init__(self, registry: Optional[PieceRegistry] = None):
        """
        Initialize step processor.

        Args:
            registry: Piece registry (defaults to global singleton)
        """
        from app.pieces.base import registry as global_registry
        self.registry = registry or global_registry

    async def process_action(
        self,
        step_name: str,
        piece_name: str,
        action_name: str,
        input_params: Dict[str, Any],
        resolver: VariableResolver,
        project_id: str,
        connection_id: Optional[str] = None,
        store: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Process an action step.

        Args:
            step_name: Name of step (for logging)
            piece_name: Piece name (e.g., "hubspot")
            action_name: Action name (e.g., "get-contact")
            input_params: Action parameters (may contain {{variables}})
            resolver: Variable resolver
            project_id: Project ID
            connection_id: Optional connection ID for credentials
            store: Optional key-value store

        Returns:
            Tuple of (success, output_data, error_message)
        """
        logger.info(f"Processing action step: {step_name} ({piece_name}.{action_name})")

        try:
            # 1. Get piece
            piece = self.registry.get(piece_name)
            if not piece:
                error_msg = f"Piece not found: {piece_name}"
                logger.error(error_msg)
                return False, None, error_msg

            # 2. Get action
            action = next((a for a in piece.actions if a.name == action_name), None)
            if not action:
                error_msg = f"Action not found: {action_name} in piece {piece_name}"
                logger.error(error_msg)
                return False, None, error_msg

            # 3. Resolve input parameters
            resolved_params = resolver.resolve(input_params)
            logger.debug(f"Resolved params for {step_name}: {resolved_params}")

            # 4. Get credentials if connection_id provided
            credentials = {}
            if connection_id:
                credentials = await self._get_credentials(connection_id)
                if not credentials:
                    logger.warning(f"No credentials found for connection_id: {connection_id}")

            # 5. Build execution context
            ctx = ExecutionContext(
                credentials=credentials,
                store=store or {},
                project_id=project_id,
                trigger_output=resolver.trigger_output,
                steps_output=resolver.steps_output,
            )

            # 6. Execute action handler
            logger.info(f"Executing action handler: {piece_name}.{action_name}")
            result: ActionResult = await action.handler(resolved_params, ctx)

            # 7. Check result
            if result.success:
                logger.info(f"Action succeeded: {step_name}")
                return True, result.data, None
            else:
                error_msg = result.error.get('message', 'Unknown error') if result.error else 'Unknown error'
                logger.error(f"Action failed: {step_name} - {error_msg}")
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Exception in step {step_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, None, error_msg

    async def process_trigger(
        self,
        piece_name: str,
        trigger_name: str,
        input_params: Dict[str, Any],
        project_id: str,
        connection_id: Optional[str] = None,
        store: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Process a trigger step.

        Args:
            piece_name: Piece name (e.g., "webhook")
            trigger_name: Trigger name (e.g., "catch_webhook")
            input_params: Trigger parameters
            project_id: Project ID
            connection_id: Optional connection ID
            store: Optional key-value store

        Returns:
            Tuple of (success, output_data, error_message)
        """
        logger.info(f"Processing trigger: {piece_name}.{trigger_name}")

        try:
            # 1. Get piece
            piece = self.registry.get(piece_name)
            if not piece:
                error_msg = f"Piece not found: {piece_name}"
                logger.error(error_msg)
                return False, None, error_msg

            # 2. Get trigger
            trigger = next((t for t in piece.triggers if t.name == trigger_name), None)
            if not trigger:
                error_msg = f"Trigger not found: {trigger_name} in piece {piece_name}"
                logger.error(error_msg)
                return False, None, error_msg

            # 3. Get credentials if connection_id provided
            credentials = {}
            if connection_id:
                credentials = await self._get_credentials(connection_id)

            # 4. Build execution context (no trigger_output yet for trigger itself)
            ctx = ExecutionContext(
                credentials=credentials,
                store=store or {},
                project_id=project_id,
                trigger_output=None,  # Triggers don't have trigger_output
                steps_output={},
            )

            # 5. Execute trigger handler
            logger.info(f"Executing trigger handler: {piece_name}.{trigger_name}")
            result: ActionResult = await trigger.handler(input_params, ctx)

            # 6. Check result
            if result.success:
                logger.info(f"Trigger succeeded: {trigger_name}")
                return True, result.data, None
            else:
                error_msg = result.error.get('message', 'Unknown error') if result.error else 'Unknown error'
                logger.error(f"Trigger failed: {trigger_name} - {error_msg}")
                return False, None, error_msg

        except Exception as e:
            error_msg = f"Exception in trigger {trigger_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, None, error_msg

    async def _get_credentials(self, connection_id: str) -> Dict[str, Any]:
        """
        Get decrypted credentials for a connection.

        Args:
            connection_id: Connection UUID

        Returns:
            Decrypted credentials dict
        """
        try:
            from app.database import db

            # Query connection
            connection = db.session.get(AppConnection, connection_id)
            if not connection:
                logger.warning(f"Connection not found: {connection_id}")
                return {}

            # Check status
            if connection.status != 'ACTIVE':
                logger.warning(f"Connection not active: {connection_id} (status: {connection.status})")
                return {}

            # Decrypt credentials
            encrypted_value = connection.value
            credentials = decrypt_credentials(encrypted_value)

            logger.debug(f"Retrieved credentials for connection: {connection_id}")
            return credentials

        except Exception as e:
            logger.error(f"Error getting credentials for {connection_id}: {e}")
            return {}

    def validate_inputs(
        self,
        piece_name: str,
        action_name: str,
        input_params: Dict[str, Any],
        resolver: VariableResolver
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that action inputs are valid.

        Args:
            piece_name: Piece name
            action_name: Action name
            input_params: Input parameters
            resolver: Variable resolver

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get piece and action
        piece = self.registry.get(piece_name)
        if not piece:
            return False, f"Piece not found: {piece_name}"

        action = next((a for a in piece.actions if a.name == action_name), None)
        if not action:
            return False, f"Action not found: {action_name}"

        # Check required properties
        for prop in action.properties:
            if prop.required and prop.name not in input_params:
                return False, f"Required property missing: {prop.name}"

        # Validate variables can be resolved
        unresolved = resolver.validate(input_params)
        if unresolved:
            return False, f"Unresolved variables: {', '.join(unresolved)}"

        return True, None
