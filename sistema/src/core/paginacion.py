"""Paginación del lado del servidor para cualquier consulta de SQLAlchemy.

Un servicio de core arma la consulta, con sus filtros y su orden, y la pagina:

    from src.core.paginacion import Pagina, paginar

    def buscar_algo(..., pagina: int) -> Pagina[Algo]:
        consulta = sa.select(Algo).where(...).order_by(Algo.nombre, Algo.id)
        return paginar(consulta, pagina, por_pagina=20)

La plantilla muestra `pagina.items` y los links con la macro de templates/macros/paginacion.html.
El orden tiene que terminar en una columna única (por ejemplo el id): si no, una fila puede
aparecer en dos páginas.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import sqlalchemy as sa

from src.core.database import db

# Cuántos números de página se muestran a cada lado de la actual (1 … 4 5 [6] 7 8 … 20).
VECINAS = 2


@dataclass(frozen=True)
class Pagina[T]:
    items: Sequence[T]
    # Número de página, desde 1.
    numero: int
    por_pagina: int
    # Filas que cumplen el filtro en todas las páginas.
    total: int

    @property
    def cantidad_de_paginas(self) -> int:
        """Siempre al menos 1, aunque no haya resultados."""
        return max(1, -(-self.total // self.por_pagina))

    @property
    def hay_anterior(self) -> bool:
        return self.numero > 1

    @property
    def hay_siguiente(self) -> bool:
        return self.numero < self.cantidad_de_paginas

    @property
    def desde(self) -> int:
        """Posición de la primera fila de la página, para "21–40 de 53". 0 si no hay filas."""
        return (self.numero - 1) * self.por_pagina + 1 if self.items else 0

    @property
    def hasta(self) -> int:
        return (self.numero - 1) * self.por_pagina + len(self.items)

    @property
    def numeros_visibles(self) -> list[int | None]:
        """Números de página para los links. None marca un salto que se muestra como «…»."""
        ultima = self.cantidad_de_paginas
        cercanas = range(max(1, self.numero - VECINAS), min(ultima, self.numero + VECINAS) + 1)
        numeros = sorted({1, ultima, *cercanas})
        resultado: list[int | None] = []
        for anterior, numero in zip([0, *numeros], numeros, strict=False):
            if numero - anterior > 1:
                resultado.append(None)
            resultado.append(numero)
        return resultado


def paginar[T](consulta: sa.Select[tuple[T]], pagina: int, por_pagina: int) -> Pagina[T]:
    """Ejecuta `consulta` para traer solo la página pedida, y cuenta el total.

    Una página menor que 1 se toma como la primera y una mayor que la última, como la última:
    así un link viejo (por ejemplo, después de cambiar un filtro) no muestra una página vacía.
    """
    if por_pagina < 1:
        raise ValueError("por_pagina tiene que ser al menos 1.")
    conteo = sa.select(sa.func.count()).select_from(consulta.order_by(None).subquery())
    total = db.session.scalar(conteo) or 0
    ultima = max(1, -(-total // por_pagina))
    numero = min(max(pagina, 1), ultima)
    items = db.session.scalars(consulta.limit(por_pagina).offset((numero - 1) * por_pagina))
    return Pagina(list(items), numero, por_pagina, total)
