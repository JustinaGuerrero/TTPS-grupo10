"""E27 Solicitar nueva extracción, E32 Cargar datos crudos y E33 Tomar estudio.

Los datos crudos van al Storage de mentira (STORAGE_CARPETA_MOCK en una carpeta temporal).
"""

from datetime import datetime, timedelta
from io import BytesIO

import pytest
import sqlalchemy as sa

from src.core.analisis import (
    ErrorDeAnalisis,
    cargar_datos_crudos,
    pendientes,
    tomar,
    validar_datos_crudos,
)
from src.core.auditoria import RegistroDeCambio
from src.core.calendario import ZONA_HORARIA
from src.core.database import db
from src.core.estudios import EstadoEstudio, Estudio, HistorialEstado
from src.core.muestras import MotivoInsuficiente, Muestra
from src.core.muestras.nueva_extraccion import (
    ErrorDeNuevaExtraccion,
    solicitar_nueva_extraccion,
)
from src.core.notificaciones import Aviso
from src.core.turnos import puede_reservar
from src.core.usuarios import roles

DATOS = b"ACGTACGTTAGC\nGGCATTACGATC\n"


@pytest.fixture(autouse=True)
def storage_en_tmp(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)


@pytest.fixture
def en_viaje(crear_estudio, crear_muestra):
    """`en_viaje()`: un estudio En viaje a Corea con su muestra tomada."""

    def _crear(estado=EstadoEstudio.EN_VIAJE_COREA) -> Estudio:
        estudio = crear_estudio(estado)
        crear_muestra(estudio)
        db.session.commit()
        return estudio

    return _crear


@pytest.fixture
def disponible(crear_estudio):
    """`disponible(hace=horas, pompe=False)`: un estudio con datos crudos, esperando que lo tomen."""

    def _crear(hace: int = 1, pompe: bool = False) -> Estudio:
        estudio = crear_estudio(EstadoEstudio.EN_AREA_BIOINFORMATICA)
        estudio.pompe_urgente = pompe
        estudio.analisis_actual.disponible_en = datetime(
            2026, 11, 17, 12, tzinfo=ZONA_HORARIA
        ) - timedelta(hours=hace)
        db.session.commit()
        return estudio

    return _crear


def _avisos_de(usuario):
    return db.session.scalars(sa.select(Aviso).where(Aviso.usuario_id == usuario.id)).all()


def _estado(estudio_id):
    db.session.expire_all()
    return db.session.get(Estudio, estudio_id).estado


def _ultimo_historial(estudio):
    return db.session.scalars(
        sa.select(HistorialEstado)
        .where(HistorialEstado.estudio_id == estudio.id)
        .order_by(HistorialEstado.id.desc())
    ).first()


def _registros(estudio, campo):
    return db.session.scalars(
        sa.select(RegistroDeCambio).where(
            RegistroDeCambio.entidad_id == estudio.id, RegistroDeCambio.campo == campo
        )
    ).all()


def _entrar_como(client, usuario):
    with client.session_transaction() as sesion:
        sesion["usuario_id"] = usuario.id


# --- E32 Cargar datos crudos ---


def test_cargar_datos_crudos_pasa_al_area_de_bioinformatica_y_avisa(
    app, en_viaje, usuario_rapido, tmp_path
):
    with app.app_context():
        bioinformaticos = [usuario_rapido(roles.BIOINFORMATICO) for _ in range(2)]
        inactivo = usuario_rapido(roles.BIOINFORMATICO)
        inactivo.activo = False
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        estudio = en_viaje()

        analisis = cargar_datos_crudos(estudio, administrativo, DATOS)
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.EN_AREA_BIOINFORMATICA
        assert (tmp_path / estudio.datos_crudos_path).read_bytes() == DATOS
        assert estudio.datos_crudos_cargados_por == administrativo.id
        assert estudio.datos_crudos_cargados_en is not None
        assert analisis.disponible_en == estudio.datos_crudos_cargados_en
        for bioinformatico in bioinformaticos:
            (aviso,) = _avisos_de(bioinformatico)
            assert aviso.link == "/bioinformatica/pendientes"
            assert estudio.codigo in aviso.mensaje
        assert _avisos_de(inactivo) == []
        (registro,) = _registros(estudio, "datos_crudos_path")
        assert registro.usuario_id == administrativo.id


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        pytest.param(b"ACGTX\n", "solo A, C, T, G", id="con una X"),
        pytest.param(b"acgt\n", "solo A, C, T, G", id="en minúscula"),
        pytest.param(b"ACGT ACGT", "solo A, C, T, G", id="con espacios"),
        pytest.param(b"", "vacío", id="vacío"),
        pytest.param(b"\n\n", "vacío", id="solo saltos de línea"),
        pytest.param(b"A" * (20 * 1024 * 1024 + 1), "20 MB", id="más de 20 MB"),
    ],
)
def test_los_datos_crudos_invalidos_se_rechazan(contenido, mensaje):
    with pytest.raises(ErrorDeAnalisis, match=mensaje):
        validar_datos_crudos(contenido)


def test_los_datos_crudos_aceptan_saltos_de_linea_de_windows():
    validar_datos_crudos(b"ACGT\r\nTTGA\r\n")


@pytest.mark.parametrize(
    "estado", [EstadoEstudio.PENDIENTE_ENVIO, EstadoEstudio.EN_AREA_BIOINFORMATICA]
)
def test_los_datos_crudos_solo_se_cargan_en_viaje_a_corea(app, en_viaje, usuario_rapido, estado):
    with app.app_context():
        estudio = en_viaje(estado)

        with pytest.raises(ErrorDeAnalisis, match="En viaje a Corea"):
            cargar_datos_crudos(estudio, usuario_rapido(roles.ADMINISTRATIVO), DATOS)


def test_solo_un_administrativo_carga_los_datos_crudos(app, en_viaje, usuario_rapido):
    with app.app_context():
        estudio = en_viaje()

        with pytest.raises(ErrorDeAnalisis, match="administrativo"):
            cargar_datos_crudos(estudio, usuario_rapido(roles.BIOINFORMATICO), DATOS)


# --- E27 Solicitar nueva extracción ---


@pytest.mark.parametrize("motivo", ["adn", "volumen"])
def test_la_muestra_que_no_sirve_pide_una_nueva_extraccion(app, en_viaje, usuario_rapido, motivo):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        estudio = en_viaje()
        muestra = db.session.scalars(
            sa.select(Muestra).where(Muestra.estudio_id == estudio.id)
        ).one()

        solicitar_nueva_extraccion(muestra, motivo, administrativo, "Informe del 17/11")
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.REQUIERE_NUEVA_EXTRACCION
        muestra = db.session.get(Muestra, muestra.id)
        assert muestra.insuficiente_motivo == MotivoInsuficiente(motivo)
        assert muestra.insuficiente_en is not None
        historial = _ultimo_historial(estudio)
        assert historial.usuario_id == administrativo.id
        assert historial.motivo.endswith(": Informe del 17/11")
        (aviso_al_paciente,) = _avisos_de(estudio.paciente.usuario)
        assert aviso_al_paciente.link == "/turnos/mio"
        (aviso_al_medico,) = _avisos_de(estudio.medico_tratante.usuario)
        assert aviso_al_medico.link == f"/historial/estudios/{estudio.id}"
        (registro,) = _registros(estudio, "muestra_insuficiente")
        assert registro.valor_nuevo == motivo
        # Reserva un turno nuevo sin volver a pagar (E27.4).
        assert puede_reservar(db.session.get(Estudio, estudio.id))


def test_con_otro_motivo_la_muestra_no_se_marca_pero_queda_el_motivo(app, en_viaje, usuario_rapido):
    with app.app_context():
        estudio = en_viaje()
        muestra = db.session.scalars(
            sa.select(Muestra).where(Muestra.estudio_id == estudio.id)
        ).one()

        solicitar_nueva_extraccion(
            muestra, "otro", usuario_rapido(roles.ADMINISTRATIVO), "Tubo roto en el viaje"
        )
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.REQUIERE_NUEVA_EXTRACCION
        assert db.session.get(Muestra, muestra.id).insuficiente_motivo is None
        assert _ultimo_historial(estudio).motivo == "Otro motivo: Tubo roto en el viaje"


@pytest.mark.parametrize(
    "estado",
    [EstadoEstudio.EN_LABORATORIO_CENTRAL, EstadoEstudio.EN_AREA_BIOINFORMATICA],
)
def test_la_nueva_extraccion_solo_se_pide_en_viaje_a_corea(app, en_viaje, usuario_rapido, estado):
    with app.app_context():
        estudio = en_viaje(estado)
        muestra = db.session.scalars(
            sa.select(Muestra).where(Muestra.estudio_id == estudio.id)
        ).one()

        with pytest.raises(ErrorDeNuevaExtraccion, match="En viaje a Corea"):
            solicitar_nueva_extraccion(muestra, "volumen", usuario_rapido(roles.ADMINISTRATIVO))
        assert muestra.insuficiente_motivo is None


def test_la_nueva_extraccion_necesita_un_motivo_valido(app, en_viaje, usuario_rapido):
    with app.app_context():
        estudio = en_viaje()
        muestra = db.session.scalars(
            sa.select(Muestra).where(Muestra.estudio_id == estudio.id)
        ).one()

        with pytest.raises(ErrorDeNuevaExtraccion, match="motivo"):
            solicitar_nueva_extraccion(muestra, "cualquiera", usuario_rapido(roles.ADMINISTRATIVO))


# --- E33 Lista de pendientes y toma ---


def test_la_lista_pone_primero_los_pompe_urgentes(app, disponible, usuario_rapido):
    with app.app_context():
        comun_viejo = disponible(hace=48)
        pompe_reciente = disponible(hace=1, pompe=True)
        comun_nuevo = disponible(hace=2)
        tomado = disponible(hace=72)
        bioinformatico = usuario_rapido(roles.BIOINFORMATICO)
        db.session.flush()
        tomado.analisis_actual.bioinformatico_id = bioinformatico.id
        sin_datos = disponible()
        sin_datos.analisis_actual.disponible_en = None
        db.session.commit()

        assert [a.estudio_id for a in pendientes()] == [
            pompe_reciente.id,
            comun_viejo.id,
            comun_nuevo.id,
        ]


def test_tomar_pasa_a_en_analisis_y_el_segundo_no_puede(app, disponible, usuario_rapido):
    with app.app_context():
        primero = usuario_rapido(roles.BIOINFORMATICO)
        segundo = usuario_rapido(roles.BIOINFORMATICO)
        estudio = disponible()
        db.session.flush()

        analisis = tomar(estudio.analisis_actual, primero)
        db.session.commit()

        assert _estado(estudio.id) == EstadoEstudio.EN_ANALISIS
        assert analisis.bioinformatico_id == primero.id
        assert analisis.tomado_en is not None
        assert pendientes() == []
        (registro,) = _registros(estudio, "bioinformatico")
        assert registro.usuario_id == primero.id
        with pytest.raises(ErrorDeAnalisis):
            tomar(db.session.get(Estudio, estudio.id).analisis_actual, segundo)


def test_si_otro_lo_toma_a_la_vez_el_update_no_pisa(app, disponible, usuario_rapido):
    with app.app_context():
        primero = usuario_rapido(roles.BIOINFORMATICO)
        segundo = usuario_rapido(roles.BIOINFORMATICO)
        estudio = disponible()
        db.session.flush()
        # Otro bioinformático lo tomó en otra transacción: el estudio sigue En área de
        # bioinformática en la sesión, pero la fila ya tiene bioinformatico_id.
        db.session.execute(
            sa.text("update analisis set bioinformatico_id = :id where id = :analisis"),
            {"id": primero.id, "analisis": estudio.analisis_actual.id},
        )

        with pytest.raises(ErrorDeAnalisis, match="ya lo tomó otro"):
            tomar(estudio.analisis_actual, segundo)


def test_solo_un_bioinformatico_toma(app, disponible, usuario_rapido):
    with app.app_context():
        estudio = disponible()

        with pytest.raises(ErrorDeAnalisis, match="bioinformático"):
            tomar(estudio.analisis_actual, usuario_rapido(roles.ADMINISTRATIVO))


# --- Pantallas ---


def test_el_administrativo_carga_los_datos_crudos_desde_la_lista(
    app, client, en_viaje, usuario_rapido
):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        estudio = en_viaje()
        estudio_id, codigo = estudio.id, estudio.codigo
        _entrar_como(client, administrativo)

    assert codigo in client.get("/datos-crudos").text

    invalido = client.post(
        f"/estudios/{estudio_id}/datos-crudos",
        data={"datos_crudos": (BytesIO(b"ACGTX"), "datos.txt")},
        content_type="multipart/form-data",
    )
    assert invalido.status_code == 400
    assert "solo A, C, T, G" in invalido.text
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.EN_VIAJE_COREA

    valido = client.post(
        f"/estudios/{estudio_id}/datos-crudos",
        data={"datos_crudos": (BytesIO(DATOS), "datos.txt")},
        content_type="multipart/form-data",
    )
    assert valido.status_code == 302
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.EN_AREA_BIOINFORMATICA


def test_el_administrativo_pide_la_nueva_extraccion_desde_la_lista(
    app, client, en_viaje, usuario_rapido
):
    with app.app_context():
        administrativo = usuario_rapido(roles.ADMINISTRATIVO)
        estudio = en_viaje()
        estudio_id = estudio.id
        _entrar_como(client, administrativo)

    respuesta = client.post(
        f"/estudios/{estudio_id}/nueva-extraccion", data={"motivo": "adn", "detalle": ""}
    )

    assert respuesta.status_code == 302
    with app.app_context():
        assert _estado(estudio_id) == EstadoEstudio.REQUIERE_NUEVA_EXTRACCION
        assert _ultimo_historial(db.session.get(Estudio, estudio_id)).motivo == "ADN insuficiente"


def test_el_bioinformatico_toma_desde_la_lista_y_lo_ve_en_mis_analisis(
    app, client, disponible, usuario_rapido
):
    with app.app_context():
        bioinformatico = usuario_rapido(roles.BIOINFORMATICO)
        otro = usuario_rapido(roles.BIOINFORMATICO)
        estudio = disponible(pompe=True)
        analisis_id, codigo = estudio.analisis_actual.id, estudio.codigo
        otro_id = otro.id
        _entrar_como(client, bioinformatico)

    lista = client.get("/bioinformatica/pendientes")
    assert codigo in lista.text
    assert "Pompe urgente" in lista.text

    respuesta = client.post(f"/bioinformatica/analisis/{analisis_id}/tomar")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/bioinformatica/mis-analisis")
    assert codigo in client.get("/bioinformatica/mis-analisis").text

    with client.session_transaction() as sesion:
        sesion["usuario_id"] = otro_id
    assert 'id="sin-pendientes"' in client.get("/bioinformatica/pendientes").text
    client.post(f"/bioinformatica/analisis/{analisis_id}/tomar")
    assert "no está en la lista de pendientes" in client.get("/bioinformatica/pendientes").text


def test_el_paciente_no_entra_a_los_pendientes(login_como):
    assert login_como(roles.PACIENTE).get("/bioinformatica/pendientes").status_code == 403


def test_el_administrativo_no_toma_estudios(app, disponible, login_como):
    with app.app_context():
        analisis_id = disponible().analisis_actual.id
    cliente = login_como(roles.ADMINISTRATIVO)

    assert cliente.post(f"/bioinformatica/analisis/{analisis_id}/tomar").status_code == 403


def test_el_bioinformatico_no_carga_datos_crudos(login_como):
    assert login_como(roles.BIOINFORMATICO).get("/datos-crudos").status_code == 403


def test_los_menus_del_area(login_como):
    assert "Para analizar" in login_como(roles.BIOINFORMATICO).get("/").text


def test_el_menu_del_administrativo_tiene_datos_crudos(login_como):
    assert "Datos crudos" in login_como(roles.ADMINISTRATIVO).get("/").text


# --- flask demo ---


def test_los_datos_de_demo_dejan_el_estudio_disponible_y_tomado(app, crear_estudio, usuario_rapido):
    from src.core.demo import DATOS_POR_ESTADO

    with app.app_context():
        # Los usuarios de prueba que usa `flask demo` (los crea `flask seeds`).
        usuario_rapido(roles.ADMINISTRATIVO).email = "administrativo@exoma.test"
        usuario_rapido(roles.BIOINFORMATICO).email = "bioinformatico@exoma.test"
        estudio = crear_estudio(EstadoEstudio.EN_VIAJE_COREA)

        DATOS_POR_ESTADO[EstadoEstudio.EN_AREA_BIOINFORMATICA](estudio)
        assert estudio.datos_crudos_path is not None
        assert estudio.analisis_actual.disponible_en is not None

        DATOS_POR_ESTADO[EstadoEstudio.EN_ANALISIS](estudio)
        assert estudio.analisis_actual.bioinformatico_id is not None
