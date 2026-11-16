"""E43 Registrar cambios: registrar, diferencias, historial mezclado, filtros, permisos y 404."""

from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa

from src.core import auditoria
from src.core.auditoria import (
    Accion,
    Entidad,
    FiltrosDeAuditoria,
    RegistroDeCambio,
    diferencias,
    historial_de,
    listar,
    registrar,
)
from src.core.database import db
from src.core.estudios import EstadoEstudio
from src.core.usuarios import roles


def _entrar_como(client, usuario):
    """Inicia sesión con un usuario o con su id (los objetos no sirven fuera del app_context)."""
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = getattr(usuario, "id", usuario)


def _filas(entidad=None):
    consulta = sa.select(RegistroDeCambio).order_by(RegistroDeCambio.id)
    if entidad is not None:
        consulta = consulta.where(RegistroDeCambio.entidad == entidad)
    return db.session.scalars(consulta).all()


def _fecha(dia: int, hora: int = 12) -> datetime:
    return datetime(2026, 11, dia, hora, 0, tzinfo=UTC)


# --- registrar ---


def test_registrar_guarda_fecha_usuario_campo_y_valores(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        filas = registrar(
            Entidad.PACIENTE,
            7,
            medico,
            Accion.MODIFICACION,
            {"fecha_nacimiento": (date(2000, 1, 1), date(2001, 2, 3))},
            detalle="Corrección de un error de carga",
        )

        (fila,) = filas
        assert fila.id is not None
        assert fila.creado_en is not None
        assert (fila.entidad, fila.entidad_id, fila.accion) == (
            Entidad.PACIENTE,
            7,
            Accion.MODIFICACION,
        )
        assert fila.campo == "fecha_nacimiento"
        assert (fila.valor_anterior, fila.valor_nuevo) == ("2000-01-01", "2001-02-03")
        assert fila.usuario_id == medico.id
        assert fila.detalle == "Corrección de un error de carga"


def test_registrar_guarda_una_fila_por_campo(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        filas = registrar(
            Entidad.PACIENTE,
            7,
            medico,
            Accion.MODIFICACION,
            {"dni": ("1", "2"), "tipo_sospecha": ("clinica", "familiar")},
        )

        assert sorted(f.campo for f in filas) == ["dni", "tipo_sospecha"]
        assert len(_filas()) == 2


def test_registrar_sin_cambios_no_guarda_nada(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        assert registrar(Entidad.ESTUDIO, 3, medico, Accion.MODIFICACION, {}) == []
        # Mismo valor antes y después, aunque venga con otro tipo o con espacios.
        assert (
            registrar(
                Entidad.ESTUDIO,
                3,
                medico,
                Accion.MODIFICACION,
                {"pompe_urgente": (False, False), "x": ("1", 1), "y": (None, "  ")},
            )
            == []
        )
        assert _filas() == []


def test_registrar_no_hace_commit_y_un_rollback_no_deja_nada(app, usuario_rapido):
    with app.app_context():
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()

        registrar(Entidad.PACIENTE, 7, medico, Accion.MODIFICACION, {"dni": ("1", "2")})
        # Dentro de la transacción de quien llama, el registro ya se ve…
        assert len(_filas()) == 1

        # …y si quien llama revierte el cambio, el registro se va con él.
        db.session.rollback()
        assert _filas() == []


def test_registrar_con_usuario_nulo_es_del_sistema(app):
    with app.app_context():
        (fila,) = registrar(Entidad.ESTUDIO, 3, None, Accion.MODIFICACION, {"datos": ("a", "b")})

        assert fila.usuario_id is None
        (cambio,) = historial_de(Entidad.ESTUDIO, 3)
        assert cambio.usuario is None
        assert cambio.quien == "Sistema"


@pytest.mark.parametrize(
    "campo",
    ["contrasena", "hash_contrasena", "contrasena_provisoria", "password", "codigo_verificacion"]
    + ["token", "api_key_secreta", "clave", "Hash_Contrasena"],
)
def test_nunca_guarda_contrasenas_ni_codigos(app, campo):
    with app.app_context():
        filas = registrar(
            Entidad.PACIENTE,
            7,
            None,
            Accion.MODIFICACION,
            {campo: ("valor-viejo-123", "valor-nuevo-456"), "dni": ("1", "2")},
        )

        assert [f.campo for f in filas] == ["dni"]
        assert [f.campo for f in _filas()] == ["dni"]


def test_el_codigo_del_estudio_no_es_un_codigo_de_verificacion(app):
    with app.app_context():
        (fila,) = registrar(
            Entidad.ESTUDIO, 3, None, Accion.MODIFICACION, {"codigo": ("EX-1", "EX-2")}
        )

        assert fila.campo == "codigo"


def test_alta_y_baja_dejan_vacio_el_valor_que_no_hay(app):
    with app.app_context():
        (alta,) = registrar(Entidad.PACIENTE, 7, None, Accion.ALTA, {"familiar": (None, "Madre")})
        (baja,) = registrar(Entidad.PACIENTE, 7, None, Accion.BAJA, {"familiar": ("Madre", None)})

        assert (alta.valor_anterior, alta.valor_nuevo) == (None, "Madre")
        assert (baja.valor_anterior, baja.valor_nuevo) == ("Madre", None)


def test_registrar_valida_entidad_accion_y_id(app):
    with app.app_context():
        with pytest.raises(ValueError, match="entidad"):
            registrar("usuario", 1, None, Accion.MODIFICACION, {"a": ("1", "2")})
        with pytest.raises(ValueError, match="acción"):
            registrar(Entidad.PACIENTE, 1, None, "borrado", {"a": ("1", "2")})
        with pytest.raises(ValueError, match="historial_estados"):
            registrar(Entidad.ESTUDIO, 1, None, Accion.ESTADO, {"estado": ("a", "b")})
        with pytest.raises(ValueError, match="id"):
            registrar(Entidad.PACIENTE, None, None, Accion.MODIFICACION, {"a": ("1", "2")})
        assert _filas() == []


def test_acepta_la_entidad_y_la_accion_como_texto(app):
    with app.app_context():
        (fila,) = registrar("sample_set", 5, None, "baja", {"muestra": ("M-1", None)})

        assert (fila.entidad, fila.accion) == (Entidad.SAMPLE_SET, Accion.BAJA)


# --- el registro no se edita ni se borra ---


def test_la_base_no_deja_editar_ni_borrar_registros(app):
    with app.app_context():
        registrar(Entidad.PACIENTE, 7, None, Accion.MODIFICACION, {"dni": ("1", "2")})

        for sentencia in ("update auditoria set valor_nuevo = 'otro'", "delete from auditoria"):
            with pytest.raises(sa.exc.DBAPIError, match="solo se inserta"):
                db.session.execute(sa.text(sentencia))
            db.session.rollback()
            # El rollback también deshizo el registro de arriba: se vuelve a crear.
            registrar(Entidad.PACIENTE, 7, None, Accion.MODIFICACION, {"dni": ("1", "2")})


def test_el_modulo_no_ofrece_editar_ni_borrar():
    publicas = {nombre.lower() for nombre in auditoria.__all__}
    for palabra in ("editar", "modificar", "borrar", "eliminar", "actualizar", "update", "delete"):
        assert not any(palabra in nombre for nombre in publicas)


# --- diferencias ---


def test_diferencias_devuelve_solo_los_campos_que_cambiaron():
    antes = {"dni": "1", "telefono": "11", "fecha_nacimiento": date(2000, 1, 1)}
    despues = {"dni": "1", "telefono": "22", "fecha_nacimiento": date(2000, 1, 1)}

    assert diferencias(antes, despues, ["dni", "telefono", "fecha_nacimiento"]) == {
        "telefono": ("11", "22")
    }


def test_diferencias_sin_cambios_es_vacio():
    assert diferencias({"a": 1}, {"a": "1"}, ["a"]) == {}
    assert diferencias({"a": None}, {"a": ""}, ["a"]) == {}


def test_diferencias_toma_atributos_de_un_objeto_y_un_campo_ausente_es_vacio():
    class Dato:
        dni = "1"

    assert diferencias(Dato(), {"dni": "2", "nuevo": "x"}, ["dni", "nuevo"]) == {
        "dni": ("1", "2"),
        "nuevo": (None, "x"),
    }


def test_diferencias_solo_mira_los_campos_pedidos():
    assert diferencias({"a": 1, "b": 1}, {"a": 2, "b": 2}, ["a"]) == {"a": (1, 2)}


# --- historial_de ---


def test_historial_de_un_estudio_mezcla_estados_y_datos_ordenados_por_fecha(
    app, crear_estudio, crear_registro_de_cambio, usuario_rapido
):
    with app.app_context():
        estudio = crear_estudio(estado=EstadoEstudio.PRESUPUESTADO)
        medico = usuario_rapido(roles.MEDICO_TRATANTE)
        db.session.flush()
        # Fechas fijas: en los tests todo comparte la hora de la transacción.
        filas = (
            db.session.execute(
                sa.text("select id from historial_estados where estudio_id = :e order by id"),
                {"e": estudio.id},
            )
            .scalars()
            .all()
        )
        assert len(filas) == 2
        for numero, fila in enumerate(filas, start=1):
            db.session.execute(
                sa.text("update historial_estados set creado_en = :f where id = :i"),
                {"f": _fecha(numero * 2), "i": fila},
            )
        crear_registro_de_cambio(
            Entidad.ESTUDIO, estudio.id, "pompe_urgente", "no", "sí", medico, creado_en=_fecha(3)
        )
        crear_registro_de_cambio(
            Entidad.ESTUDIO, estudio.id, "genes", "GAA", "GAA, GBA", None, creado_en=_fecha(5)
        )

        cambios = historial_de(Entidad.ESTUDIO, estudio.id)

        assert [(c.accion, c.campo) for c in cambios] == [
            (Accion.MODIFICACION, "genes"),
            (Accion.ESTADO, "estado"),
            (Accion.MODIFICACION, "pompe_urgente"),
            (Accion.ESTADO, "estado"),
        ]
        assert [c.creado_en for c in cambios] == sorted(
            (c.creado_en for c in cambios), reverse=True
        )
        estado = cambios[1]
        assert (estado.valor_anterior, estado.valor_nuevo) == ("creado", "presupuestado")
        assert estado.usuario is None
        assert cambios[2].usuario == medico
        assert cambios[3].valor_anterior is None
        assert cambios[3].usuario is not None


def test_historial_de_un_paciente_o_sample_set_no_trae_estados_ni_otras_entidades(
    app, crear_estudio, crear_registro_de_cambio
):
    with app.app_context():
        estudio = crear_estudio()
        crear_registro_de_cambio(Entidad.PACIENTE, estudio.id, "dni")
        crear_registro_de_cambio(Entidad.SAMPLE_SET, estudio.id, "muestra")
        crear_registro_de_cambio(Entidad.PACIENTE, estudio.id + 1, "otro")

        assert [c.campo for c in historial_de(Entidad.PACIENTE, estudio.id)] == ["dni"]
        assert [c.campo for c in historial_de(Entidad.SAMPLE_SET, estudio.id)] == ["muestra"]


def test_historial_de_con_la_misma_fecha_pone_el_ultimo_registro_primero(
    app, crear_registro_de_cambio
):
    with app.app_context():
        for campo in ("a", "b", "c"):
            crear_registro_de_cambio(Entidad.PACIENTE, 1, campo, creado_en=_fecha(1))

        assert [c.campo for c in historial_de(Entidad.PACIENTE, 1)] == ["c", "b", "a"]


# --- listar ---


@pytest.fixture
def registros(app, usuario_rapido, crear_registro_de_cambio):
    """Cinco cambios: de dos usuarios y del sistema, en tres entidades y varios días."""
    with app.app_context():
        ana = usuario_rapido(roles.MEDICO_TRATANTE)
        beto = usuario_rapido(roles.ADMINISTRATIVO)
        db.session.flush()
        crear_registro_de_cambio(Entidad.PACIENTE, 1, "dni", usuario=ana, creado_en=_fecha(10))
        crear_registro_de_cambio(Entidad.PACIENTE, 1, "telefono", usuario=ana, creado_en=_fecha(11))
        crear_registro_de_cambio(Entidad.ESTUDIO, 2, "genes", usuario=beto, creado_en=_fecha(12))
        crear_registro_de_cambio(
            Entidad.SAMPLE_SET, 3, "muestra", usuario=None, creado_en=_fecha(13)
        )
        crear_registro_de_cambio(
            Entidad.ESTUDIO, 2, "pompe_urgente", usuario=ana, creado_en=_fecha(14)
        )
        db.session.commit()
        ids = {"ana": ana.id, "ana_nombre": f"{ana.apellido}, {ana.nombre}", "beto": beto.id}
    return ids


def _campos(pagina):
    return [r.campo for r in pagina.items]


def test_listar_sin_filtros_trae_todo_del_mas_nuevo_al_mas_viejo(app, registros):
    with app.app_context():
        pagina = listar(FiltrosDeAuditoria())

        assert _campos(pagina) == ["pompe_urgente", "muestra", "genes", "telefono", "dni"]
        assert pagina.total == 5


def test_listar_filtra_por_entidad(app, registros):
    with app.app_context():
        pagina = listar(FiltrosDeAuditoria(entidad="estudio"))

        assert _campos(pagina) == ["pompe_urgente", "genes"]


def test_listar_filtra_por_usuario_y_por_sistema(app, registros):
    with app.app_context():
        ana = listar(FiltrosDeAuditoria(usuario=str(registros["ana"])))
        sistema = listar(FiltrosDeAuditoria(usuario="sistema"))

        assert _campos(ana) == ["pompe_urgente", "telefono", "dni"]
        assert _campos(sistema) == ["muestra"]


def test_listar_filtra_por_fechas_con_el_dia_de_argentina(app, registros, crear_registro_de_cambio):
    with app.app_context():
        # 02:30 UTC del 15 es el 14 a las 23:30 en Argentina: cae en el día 14, no en el 15.
        crear_registro_de_cambio(
            Entidad.PACIENTE, 9, "tarde", creado_en=datetime(2026, 11, 15, 2, 30, tzinfo=UTC)
        )

        entre = listar(FiltrosDeAuditoria(desde=date(2026, 11, 11), hasta=date(2026, 11, 12)))
        el_14 = listar(FiltrosDeAuditoria(desde=date(2026, 11, 14), hasta=date(2026, 11, 14)))
        desde = listar(FiltrosDeAuditoria(desde=date(2026, 11, 13)))
        hasta = listar(FiltrosDeAuditoria(hasta=date(2026, 11, 10)))
        invertido = listar(FiltrosDeAuditoria(desde=date(2026, 11, 14), hasta=date(2026, 11, 10)))

        assert _campos(entre) == ["genes", "telefono"]
        assert sorted(_campos(el_14)) == ["pompe_urgente", "tarde"]
        assert _campos(desde) == ["tarde", "pompe_urgente", "muestra"]
        assert _campos(hasta) == ["dni"]
        assert invertido.total == 0


def test_listar_combina_filtros_y_pagina(app, registros):
    with app.app_context():
        primera = listar(FiltrosDeAuditoria(usuario=str(registros["ana"])), por_pagina=2)
        segunda = listar(FiltrosDeAuditoria(usuario=str(registros["ana"]), pagina=2), por_pagina=2)
        combinada = listar(FiltrosDeAuditoria(entidad="paciente", usuario=str(registros["ana"])))

        assert (_campos(primera), primera.total, primera.cantidad_de_paginas) == (
            ["pompe_urgente", "telefono"],
            3,
            2,
        )
        assert _campos(segunda) == ["dni"]
        assert _campos(combinada) == ["telefono", "dni"]


def test_los_filtros_descartan_lo_que_no_es_valido():
    filtros = FiltrosDeAuditoria.desde_parametros(
        {"entidad": "usuario", "usuario": "1; drop", "desde": "ayer", "hasta": "2026-13-45"}
        | {"pagina": "-3"}
    )

    assert filtros == FiltrosDeAuditoria()
    valido = FiltrosDeAuditoria.desde_parametros(
        {"entidad": "estudio", "usuario": "sistema", "desde": "2026-11-01", "pagina": "2"}
    )
    assert valido == FiltrosDeAuditoria("estudio", "sistema", date(2026, 11, 1), None, 2)
    assert valido.parametros(pagina=3) == {
        "entidad": "estudio",
        "usuario": "sistema",
        "desde": "2026-11-01",
        "pagina": 3,
    }


# --- pantallas: la lista (administrador general) ---


def test_administrador_ve_la_lista_y_filtra_por_usuario(app, client, login_como, registros):
    login_como(roles.ADMINISTRADOR_GENERAL)
    ana_id, ana_nombre = registros["ana"], registros["ana_nombre"]

    todo = client.get("/auditoria")
    assert todo.status_code == 200
    assert "5 cambios" in todo.text
    assert "pompe urgente" in todo.text.lower()
    assert "Sistema" in todo.text
    assert ana_nombre in todo.text
    assert 'href="/auditoria/estudio/2"' in todo.text

    de_ana = client.get(f"/auditoria?usuario={ana_id}")
    assert "3 cambios" in de_ana.text
    assert "Genes" not in de_ana.text
    assert "Muestra" not in de_ana.text

    por_fecha = client.get("/auditoria?entidad=estudio&desde=2026-11-14&hasta=2026-11-14")
    assert "1–1 de 1 cambio" in por_fecha.text


def test_la_lista_sin_resultados_lo_dice_y_pagina(
    app, client, login_como, crear_registro_de_cambio
):
    login_como(roles.ADMINISTRADOR_GENERAL)
    assert "Todavía no hay cambios" in client.get("/auditoria").text
    assert "Ningún cambio coincide" in client.get("/auditoria?entidad=estudio").text

    with app.app_context():
        for numero in range(27):
            crear_registro_de_cambio(Entidad.PACIENTE, 1, f"campo{numero}", creado_en=_fecha(1))
        db.session.commit()

    assert "1–25 de 27 cambios" in client.get("/auditoria").text
    assert "26–27 de 27 cambios" in client.get("/auditoria?pagina=2").text


def test_el_menu_del_administrador_tiene_auditoria(client, login_como):
    login_como(roles.ADMINISTRADOR_GENERAL)

    assert 'href="/auditoria"' in client.get("/").text


@pytest.mark.parametrize(
    "rol",
    [
        roles.PACIENTE,
        roles.MEDICO_TRATANTE,
        roles.ADMINISTRATIVO,
        roles.BIOINFORMATICO,
        roles.TRANSPORTISTA,
        roles.GERENTE_MEDICO,
    ],
)
def test_la_lista_completa_es_solo_del_administrador_general(client, login_como, rol):
    login_como(rol)

    assert client.get("/auditoria").status_code == 403


def test_sin_sesion_redirige_al_login(client):
    assert client.get("/auditoria").status_code == 302
    assert client.get("/auditoria/paciente/1").status_code == 302


# --- pantallas: el historial de una entidad (G17) ---


@pytest.fixture
def caso(app, client, crear_estudio, crear_paciente, crear_registro_de_cambio, usuario_rapido):
    """Un estudio con su paciente, un médico ajeno y cambios en las tres entidades."""
    with app.app_context():
        estudio = crear_estudio()
        paciente = estudio.paciente
        ajeno = crear_paciente().medico_tratante.usuario
        crear_registro_de_cambio(
            Entidad.PACIENTE,
            paciente.id,
            "fecha_nacimiento",
            "2000-01-01",
            "2001-02-03",
            usuario_rapido(roles.MEDICO_TRATANTE),
            # 02:30 UTC es las 23:30 del día anterior en Argentina.
            creado_en=datetime(2026, 11, 10, 2, 30, tzinfo=UTC),
        )
        crear_registro_de_cambio(Entidad.ESTUDIO, estudio.id, "pompe_urgente", "no", "sí")
        crear_registro_de_cambio(Entidad.SAMPLE_SET, 77, "muestra", None, "M-1")
        db.session.commit()
        return {
            "paciente_id": paciente.id,
            "estudio_id": estudio.id,
            "codigo": estudio.codigo,
            "medico": paciente.medico_tratante.usuario_id,
            "ajeno": ajeno.id,
            "paciente": paciente.usuario_id,
        }


def test_el_historial_de_un_paciente_muestra_fecha_argentina_usuario_y_valores(client, caso):
    _entrar_como(client, caso["medico"])

    respuesta = client.get(f"/auditoria/paciente/{caso['paciente_id']}")

    assert respuesta.status_code == 200
    assert "09/11/2026 23:30" in respuesta.text
    assert "Fecha nacimiento" in respuesta.text
    assert "2000-01-01" in respuesta.text
    assert "2001-02-03" in respuesta.text
    assert "De Test" in respuesta.text


def test_el_historial_de_un_estudio_trae_los_cambios_de_estado(client, caso):
    _entrar_como(client, caso["medico"])

    respuesta = client.get(f"/auditoria/estudio/{caso['estudio_id']}")

    assert respuesta.status_code == 200
    assert caso["codigo"] in respuesta.text
    assert "Pompe urgente" in respuesta.text
    assert "Cambio de estado" in respuesta.text
    assert "Creado" in respuesta.text


def test_quien_ve_cada_historial(app, client, caso, usuario_rapido):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        administrador = usuario_rapido(roles.ADMINISTRADOR_GENERAL)
        db.session.commit()
        administrativo, administrador = administrativo.id, administrador.id
    paciente = f"/auditoria/paciente/{caso['paciente_id']}"
    estudio = f"/auditoria/estudio/{caso['estudio_id']}"
    sample_set = "/auditoria/sample_set/77"
    esperado = {
        # (usuario, paciente, estudio, sample set)
        "medico": (caso["medico"], 200, 200, 404),
        "medico ajeno": (caso["ajeno"], 404, 404, 404),
        "administrativo": (administrativo, 404, 200, 200),
        "administrador": (administrador, 200, 200, 200),
    }

    for nombre, (usuario, en_paciente, en_estudio, en_sample_set) in esperado.items():
        _entrar_como(client, usuario)
        resultados = (
            client.get(paciente).status_code,
            client.get(estudio).status_code,
            client.get(sample_set).status_code,
        )
        assert resultados == (en_paciente, en_estudio, en_sample_set), nombre


@pytest.mark.parametrize(
    "rol", [roles.PACIENTE, roles.BIOINFORMATICO, roles.TRANSPORTISTA, roles.GERENTE_MEDICO]
)
def test_los_demas_roles_no_entran_a_ningun_historial(client, login_como, caso, rol):
    login_como(rol)

    for ruta in (
        f"/auditoria/paciente/{caso['paciente_id']}",
        f"/auditoria/estudio/{caso['estudio_id']}",
        "/auditoria/sample_set/77",
    ):
        assert client.get(ruta).status_code == 403


def test_el_paciente_no_ve_su_propio_historial(client, caso):
    _entrar_como(client, caso["paciente"])

    assert client.get(f"/auditoria/paciente/{caso['paciente_id']}").status_code == 403
    assert client.get(f"/auditoria/estudio/{caso['estudio_id']}").status_code == 403


def test_lo_que_no_existe_responde_404(client, login_como):
    login_como(roles.ADMINISTRADOR_GENERAL)

    assert client.get("/auditoria/paciente/999999").status_code == 404
    assert client.get("/auditoria/estudio/999999").status_code == 404
    # Un sample set sin cambios registrados todavía no existe para el registro.
    assert client.get("/auditoria/sample_set/999999").status_code == 404
    assert client.get("/auditoria/usuario/1").status_code == 404
    assert client.get("/auditoria/estudio/abc").status_code == 404


def test_un_estudio_sin_cambios_de_datos_muestra_sus_estados(
    app, client, login_como, crear_estudio
):
    login_como(roles.ADMINISTRADOR_GENERAL)
    with app.app_context():
        estudio_id = crear_estudio().id

    respuesta = client.get(f"/auditoria/estudio/{estudio_id}")

    assert respuesta.status_code == 200
    assert "Cambio de estado" in respuesta.text
    assert "Todavía no hay cambios" not in respuesta.text


def test_un_paciente_sin_cambios_lo_dice(app, client, login_como, crear_paciente):
    login_como(roles.ADMINISTRADOR_GENERAL)
    with app.app_context():
        paciente_id = crear_paciente().id
        db.session.commit()

    assert "Todavía no hay cambios" in client.get(f"/auditoria/paciente/{paciente_id}").text
