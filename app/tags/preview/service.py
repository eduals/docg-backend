"""
Tag Preview Service

Provides preview functionality to show how tags will be resolved
before actually generating documents.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from app.tags.parser import TagParser
from app.tags.parser.lexer import LexerError
from app.tags.parser.parser import ParseError
from app.tags.parser.ast import (
    DocumentNode,
    TextNode,
    VariableNode,
    GlobalVarNode,
    FormulaNode,
    ConditionalNode,
    LoopNode
)
from app.tags.engine.evaluator import TagEvaluator
from app.tags.context.builder import ContextBuilder


@dataclass
class TagPreview:
    """Preview of a single tag resolution."""
    tag: str                          # Original tag text
    resolved: Any                      # Resolved value
    status: str                        # 'ok', 'warning', 'error'
    message: Optional[str] = None     # Error/warning message
    transform_applied: List[str] = field(default_factory=list)  # Transforms used


@dataclass
class LoopPreview:
    """Preview of a loop tag."""
    tag: str                          # Original FOR tag
    items_count: int                  # Number of items in collection
    sample_data: List[Dict] = field(default_factory=list)  # Sample of items (first 3)
    status: str = 'ok'
    message: Optional[str] = None


@dataclass
class ConditionalPreview:
    """Preview of a conditional tag."""
    tag: str                          # Original IF tag
    condition_result: bool            # Result of condition evaluation
    branch_used: str                  # 'true' or 'false'
    status: str = 'ok'
    message: Optional[str] = None


@dataclass
class PreviewResult:
    """Complete preview result for a template."""
    tags: List[TagPreview] = field(default_factory=list)
    loops: List[LoopPreview] = field(default_factory=list)
    conditionals: List[ConditionalPreview] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    sample_output: str = ""
    stats: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'tags': [
                {
                    'tag': t.tag,
                    'resolved': t.resolved,
                    'status': t.status,
                    'message': t.message,
                    'transforms': t.transform_applied
                }
                for t in self.tags
            ],
            'loops': [
                {
                    'tag': l.tag,
                    'items_count': l.items_count,
                    'sample_data': l.sample_data,
                    'status': l.status,
                    'message': l.message
                }
                for l in self.loops
            ],
            'conditionals': [
                {
                    'tag': c.tag,
                    'condition_result': c.condition_result,
                    'branch_used': c.branch_used,
                    'status': c.status,
                    'message': c.message
                }
                for c in self.conditionals
            ],
            'warnings': self.warnings,
            'errors': self.errors,
            'sample_output': self.sample_output,
            'stats': self.stats
        }

    @property
    def is_valid(self) -> bool:
        """Check if preview has no errors."""
        return len(self.errors) == 0


class TagPreviewService:
    """
    Service for previewing tag resolution.

    Parses templates, resolves tags with provided data, and returns
    a detailed preview of what will be generated.
    """

    def __init__(self, locale: str = 'pt_BR'):
        self.locale = locale
        self.parser = TagParser()
        self.context_builder = ContextBuilder(locale=locale)

    def preview(
        self,
        template_content: str,
        context: Dict[str, Any],
        options: Optional[Dict] = None
    ) -> PreviewResult:
        """
        Generate a preview of how tags in the template will be resolved.

        Args:
            template_content: Template text containing tags
            context: Data context for resolving tags
            options: Preview options (e.g., max_sample_items)

        Returns:
            PreviewResult with detailed tag resolution info
        """
        options = options or {}
        max_sample_items = options.get('max_sample_items', 3)

        result = PreviewResult(
            stats={
                'total_tags': 0,
                'resolved': 0,
                'warnings': 0,
                'errors': 0,
                'loops': 0,
                'conditionals': 0
            }
        )

        # Add locale to context
        context['locale'] = self.locale

        try:
            # Parse the template
            ast = self.parser.parse(template_content)

            # Walk the AST to extract and preview tags
            self._process_node(ast, context, result, max_sample_items)

            # Generate sample output
            try:
                evaluator = TagEvaluator(context, locale=self.locale)
                result.sample_output = evaluator.evaluate(ast)
            except Exception as e:
                result.sample_output = f"[Error generating output: {e}]"

        except LexerError as e:
            result.errors.append(f"Syntax error: {e}")
            result.stats['errors'] += 1
        except ParseError as e:
            result.errors.append(f"Parse error: {e}")
            result.stats['errors'] += 1
        except Exception as e:
            result.errors.append(f"Unexpected error: {e}")
            result.stats['errors'] += 1

        # Update stats
        result.stats['warnings'] = len(result.warnings)
        result.stats['errors'] = len(result.errors)

        return result

    def preview_from_trigger(
        self,
        template_content: str,
        trigger_data: Dict[str, Any],
        trigger_source: str = 'generic',
        workflow_metadata: Optional[Dict] = None,
        previous_steps: Optional[List] = None,
        options: Optional[Dict] = None
    ) -> PreviewResult:
        """
        Generate preview using trigger data that will be normalized.

        This is the main method for previewing in the workflow context.

        Args:
            template_content: Template text
            trigger_data: Raw trigger data (will be normalized)
            trigger_source: Source identifier (e.g., 'hubspot')
            workflow_metadata: Workflow info
            previous_steps: Previous step outputs
            options: Preview options

        Returns:
            PreviewResult
        """
        # Build context with normalization
        context = self.context_builder.build(
            trigger_data=trigger_data,
            trigger_source=trigger_source,
            previous_steps=previous_steps,
            workflow_metadata=workflow_metadata
        )

        return self.preview(template_content, context, options)

    def validate_tags(self, template_content: str) -> Dict:
        """
        Validate tag syntax without resolving.

        Args:
            template_content: Template text

        Returns:
            Dict with 'valid', 'errors', 'tags' (list of found tags)
        """
        errors = []
        tags = []

        try:
            # Extract tags using regex (for listing)
            tag_pattern = r'\{\{[^}]+\}\}'
            tags = re.findall(tag_pattern, template_content)

            # Try to parse (validates syntax)
            self.parser.parse(template_content)

            return {
                'valid': True,
                'errors': [],
                'tags': tags,
                'tag_count': len(tags)
            }

        except (LexerError, ParseError) as e:
            errors.append(str(e))
            return {
                'valid': False,
                'errors': errors,
                'tags': tags,
                'tag_count': len(tags)
            }

    def _process_node(
        self,
        node,
        context: Dict,
        result: PreviewResult,
        max_sample_items: int
    ):
        """Process an AST node to extract preview information."""
        if isinstance(node, DocumentNode):
            for child in node.children:
                self._process_node(child, context, result, max_sample_items)

        elif isinstance(node, TextNode):
            pass  # No preview needed for plain text

        elif isinstance(node, VariableNode):
            self._preview_variable(node, context, result)

        elif isinstance(node, GlobalVarNode):
            self._preview_global_var(node, context, result)

        elif isinstance(node, FormulaNode):
            self._preview_formula(node, context, result)

        elif isinstance(node, ConditionalNode):
            self._preview_conditional(node, context, result, max_sample_items)

        elif isinstance(node, LoopNode):
            self._preview_loop(node, context, result, max_sample_items)

    def _preview_variable(
        self,
        node: VariableNode,
        context: Dict,
        result: PreviewResult
    ):
        """Preview a variable tag."""
        result.stats['total_tags'] += 1

        # Reconstruct tag string
        path_str = '.'.join(node.path)
        if node.index is not None:
            path_str += f'[{node.index}]'

        transforms = [t.name for t in node.transforms]
        if transforms:
            transform_str = ' | '.join(transforms)
            tag_str = f"{{{{{path_str} | {transform_str}}}}}"
        else:
            tag_str = f"{{{{{path_str}}}}}"

        try:
            # Create evaluator for this resolution
            evaluator = TagEvaluator(context, locale=self.locale)
            resolved = evaluator._evaluate_variable(node)

            if resolved is None:
                result.tags.append(TagPreview(
                    tag=tag_str,
                    resolved=None,
                    status='warning',
                    message=f"Path '{path_str}' not found in data",
                    transform_applied=transforms
                ))
                result.warnings.append(f"Tag '{tag_str}' could not be resolved")
                result.stats['warnings'] += 1
            else:
                result.tags.append(TagPreview(
                    tag=tag_str,
                    resolved=resolved,
                    status='ok',
                    transform_applied=transforms
                ))
                result.stats['resolved'] += 1

        except Exception as e:
            result.tags.append(TagPreview(
                tag=tag_str,
                resolved=None,
                status='error',
                message=str(e),
                transform_applied=transforms
            ))
            result.errors.append(f"Error resolving '{tag_str}': {e}")
            result.stats['errors'] += 1

    def _preview_global_var(
        self,
        node: GlobalVarNode,
        context: Dict,
        result: PreviewResult
    ):
        """Preview a global variable tag."""
        result.stats['total_tags'] += 1
        tag_str = f"{{{{${node.name}}}}}"

        try:
            evaluator = TagEvaluator(context, locale=self.locale)
            resolved = evaluator._evaluate_global_var(node)

            if resolved is None:
                result.tags.append(TagPreview(
                    tag=tag_str,
                    resolved=None,
                    status='warning',
                    message=f"Global variable '{node.name}' not found"
                ))
                result.stats['warnings'] += 1
            else:
                result.tags.append(TagPreview(
                    tag=tag_str,
                    resolved=resolved,
                    status='ok'
                ))
                result.stats['resolved'] += 1

        except Exception as e:
            result.tags.append(TagPreview(
                tag=tag_str,
                resolved=None,
                status='error',
                message=str(e)
            ))
            result.stats['errors'] += 1

    def _preview_formula(
        self,
        node: FormulaNode,
        context: Dict,
        result: PreviewResult
    ):
        """Preview a formula tag."""
        result.stats['total_tags'] += 1
        tag_str = "{{= formula }}"  # Simplified representation

        try:
            evaluator = TagEvaluator(context, locale=self.locale)
            resolved = evaluator._evaluate_formula(node)

            result.tags.append(TagPreview(
                tag=tag_str,
                resolved=resolved,
                status='ok' if not str(resolved).startswith('[Error') else 'error',
                message=str(resolved) if str(resolved).startswith('[Error') else None
            ))

            if str(resolved).startswith('[Error'):
                result.stats['errors'] += 1
            else:
                result.stats['resolved'] += 1

        except Exception as e:
            result.tags.append(TagPreview(
                tag=tag_str,
                resolved=None,
                status='error',
                message=str(e)
            ))
            result.stats['errors'] += 1

    def _preview_conditional(
        self,
        node: ConditionalNode,
        context: Dict,
        result: PreviewResult,
        max_sample_items: int
    ):
        """Preview a conditional block."""
        result.stats['conditionals'] += 1
        tag_str = "{{IF condition}}"

        try:
            evaluator = TagEvaluator(context, locale=self.locale)
            condition_result = evaluator._evaluate_condition(node.condition.expression)

            result.conditionals.append(ConditionalPreview(
                tag=tag_str,
                condition_result=condition_result,
                branch_used='true' if condition_result else 'false',
                status='ok'
            ))

            # Process the branch that will be used
            branch = node.true_branch if condition_result else node.false_branch
            for child in branch:
                self._process_node(child, context, result, max_sample_items)

        except Exception as e:
            result.conditionals.append(ConditionalPreview(
                tag=tag_str,
                condition_result=False,
                branch_used='error',
                status='error',
                message=str(e)
            ))
            result.stats['errors'] += 1

    def _preview_loop(
        self,
        node: LoopNode,
        context: Dict,
        result: PreviewResult,
        max_sample_items: int
    ):
        """Preview a loop block."""
        result.stats['loops'] += 1

        collection_path = '.'.join(node.collection.path)
        tag_str = f"{{{{FOR {node.item_name} IN {collection_path}}}}}"

        try:
            # Resolve collection
            evaluator = TagEvaluator(context, locale=self.locale)
            collection = evaluator._resolve_path(node.collection.path)

            if not isinstance(collection, (list, tuple)):
                result.loops.append(LoopPreview(
                    tag=tag_str,
                    items_count=0,
                    sample_data=[],
                    status='warning',
                    message=f"'{collection_path}' is not a list"
                ))
                result.stats['warnings'] += 1
                return

            items_count = len(collection)
            sample_data = list(collection[:max_sample_items])

            result.loops.append(LoopPreview(
                tag=tag_str,
                items_count=items_count,
                sample_data=sample_data,
                status='ok'
            ))

            # Process body with first item as sample
            if collection:
                sample_context = {
                    **context,
                    node.item_name: collection[0]
                }
                for child in node.body:
                    self._process_node(child, sample_context, result, max_sample_items)

        except Exception as e:
            result.loops.append(LoopPreview(
                tag=tag_str,
                items_count=0,
                sample_data=[],
                status='error',
                message=str(e)
            ))
            result.stats['errors'] += 1
