import logging
from typing import List

import strawberry
from graphql import GraphQLError

from app.graphql.resolvers.query import Query
from app.graphql.resolvers.mutation import Mutation

logger = logging.getLogger("app.graphql.errors")

# ---------------------------------------------------------------------------
# Errores esperados (validación de negocio) cuyos mensajes pueden llegar
# al cliente sin riesgo de exponer internos del sistema.
# ---------------------------------------------------------------------------
_CLIENT_SAFE_EXCEPTIONS = (ValueError, FileNotFoundError, PermissionError)


def _process_errors(errors: List[GraphQLError], execution_context=None) -> List[GraphQLError]:
    """Sanitiza errores GraphQL antes de enviarlos al cliente.

    - Errores de validación conocidos (ValueError, etc.) → mensaje original.
    - Errores internos inesperados → mensaje genérico + log completo server-side.
    """
    sanitized: List[GraphQLError] = []
    for error in errors:
        original = error.original_error
        if original is None:
            # Error de sintaxis o validación de esquema GraphQL → seguro para el cliente
            sanitized.append(error)
        elif isinstance(original, _CLIENT_SAFE_EXCEPTIONS):
            # Error de negocio esperado → pasar mensaje al cliente
            sanitized.append(error)
        else:
            # Error interno inesperado → loguear detalle y devolver mensaje genérico
            logger.error(
                "GraphQL unhandled error [%s]: %s",
                type(original).__name__,
                original,
                exc_info=original,
            )
            sanitized.append(
                GraphQLError(
                    "Error interno del servidor. Por favor contacte al administrador.",
                    locations=error.locations,
                    path=error.path,
                )
            )
    return sanitized


schema = strawberry.Schema(query=Query, mutation=Mutation, process_errors=_process_errors)

