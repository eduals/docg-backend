import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TagProcessor:
    """
    Processa tags no formato {{tag_name}} em templates.
    
    Formatos suportados:
    - {{property_name}} - propriedade simples
    - {{object.property}} - propriedade de objeto relacionado
    - {{line_items}} - marcador para tabela de line items
    - {{=SUM(...)}} - fórmulas (para Sheets)
    - {{ai:tag_name}} - tag de IA para geração de texto via LLM
    """
    
    TAG_PATTERN = r'\{\{([^}]+)\}\}'
    AI_TAG_PATTERN = r'\{\{ai:([^}]+)\}\}'
    
    @classmethod
    def extract_tags(cls, text: str) -> List[str]:
        """Extrai todas as tags de um texto (excluindo tags AI)"""
        matches = re.findall(cls.TAG_PATTERN, text)
        # Filtra tags AI que serão processadas separadamente
        return list(set(m for m in matches if not m.startswith('ai:')))
    
    @classmethod
    def extract_ai_tags(cls, text: str) -> List[str]:
        """
        Extrai todas as tags AI de um texto.
        
        Tags AI têm o formato {{ai:nome_da_tag}}.
        
        Args:
            text: Texto do template
        
        Returns:
            Lista de nomes de tags AI (sem o prefixo 'ai:')
        
        Example:
            >>> TagProcessor.extract_ai_tags("Hello {{ai:intro}} world {{ai:outro}}")
            ['intro', 'outro']
        """
        matches = re.findall(cls.AI_TAG_PATTERN, text)
        return list(set(matches))
    
    @classmethod
    def replace_tags(cls, text: str, data: Dict[str, Any], mappings: Dict[str, str] = None) -> str:
        """
        Substitui tags no texto pelos valores correspondentes.
        
        Args:
            text: Texto com tags {{...}}
            data: Dicionário com os dados
            mappings: Mapeamento opcional de tag -> campo no data
        
        Returns:
            Texto com tags substituídas
        """
        def replace_match(match):
            tag = match.group(1).strip()
            
            # Se tem mapeamento, usa o campo mapeado
            field = mappings.get(tag, tag) if mappings else tag
            
            # Busca o valor (suporta dot notation: "contact.firstname")
            value = cls._get_nested_value(data, field)
            
            if value is None:
                return ''  # ou match.group(0) para manter a tag
            
            return str(value)
        
        return re.sub(cls.TAG_PATTERN, replace_match, text)
    
    @classmethod
    def _get_nested_value(cls, data: Dict, path: str) -> Any:
        """
        Busca valor em dicionário usando dot notation.
        Ex: "contact.firstname" -> data['contact']['firstname']
        """
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            
            if value is None:
                return None
        
        return value
    
    @classmethod
    def apply_transform(cls, value: Any, transform_type: str, config: Dict = None) -> str:
        """
        Aplica transformação ao valor.
        
        Transform types:
        - date_format: Formata data
        - number_format: Formata número
        - currency: Formata como moeda
        - uppercase: Converte para maiúsculas
        - lowercase: Converte para minúsculas
        - capitalize: Primeira letra maiúscula
        """
        if value is None:
            return ''
        
        config = config or {}
        
        if transform_type == 'uppercase':
            return str(value).upper()
        
        elif transform_type == 'lowercase':
            return str(value).lower()
        
        elif transform_type == 'capitalize':
            return str(value).capitalize()
        
        elif transform_type == 'date_format':
            from datetime import datetime
            fmt = config.get('format', '%d/%m/%Y')
            if isinstance(value, str):
                # Tenta parsear ISO format
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.strftime(fmt)
                except:
                    return value
            elif isinstance(value, datetime):
                return value.strftime(fmt)
            return str(value)
        
        elif transform_type == 'number_format':
            try:
                num = float(value)
                decimals = config.get('decimals', 2)
                return f"{num:,.{decimals}f}"
            except:
                return str(value)
        
        elif transform_type == 'currency':
            try:
                num = float(value)
                symbol = config.get('symbol', 'R$')
                decimals = config.get('decimals', 2)
                return f"{symbol} {num:,.{decimals}f}"
            except:
                return str(value)
        
        return str(value)
    
    @classmethod
    def replace_ai_tag(cls, text: str, tag_name: str, value: str) -> str:
        """
        Substitui uma tag AI específica pelo valor gerado.
        
        Args:
            text: Texto do template
            tag_name: Nome da tag AI (sem prefixo 'ai:')
            value: Valor gerado pela IA
        
        Returns:
            Texto com a tag substituída
        """
        pattern = r'\{\{ai:' + re.escape(tag_name) + r'\}\}'
        return re.sub(pattern, value, text)
    
    @classmethod
    def build_ai_prompt(
        cls,
        prompt_template: str,
        source_data: Dict[str, Any],
        source_fields: List[str] = None
    ) -> str:
        """
        Constrói o prompt para a IA baseado no template e dados.
        
        O prompt_template pode conter placeholders {{field}} que serão
        substituídos pelos valores dos campos em source_data.
        
        Args:
            prompt_template: Template do prompt com placeholders
            source_data: Dados da fonte (HubSpot, etc)
            source_fields: Lista opcional de campos a usar (para contexto)
        
        Returns:
            Prompt montado pronto para enviar à IA
        
        Example:
            >>> data = {'dealname': 'Projeto X', 'amount': '50000'}
            >>> template = "Descreva o deal {{dealname}} no valor de {{amount}}"
            >>> TagProcessor.build_ai_prompt(template, data)
            "Descreva o deal Projeto X no valor de 50000"
        """
        if not prompt_template:
            # Prompt padrão se não configurado
            if source_fields:
                fields_text = ', '.join(source_fields)
                return f"Com base nos seguintes dados: {cls._format_source_data(source_data, source_fields)}, gere um texto apropriado."
            return "Gere um texto descritivo."
        
        # Substituir placeholders no template
        return cls.replace_tags(prompt_template, source_data)
    
    @classmethod
    def _format_source_data(cls, data: Dict, fields: List[str] = None) -> str:
        """
        Formata dados para inclusão no prompt.
        
        Args:
            data: Dicionário de dados
            fields: Lista de campos a incluir (None = todos)
        
        Returns:
            String formatada com os dados
        """
        if fields:
            filtered = {}
            for field in fields:
                value = cls._get_nested_value(data, field)
                if value is not None:
                    filtered[field] = value
            data = filtered
        
        parts = []
        for key, value in data.items():
            if value is not None and value != '':
                parts.append(f"{key}: {value}")
        
        return '; '.join(parts) if parts else "Nenhum dado disponível"

