"""
Advanced Tag Processing System for DocG

This module provides a powerful tag system with:
- Pipe-style transforms: {{value | format:"DD/MM/YYYY"}}
- Mathematical formulas: {{= price * 1.1}}
- Conditionals: {{IF condition}}...{{ELSE}}...{{ENDIF}}
- Loops: {{FOR item IN items}}...{{ENDFOR}}
- Global variables: {{$timestamp}}, {{$date}}

Usage:
    from app.tags import TagProcessor

    processor = TagProcessor(context)
    result = processor.process(template_text)
"""

from app.tags.parser import TagParser
from app.tags.engine.evaluator import TagEvaluator
from app.tags.context.builder import ContextBuilder


class TagProcessor:
    """
    Main entry point for processing tags in text.

    Combines parsing, context building, and evaluation into a single interface.
    """

    def __init__(self, context: dict = None, locale: str = 'pt_BR'):
        """
        Initialize the tag processor.

        Args:
            context: Data context for resolving variables (trigger, step outputs, etc)
            locale: Locale for date/number formatting (default: pt_BR)
        """
        self.context = context or {}
        self.locale = locale
        self.parser = TagParser()
        self.evaluator = None  # Lazy initialization
        self._stats = {
            'tags_found': 0,
            'tags_resolved': 0,
            'tags_failed': 0,
            'loops_expanded': 0,
            'conditionals_evaluated': 0
        }

    def process(self, content):
        """
        Process all tags in the given content.

        Args:
            content: Can be a string, dict, or list. Processes recursively.

        Returns:
            The content with all tags resolved.
        """
        if content is None:
            return None

        if isinstance(content, str):
            return self._process_string(content)
        elif isinstance(content, dict):
            return {k: self.process(v) for k, v in content.items()}
        elif isinstance(content, list):
            return [self.process(item) for item in content]
        else:
            return content

    def _process_string(self, text: str) -> str:
        """Process tags in a string."""
        if not text or '{{' not in text:
            return text

        # Lazy initialize evaluator with context
        if self.evaluator is None:
            self.evaluator = TagEvaluator(self.context, locale=self.locale)

        try:
            # Parse and evaluate
            ast = self.parser.parse(text)
            result = self.evaluator.evaluate(ast)

            # Update stats
            self._stats['tags_found'] += self.parser.get_tag_count()
            self._stats['tags_resolved'] += self.evaluator.get_resolved_count()
            self._stats['loops_expanded'] += self.evaluator.get_loops_count()
            self._stats['conditionals_evaluated'] += self.evaluator.get_conditionals_count()

            return result
        except Exception as e:
            self._stats['tags_failed'] += 1
            # Return original text if processing fails, but log the error
            import logging
            logging.getLogger(__name__).warning(f"Tag processing failed: {e}")
            return text

    def get_stats(self) -> dict:
        """Get processing statistics."""
        return self._stats.copy()

    def extract_tags(self, text: str) -> list:
        """
        Extract all tags from text without processing them.

        Args:
            text: Text containing tags

        Returns:
            List of tag strings found in the text
        """
        return self.parser.extract_tags(text)

    def validate_tags(self, text: str) -> dict:
        """
        Validate tags in text without processing.

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)
        """
        return self.parser.validate(text)


__all__ = [
    'TagProcessor',
    'TagParser',
    'TagEvaluator',
    'ContextBuilder'
]
