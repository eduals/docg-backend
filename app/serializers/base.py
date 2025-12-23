"""
Base Serializer - Classe base para todos os serializers.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime

T = TypeVar('T')


class BaseSerializer:
    """
    Classe base para serializers.

    Define interface comum e helpers para transformar
    objetos do banco em dicionários JSON.
    """

    # Campos a serem incluídos na serialização
    fields: List[str] = []

    # Campos a serem excluídos
    exclude: List[str] = []

    # Campos que são relacionamentos
    relations: Dict[str, Type['BaseSerializer']] = {}

    def __init__(self, instance: Any = None, many: bool = False):
        """
        Inicializa serializer.

        Args:
            instance: Objeto ou lista de objetos a serializar
            many: Se True, instance é uma lista
        """
        self.instance = instance
        self.many = many

    def serialize(self) -> Dict[str, Any] | List[Dict[str, Any]]:
        """
        Serializa a instância.

        Returns:
            Dict ou lista de dicts
        """
        if self.instance is None:
            return {} if not self.many else []

        if self.many:
            return [self._serialize_one(item) for item in self.instance]

        return self._serialize_one(self.instance)

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """
        Serializa um único objeto.

        Args:
            instance: Objeto a serializar

        Returns:
            Dict serializado
        """
        result = {}

        # Usar campos definidos ou todos os atributos
        fields_to_use = self.fields if self.fields else self._get_model_fields(instance)

        for field in fields_to_use:
            if field in self.exclude:
                continue

            value = getattr(instance, field, None)

            # Serializar relacionamentos
            if field in self.relations and value is not None:
                serializer_class = self.relations[field]
                is_list = isinstance(value, (list, tuple))
                serializer = serializer_class(value, many=is_list)
                result[field] = serializer.serialize()
            else:
                result[field] = self._serialize_value(value)

        return result

    def _serialize_value(self, value: Any) -> Any:
        """
        Serializa um valor individual.

        Args:
            value: Valor a serializar

        Returns:
            Valor serializado
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.isoformat()

        if hasattr(value, 'id'):
            # UUID ou ID
            return str(value)

        if isinstance(value, (dict, list, str, int, float, bool)):
            return value

        return str(value)

    def _get_model_fields(self, instance: Any) -> List[str]:
        """
        Obtém campos do model.

        Args:
            instance: Instância do model

        Returns:
            Lista de nomes de campos
        """
        if hasattr(instance, '__table__'):
            return [c.name for c in instance.__table__.columns]
        return []

    @classmethod
    def to_dict(cls, instance: Any, **kwargs) -> Dict[str, Any]:
        """
        Atalho para serializar um objeto.

        Args:
            instance: Objeto a serializar
            **kwargs: Opções adicionais

        Returns:
            Dict serializado
        """
        serializer = cls(instance, **kwargs)
        return serializer.serialize()

    @classmethod
    def to_list(cls, instances: List[Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Atalho para serializar uma lista.

        Args:
            instances: Lista de objetos
            **kwargs: Opções adicionais

        Returns:
            Lista de dicts serializados
        """
        serializer = cls(instances, many=True, **kwargs)
        return serializer.serialize()
