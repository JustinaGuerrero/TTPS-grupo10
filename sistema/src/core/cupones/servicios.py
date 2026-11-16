"""Reglas de los cupones de descuento (E37, E38 y la validación de E15).

El módulo de cupones (externo) es el que manda sobre el estado; acá se guarda una copia. Ninguna
función hace commit: lo decide el controlador. El descuento es un porcentaje de 1 a 100 (O15).
"""

import io
import re
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import sqlalchemy as sa

from src.core.cupones.modelos import Cupon, EstadoCupon
from src.core.cupones.pdf import pdf_del_cupon
from src.core.database import db
from src.core.notificaciones import notificar
from src.core.pacientes.modelos import Paciente
from src.core.usuarios import roles
from src.core.usuarios.modelos import Medico, Usuario
from src.integraciones import cupones as modulo_de_cupones
from src.integraciones import storage
from src.integraciones.base import ErrorDeIntegracion

MAXIMO_DE_CUPONES_POR_PEDIDO = 100
SOLO_UN_GERENTE = "El módulo de cupones admite un solo gerente por grupo y ya hay otro."
PACIENTE_CON_CUPON = "Ese paciente ya recibió un cupón: el módulo permite uno por paciente."
CUPON_DESCONOCIDO = "El módulo de cupones no reconoce ese cupón para tu usuario."
CENTAVOS = Decimal("0.01")


class ErrorDeCupon(ValueError):
    """No se puede generar, asignar o usar el cupón; el mensaje se muestra al usuario."""


# --- E37: el gerente médico genera cupones para un médico tratante -----------------------------


def medicos_tratantes() -> list[Usuario]:
    """Médicos tratantes activos, para elegir a quién se asignan los cupones (E37.4)."""
    consulta = (
        sa.select(Usuario)
        .join(Medico, Medico.usuario_id == Usuario.id)
        .where(Usuario.rol_codigo == roles.MEDICO_TRATANTE, Usuario.activo)
        .order_by(Usuario.apellido, Usuario.nombre, Usuario.id)
    )
    return list(db.session.scalars(consulta))


def generar_cupones(
    gerente: Usuario, medico: Usuario | None, porcentaje: Decimal | int | str, cantidad: int | str
) -> list[Cupon]:
    """E37.1 a E37.5: pide los cupones al módulo, guarda sus PDF, los asigna al médico y le avisa.

    Lanza ErrorDeCupon si quien genera no es gerente médico, si el médico no es un médico tratante
    activo, si el porcentaje no está entre 1 y 100 o si la cantidad no es válida. Si el módulo o
    Storage fallan, lanza ErrorDeIntegracion y el controlador hace rollback: no queda ningún cupón.
    """
    if not gerente.tiene_rol(roles.GERENTE_MEDICO):
        raise ErrorDeCupon("Solo un gerente médico puede generar cupones.")
    if (
        medico is None
        or not medico.tiene_rol(roles.MEDICO_TRATANTE)
        or not medico.activo
        or db.session.get(Medico, medico.id) is None
    ):
        raise ErrorDeCupon("Elegí un médico tratante.")
    porcentaje = _validar_porcentaje(porcentaje)
    cantidad = _validar_cantidad(cantidad)

    try:
        generados = modulo_de_cupones.generar(gerente.id, porcentaje, cantidad)
    except ErrorDeIntegracion as error:
        raise _error_de_cupon(error, {403: SOLO_UN_GERENTE}) from None
    codigos = [generado.codigo for generado in generados]
    repetidos = db.session.scalars(sa.select(Cupon.codigo).where(Cupon.codigo.in_(codigos))).all()
    if repetidos or len(set(codigos)) != len(codigos):
        raise ErrorDeCupon("El módulo de cupones devolvió códigos que ya están registrados.")

    ahora = datetime.now(UTC)
    cupones = []
    for generado in generados:
        try:
            modulo_de_cupones.asignar_a_medico(gerente.id, medico.id, generado.codigo)
        except ErrorDeIntegracion as error:
            raise _error_de_cupon(error, {403: SOLO_UN_GERENTE}) from None
        pdf = pdf_del_cupon(generado.codigo, generado.porcentaje)
        ruta = storage.subir(f"cupones/{generado.codigo}.pdf", pdf, reemplazar=True)
        cupon = Cupon(
            codigo=generado.codigo,
            descuento_porcentaje=generado.porcentaje,
            pdf_path=ruta,
            estado=EstadoCupon.VIGENTE,
            generado_por=gerente.id,
            medico_tratante_id=medico.id,
            asignado_a_medico_en=ahora,
        )
        db.session.add(cupon)
        cupones.append(cupon)
    db.session.flush()
    notificar(
        medico,
        "Cupones de descuento recibidos",
        f"Recibiste {cantidad} cupón(es) de descuento del {cupones[0].descuento_porcentaje}%. "
        "Podés asignarlos a tus pacientes.",
        "/cupones/mios",
    )
    return cupones


def cupones_generados(gerente: Usuario) -> list[Cupon]:
    """Cupones que generó este gerente médico, los últimos primero."""
    consulta = sa.select(Cupon).where(Cupon.generado_por == gerente.id).order_by(Cupon.id.desc())
    return list(db.session.scalars(consulta))


# --- E38: el médico tratante asigna sus cupones a sus pacientes ---------------------------------


def cupones_del_medico(medico: Usuario) -> list[Cupon]:
    """E38.1: todos los cupones que recibió el médico, con su estado y su paciente."""
    consulta = sa.select(Cupon).where(Cupon.medico_tratante_id == medico.id).order_by(Cupon.id)
    return list(db.session.scalars(consulta))


def cupones_disponibles(medico: Usuario) -> list[Cupon]:
    """E38.1: los cupones del médico que están vigentes y todavía sin paciente."""
    return [
        cupon
        for cupon in cupones_del_medico(medico)
        if cupon.estado == EstadoCupon.VIGENTE and cupon.paciente_id is None
    ]


def pacientes_del_medico(medico: Usuario) -> list[Paciente]:
    consulta = (
        sa.select(Paciente)
        .join(Usuario, Usuario.id == Paciente.usuario_id)
        .where(Paciente.medico_tratante_id == medico.id)
        .order_by(Usuario.apellido, Usuario.nombre, Paciente.id)
    )
    return list(db.session.scalars(consulta))


def asignar_a_paciente(medico: Usuario, cupon_id: int, paciente_id: int) -> Cupon:
    """E38.2 a E38.5: asigna un cupón vigente y sin paciente a un paciente del médico y le avisa.

    Lanza ErrorDeCupon si quien asigna no es médico tratante, si el cupón no es suyo, no está
    vigente o ya tiene paciente, o si el paciente no es suyo.
    """
    if not medico.tiene_rol(roles.MEDICO_TRATANTE):
        raise ErrorDeCupon("Solo un médico tratante puede asignar cupones.")
    cupon = db.session.get(Cupon, cupon_id, with_for_update=True)
    if cupon is None or cupon.medico_tratante_id != medico.id:
        raise ErrorDeCupon("Ese cupón no está entre tus cupones.")
    if cupon.estado != EstadoCupon.VIGENTE:
        raise ErrorDeCupon(f"El cupón {cupon.codigo} ya no está vigente.")
    if cupon.paciente_id is not None:
        raise ErrorDeCupon(f"El cupón {cupon.codigo} ya está asignado a un paciente.")
    paciente = db.session.get(Paciente, paciente_id)
    if paciente is None or paciente.medico_tratante_id != medico.id:
        raise ErrorDeCupon("Ese paciente no es tuyo.")

    try:
        modulo_de_cupones.asignar_a_paciente(medico.id, paciente.id, cupon.codigo)
    except ErrorDeIntegracion as error:
        raise _error_de_cupon(error, {404: CUPON_DESCONOCIDO, 409: PACIENTE_CON_CUPON}) from None

    cupon.paciente_id = paciente.id
    cupon.asignado_a_paciente_en = datetime.now(UTC)
    db.session.flush()
    notificar(
        paciente.usuario,
        "Tenés un cupón de descuento",
        f"Tu médico te asignó un cupón de descuento del {cupon.descuento_porcentaje}%. "
        "Lo podés usar al pagar tu estudio.",
        "/cupones/mios",
    )
    return cupon


# --- E15: el paciente usa su cupón al pagar -----------------------------------------------------


def cupones_del_paciente(usuario: Usuario) -> list[Cupon]:
    """E38.5: los cupones vigentes asignados al paciente."""
    consulta = (
        sa.select(Cupon)
        .join(Paciente, Paciente.id == Cupon.paciente_id)
        .where(Paciente.usuario_id == usuario.id, Cupon.estado == EstadoCupon.VIGENTE)
        .order_by(Cupon.id)
    )
    return list(db.session.scalars(consulta))


def resolver_cupon(usuario: Usuario, codigo: str) -> Cupon:
    """E15.2 a E15.4: el cupón del paciente con ese código, si está vigente en el módulo.

    Lanza ErrorDeCupon con el motivo del rechazo si no existe, no es del paciente o no está
    vigente (en el sistema o según el módulo). Si el módulo falla, lanza ErrorDeIntegracion.
    """
    codigo = (codigo or "").strip()
    if not codigo:
        raise ErrorDeCupon("Ingresá el código del cupón o subí su PDF.")
    cupon = db.session.scalar(sa.select(Cupon).where(Cupon.codigo == codigo))
    if cupon is None or cupon.paciente_id is None:
        raise ErrorDeCupon("Ese cupón no existe o no está asignado a tu cuenta.")
    if db.session.get(Paciente, cupon.paciente_id).usuario_id != usuario.id:
        raise ErrorDeCupon("Ese cupón no existe o no está asignado a tu cuenta.")
    if cupon.estado != EstadoCupon.VIGENTE:
        raise ErrorDeCupon(f"El cupón {cupon.codigo} ya fue utilizado.")
    en_modulo = modulo_de_cupones.consultar(cupon.codigo, medico_id=cupon.medico_tratante_id)
    if en_modulo is None:
        raise ErrorDeCupon(f"El módulo de cupones no encuentra el cupón {cupon.codigo}.")
    if en_modulo.estado == "usado":
        raise ErrorDeCupon(f"El cupón {cupon.codigo} ya fue utilizado.")
    if en_modulo.vencido:
        vencimiento = en_modulo.fecha_vencimiento
        raise ErrorDeCupon(f"El cupón {cupon.codigo} venció el {vencimiento:%d/%m/%Y}.")
    if en_modulo.estado != "paciente":
        raise ErrorDeCupon(f"El módulo informa que el cupón {cupon.codigo} no está asignado.")
    return cupon


def calcular_descuento(total: Decimal, cupon: Cupon) -> Decimal:
    """Porcentaje del cupón sobre el total del presupuesto, a centavos."""
    return (total * cupon.descuento_porcentaje / 100).quantize(CENTAVOS, ROUND_HALF_UP)


def consumir_cupon(cupon: Cupon) -> None:
    """E15.6: avisa al módulo que el cupón se usó y lo marca utilizado en el sistema.

    Va dentro de la transacción del pago, antes del commit: si el módulo falla lanza
    ErrorDeIntegracion y el controlador hace rollback, así que no queda ningún pago.
    """
    modulo_de_cupones.canjear(cupon.paciente_id, cupon.codigo)
    cupon.estado = EstadoCupon.UTILIZADO
    cupon.utilizado_en = datetime.now(UTC)
    db.session.flush()


# --- G7: código a partir del PDF subido -------------------------------------------------------


def codigo_desde_pdf(contenido: bytes) -> str:
    """El código de cupón que aparece en el texto del PDF.

    Busca, entre las palabras del texto, un código de cupón registrado. Lanza ErrorDeCupon si el
    archivo no es un PDF legible o no contiene un código conocido; el mensaje pide escribirlo.
    """
    try:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(contenido))
        texto = " ".join(pagina.extract_text() or "" for pagina in lector.pages)
    except Exception:  # noqa: BLE001  (pypdf lanza errores de muchos tipos con PDF dañados)
        raise ErrorDeCupon("No se pudo leer el PDF. Escribí el código del cupón a mano.") from None
    candidatos = set(re.findall(r"[A-Za-z0-9_-]{4,64}", texto))
    if candidatos:
        encontrado = db.session.scalar(sa.select(Cupon.codigo).where(Cupon.codigo.in_(candidatos)))
        if encontrado:
            return encontrado
    raise ErrorDeCupon("No se encontró el código del cupón en el PDF. Escribilo a mano.")


def _error_de_cupon(error: ErrorDeIntegracion, mensajes: dict[int, str]) -> Exception:
    """Un rechazo del módulo que el usuario puede corregir pasa a ErrorDeCupon; una caída sigue
    siendo ErrorDeIntegracion."""
    if error.status in mensajes:
        return ErrorDeCupon(mensajes[error.status])
    if error.status in (400, 404, 409):
        return ErrorDeCupon(error.mensaje)
    return error


# --- validaciones -------------------------------------------------------------------------------


def _validar_porcentaje(valor) -> Decimal:
    try:
        porcentaje = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise ErrorDeCupon("El descuento tiene que ser un número.") from None
    if not porcentaje.is_finite() or not Decimal(1) <= porcentaje <= Decimal(100):
        raise ErrorDeCupon("El descuento es un porcentaje entre 1 y 100.")
    if porcentaje != porcentaje.quantize(CENTAVOS):
        raise ErrorDeCupon("El descuento admite hasta dos decimales.")
    return porcentaje.quantize(CENTAVOS)


def _validar_cantidad(valor) -> int:
    try:
        cantidad = int(str(valor).strip())
    except ValueError:
        raise ErrorDeCupon("La cantidad tiene que ser un número entero.") from None
    if not 1 <= cantidad <= MAXIMO_DE_CUPONES_POR_PEDIDO:
        raise ErrorDeCupon(f"La cantidad de cupones es de 1 a {MAXIMO_DE_CUPONES_POR_PEDIDO}.")
    return cantidad
