"""Base de test: migraciones aplicadas, modelos alineados y usuarios que se guardan y se leen."""

import importlib
import pkgutil

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

import src.core
from src.core.database import Base, db
from src.core.usuarios import Rol, Usuario, roles

ROLES_DEL_LEL = {
    "paciente",
    "medico_tratante",
    "administrativo",
    "bioinformatico",
    "transportista",
    "gerente_medico",
    "administrador_general",
}


def _usuario_de_prueba(email: str = "ana.prueba@example.com") -> Usuario:
    return Usuario(
        email=email,
        hash_contrasena="hash-de-prueba",
        nombre="Ana",
        apellido="Prueba",
        rol_codigo="administrativo",
    )


def test_inserta_y_lee_un_usuario(app):
    with app.app_context():
        db.session.add(_usuario_de_prueba())
        db.session.commit()

    # Otro contexto de app es otra sesión: el usuario se lee de la base, no de memoria.
    with app.app_context():
        usuario = db.session.scalars(
            sa.select(Usuario).where(Usuario.email == "ana.prueba@example.com")
        ).one()

        assert usuario.nombre == "Ana"
        assert usuario.apellido == "Prueba"
        assert usuario.rol.nombre == "Administrativo"
        assert usuario.activo is True
        assert usuario.creado_en is not None
        assert usuario.actualizado_en is not None


def test_rechaza_el_mismo_email_con_otras_mayusculas(app):
    with app.app_context():
        db.session.add(_usuario_de_prueba("ana.prueba@example.com"))
        db.session.commit()

        db.session.add(_usuario_de_prueba("Ana.Prueba@Example.com"))
        with pytest.raises(IntegrityError, match="usuarios_email_unico"):
            db.session.commit()


def test_la_migracion_carga_los_siete_roles_del_lel(app):
    with app.app_context():
        codigos = set(db.session.scalars(sa.select(Rol.codigo)))

    assert codigos == ROLES_DEL_LEL
    assert set(roles.TODOS) == ROLES_DEL_LEL


def test_todas_las_tablas_tienen_rls(app):
    consulta = sa.text(
        """
        select c.relname
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind in ('r', 'p') and not c.relrowsecurity
        """
    )
    with app.app_context():
        sin_rls = db.session.scalars(consulta).all()

    assert sin_rls == [], f"Tablas sin 'enable row level security': {sin_rls}"


def test_los_modelos_coinciden_con_las_migraciones(app):
    # Importa todo src/core para que cada modelo, de cualquier módulo, quede en Base.metadata.
    for modulo in pkgutil.walk_packages(src.core.__path__, "src.core."):
        importlib.import_module(modulo.name)
    assert Base.metadata.sorted_tables

    with app.app_context():
        inspector = sa.inspect(db.session.connection())
        for tabla in Base.metadata.sorted_tables:
            assert inspector.has_table(tabla.name, schema="public"), (
                f"El modelo usa la tabla {tabla.name}, que ninguna migración crea"
            )
            columnas = {c["name"] for c in inspector.get_columns(tabla.name, schema="public")}
            faltantes = set(tabla.columns.keys()) - columnas
            assert not faltantes, f"{tabla.name}: columnas del modelo sin migración: {faltantes}"
