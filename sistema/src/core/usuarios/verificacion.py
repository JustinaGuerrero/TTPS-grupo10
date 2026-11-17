"""Códigos de acceso de un solo uso y dispositivos confiables (E04)."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from werkzeug.security import check_password_hash, generate_password_hash

from src.core.database import db
from src.core.usuarios.modelos import CodigoVerificacion, DispositivoConfiable, Usuario

DURACION_CODIGO = timedelta(minutes=10)
MAXIMO_DE_INTENTOS = 5


def calcular_huella_hash(cookie: str, ip: str, secreto: str) -> str:
    """Genera un HMAC de la cookie aleatoria y la IP, sin conservar ninguno en claro."""
    mensaje = b"exoma-dispositivo-v1\0" + cookie.encode() + b"\0" + ip.encode()
    return hmac.new(secreto.encode(), mensaje, hashlib.sha256).hexdigest()


def dispositivo_confiable(usuario_id: int, huella_hash: str) -> bool:
    """Actualiza el último ingreso si existe la combinación usuario, dispositivo y red."""
    dispositivo = db.session.scalar(
        sa.select(DispositivoConfiable)
        .where(
            DispositivoConfiable.usuario_id == usuario_id,
            DispositivoConfiable.huella_hash == huella_hash,
        )
        .with_for_update()
    )
    if dispositivo is None:
        return False
    dispositivo.ultimo_ingreso_en = datetime.now(UTC)
    return True


def emitir_codigo(usuario_id: int, huella_hash: str) -> tuple[CodigoVerificacion, str]:
    """Invalida los códigos previos para esta huella y emite uno válido durante diez minutos."""
    ahora = datetime.now(UTC)
    db.session.scalar(sa.select(Usuario.id).where(Usuario.id == usuario_id).with_for_update())
    anteriores = db.session.scalars(
        sa.select(CodigoVerificacion)
        .where(
            CodigoVerificacion.usuario_id == usuario_id,
            CodigoVerificacion.huella_hash == huella_hash,
            CodigoVerificacion.usado_en.is_(None),
        )
        .with_for_update()
    )
    for anterior in anteriores:
        anterior.usado_en = ahora

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    registro = CodigoVerificacion(
        usuario_id=usuario_id,
        codigo_hash=generate_password_hash(codigo, method="scrypt"),
        huella_hash=huella_hash,
        intentos=0,
        expira_en=ahora + DURACION_CODIGO,
    )
    db.session.add(registro)
    db.session.flush()
    return registro, codigo


def validar_codigo(codigo_id: int, usuario_id: int, huella_hash: str, valor: str) -> bool:
    """Consume el código correcto o registra un intento fallido. No hace commit."""
    registro = db.session.scalar(
        sa.select(CodigoVerificacion)
        .where(
            CodigoVerificacion.id == codigo_id,
            CodigoVerificacion.usuario_id == usuario_id,
            CodigoVerificacion.huella_hash == huella_hash,
        )
        .with_for_update()
    )
    if registro is None or registro.usado_en is not None:
        return False

    ahora = datetime.now(UTC)
    if registro.expira_en <= ahora or registro.intentos >= MAXIMO_DE_INTENTOS:
        registro.usado_en = ahora
        return False

    if (
        len(valor) != 6
        or not valor.isascii()
        or not valor.isdigit()
        or not check_password_hash(registro.codigo_hash, valor)
    ):
        registro.intentos += 1
        if registro.intentos >= MAXIMO_DE_INTENTOS:
            registro.usado_en = ahora
        return False

    registro.usado_en = ahora
    dispositivo = db.session.scalar(
        sa.select(DispositivoConfiable).where(
            DispositivoConfiable.usuario_id == usuario_id,
            DispositivoConfiable.huella_hash == huella_hash,
        )
    )
    if dispositivo is None:
        db.session.add(
            DispositivoConfiable(
                usuario_id=usuario_id,
                huella_hash=huella_hash,
                ultimo_ingreso_en=ahora,
            )
        )
    else:
        dispositivo.ultimo_ingreso_en = ahora
    return True
