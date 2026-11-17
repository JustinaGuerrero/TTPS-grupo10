"""E10 Dar de alta estudio: genes de Apigen, genes a mano, Pompe urgente, aviso y permisos."""

import itertools
import re
from datetime import date

import pytest
import sqlalchemy as sa

from src.core.auditoria import Accion, Entidad, RegistroDeCambio
from src.core.database import db
from src.core.estudios import (
    EstadoEstudio,
    Estudio,
    HistorialEstado,
)
from src.core.estudios.alta import dar_de_alta_estudio, es_pompe_urgente, genes_para
from src.core.estudios.analisis_patologias import AnalisisPatologia
from src.core.notificaciones import Aviso
from src.core.pacientes import DiagnosticoPresuntivo, ErrorDeValidacion, Paciente
from src.core.usuarios import Usuario, roles
from src.core.usuarios.modelos import Medico
from src.integraciones import apigen
from src.integraciones.base import ErrorDeIntegracion

HOY = date(2026, 11, 17)
ADULTO = date(1990, 5, 20)
BEBE_DE_3_MESES = date(2026, 8, 10)
BEBE_DE_5_MESES = date(2026, 6, 10)

numeros = itertools.count(1)


@pytest.fixture
def paciente_con(usuario_rapido, crear_paciente, crear_patologia):
    """Fábrica: `paciente_con("FABRY", fecha_nacimiento=...)` agrega un paciente con ese diagnóstico."""

    def _crear(*codigos: str, fecha_nacimiento: date = ADULTO) -> Paciente:
        paciente = crear_paciente(fecha_nacimiento=fecha_nacimiento)
        for codigo in codigos:
            patologia = crear_patologia()
            patologia.codigo_apigen = codigo
            paciente.diagnosticos_presuntivos.append(DiagnosticoPresuntivo(patologia=patologia))
        db.session.commit()
        return paciente

    return _crear


def _genes(estudio: Estudio) -> dict[str, bool]:
    return {g.gen_simbolo: g.agregado_a_mano for g in estudio.analisis[0].genes}


def test_fabry_crea_el_estudio_en_creado_con_sus_genes(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY")
        medico = paciente.medico_tratante.usuario

        estudio = dar_de_alta_estudio(paciente, medico, evalua_hallazgos_secundarios=True)
        db.session.commit()

        assert estudio.estado == EstadoEstudio.CREADO
        assert estudio.pompe_urgente is False
        assert _genes(estudio) == {"GLA": False}
        assert estudio.analisis[0].evalua_hallazgos_secundarios is True
        [analisis_patologia] = db.session.scalars(sa.select(AnalisisPatologia)).all()
        assert analisis_patologia.patologia.codigo_apigen == "FABRY"
        [primera] = estudio.historial
        assert primera.estado_nuevo == EstadoEstudio.CREADO
        assert primera.usuario_id == medico.id


def test_el_alta_queda_en_el_registro_de_cambios(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY")
        estudio = dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario)
        db.session.commit()

        campos = {
            fila.campo: fila.valor_nuevo
            for fila in db.session.scalars(
                sa.select(RegistroDeCambio).where(
                    RegistroDeCambio.entidad == Entidad.ESTUDIO,
                    RegistroDeCambio.entidad_id == estudio.id,
                    RegistroDeCambio.accion == Accion.ALTA,
                )
            )
        }
        assert campos["genes"] == "GLA"
        assert campos["pompe_urgente"] == "no"


def test_un_gen_a_mano_que_existe_en_apigen_queda_agregado_a_mano(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY")

        estudio = dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario, ["gab1"])

        assert _genes(estudio) == {"GLA": False, "GAB1": True}


def test_los_genes_no_se_repiten(app, paciente_con):
    with app.app_context():
        # GAA es el gen de Pompe y también lo agrega a mano, dos veces y con otras mayúsculas.
        paciente = paciente_con("POMPE")

        estudio = dar_de_alta_estudio(
            paciente, paciente.medico_tratante.usuario, ["GAA", "gaa", " GAA "]
        )

        assert _genes(estudio) == {"GAA": False}
        assert len(estudio.analisis[0].genes) == 1


def test_genes_para_junta_las_patologias_sin_repetir(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY", "POMPE")

        genes = genes_para([d.patologia for d in paciente.diagnosticos_presuntivos])

        assert genes == ["GAA", "GLA"]


def test_un_gen_que_no_existe_en_apigen_no_crea_nada(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY")

        with pytest.raises(ErrorDeValidacion) as error:
            dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario, ["GLA", "ZZZ9"])

        assert "ZZZ9" in error.value.errores["genes_a_mano"]
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Estudio)) == 0


@pytest.mark.parametrize(
    ("diagnostico", "nacimiento", "urgente"),
    [
        ("POMPE", BEBE_DE_3_MESES, True),
        ("POMPE", BEBE_DE_5_MESES, False),
        ("FABRY", BEBE_DE_3_MESES, False),
    ],
    ids=["pompe-menor-de-4-meses", "pompe-mayor-de-4-meses", "otra-patologia-menor-de-4-meses"],
)
def test_pompe_urgente(app, paciente_con, diagnostico, nacimiento, urgente):
    with app.app_context():
        paciente = paciente_con(diagnostico, fecha_nacimiento=nacimiento)

        estudio = dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario, hoy=HOY)

        assert estudio.pompe_urgente is urgente


def test_pompe_a_los_4_meses_exactos_ya_no_es_urgente(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("POMPE")
        patologias = [d.patologia for d in paciente.diagnosticos_presuntivos]

        assert es_pompe_urgente(patologias, date(2026, 7, 17), HOY) is False
        assert es_pompe_urgente(patologias, date(2026, 7, 18), HOY) is True


def test_el_segundo_estudio_del_paciente_se_rechaza(app, paciente_con):
    with app.app_context():
        paciente = paciente_con("FABRY")
        medico = paciente.medico_tratante.usuario
        dar_de_alta_estudio(paciente, medico)
        db.session.commit()

        with pytest.raises(ErrorDeValidacion) as error:
            dar_de_alta_estudio(paciente, medico)

        assert "ya tiene un estudio" in error.value.errores["paciente"]
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Estudio)) == 1


def test_si_apigen_falla_no_se_crea_nada(app, paciente_con, monkeypatch):
    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("Apigen", "Apigen no responde.")

    monkeypatch.setattr(apigen, "genes_de_patologia", caido)
    with app.app_context():
        paciente = paciente_con("FABRY")

        with pytest.raises(ErrorDeIntegracion):
            dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario)

        assert db.session.scalar(sa.select(sa.func.count()).select_from(Estudio)) == 0
        assert db.session.scalar(sa.select(sa.func.count()).select_from(HistorialEstado)) == 0
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Aviso)) == 0


def test_avisa_a_todos_los_administrativos_activos(app, paciente_con, usuario_rapido):
    with app.app_context():
        activos = [usuario_rapido(roles.ADMINISTRATIVO) for _ in range(2)]
        inactivo = usuario_rapido(roles.ADMINISTRATIVO)
        inactivo.activo = False
        otro_rol = usuario_rapido(roles.BIOINFORMATICO)
        paciente = paciente_con("FABRY")

        estudio = dar_de_alta_estudio(paciente, paciente.medico_tratante.usuario)
        db.session.commit()

        avisos = db.session.scalars(sa.select(Aviso)).all()
        assert {a.usuario_id for a in avisos} == {u.id for u in activos}
        assert inactivo.id not in {a.usuario_id for a in avisos}
        assert otro_rol.id not in {a.usuario_id for a in avisos}
        assert all(a.estudio_id == estudio.id for a in avisos)


def test_solo_un_medico_tratante_puede_dar_de_alta(app, paciente_con, usuario_rapido):
    with app.app_context():
        paciente = paciente_con("FABRY")

        with pytest.raises(ValueError, match="médico tratante"):
            dar_de_alta_estudio(paciente, usuario_rapido(roles.ADMINISTRATIVO))


# --- Pantallas y permisos -------------------------------------------------------------------


def _paciente_del(email: str, paciente_con, usuario_rapido) -> Paciente:
    medico = db.session.scalar(sa.select(Usuario).where(Usuario.email == email))
    paciente = paciente_con("FABRY")
    paciente.medico_tratante = db.session.get(Medico, medico.id)
    db.session.commit()
    return paciente


def _ingresar(email: str, autenticar_como) -> None:
    autenticar_como(email)


def test_el_medico_da_de_alta_desde_la_pantalla(
    app, client, crear_medico, paciente_con, usuario_rapido, autenticar_como
):
    email = crear_medico()
    with app.app_context():
        paciente = _paciente_del(email, paciente_con, usuario_rapido)
        paciente_id = paciente.id
    _ingresar(email, autenticar_como)

    pantalla = client.get(f"/estudios/nuevo/{paciente_id}")
    assert pantalla.status_code == 200
    assert "GLA" in pantalla.get_data(as_text=True)

    token = _token(client, f"/estudios/nuevo/{paciente_id}")
    respuesta = client.post(
        f"/estudios/nuevo/{paciente_id}",
        data={"csrf_token": token, "genes_a_mano": "GAB1", "evalua_hallazgos_secundarios": "on"},
    )

    assert respuesta.status_code == 302
    with app.app_context():
        estudio = db.session.scalar(sa.select(Estudio).where(Estudio.paciente_id == paciente_id))
        assert estudio.estado == EstadoEstudio.CREADO
        assert _genes(estudio) == {"GLA": False, "GAB1": True}


def _token(client, ruta: str) -> str:
    html = client.get(ruta).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_un_gen_inexistente_vuelve_al_formulario_con_el_error(
    app, client, crear_medico, paciente_con, usuario_rapido, autenticar_como
):
    email = crear_medico()
    with app.app_context():
        paciente_id = _paciente_del(email, paciente_con, usuario_rapido).id
    _ingresar(email, autenticar_como)

    respuesta = client.post(
        f"/estudios/nuevo/{paciente_id}",
        data={
            "csrf_token": _token(client, f"/estudios/nuevo/{paciente_id}"),
            "genes_a_mano": "ZZZ9",
        },
    )

    assert respuesta.status_code == 400
    assert "ZZZ9" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Estudio)) == 0


def test_con_apigen_caido_la_pantalla_avisa_y_no_crea_nada(
    app, client, crear_medico, paciente_con, usuario_rapido, monkeypatch, autenticar_como
):
    email = crear_medico()
    with app.app_context():
        paciente_id = _paciente_del(email, paciente_con, usuario_rapido).id
    _ingresar(email, autenticar_como)
    token = _token(client, f"/estudios/nuevo/{paciente_id}")

    def caido(*args, **kwargs):
        raise ErrorDeIntegracion("Apigen", "Apigen no responde.")

    monkeypatch.setattr(apigen, "genes_de_patologia", caido)
    respuesta = client.post(f"/estudios/nuevo/{paciente_id}", data={"csrf_token": token})

    assert respuesta.status_code == 503
    assert "Apigen no responde" in respuesta.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(sa.select(sa.func.count()).select_from(Estudio)) == 0


def test_los_botones_de_alta_estan_en_la_ficha_y_en_mis_pacientes(
    app, client, crear_medico, paciente_con, usuario_rapido, autenticar_como
):
    email = crear_medico()
    with app.app_context():
        paciente_id = _paciente_del(email, paciente_con, usuario_rapido).id
    _ingresar(email, autenticar_como)
    ruta = f"/estudios/nuevo/{paciente_id}"

    assert ruta in client.get(f"/pacientes/{paciente_id}").get_data(as_text=True)
    assert ruta in client.get("/pacientes").get_data(as_text=True)

    client.post(ruta, data={"csrf_token": _token(client, ruta)})

    assert ruta not in client.get(f"/pacientes/{paciente_id}").get_data(as_text=True)
    assert ruta not in client.get("/pacientes").get_data(as_text=True)
    assert client.get(ruta).status_code == 302


def test_el_paciente_de_otro_medico_responde_404(
    app, client, crear_medico, paciente_con, usuario_rapido, autenticar_como
):
    with app.app_context():
        paciente_id = paciente_con("FABRY").id
    _ingresar(crear_medico(), autenticar_como)

    assert client.get(f"/estudios/nuevo/{paciente_id}").status_code == 404
    assert client.post(f"/estudios/nuevo/{paciente_id}").status_code in (400, 404)


@pytest.mark.parametrize(
    "rol",
    [
        roles.PACIENTE,
        roles.ADMINISTRATIVO,
        roles.BIOINFORMATICO,
        roles.TRANSPORTISTA,
        roles.GERENTE_MEDICO,
        roles.ADMINISTRADOR_GENERAL,
    ],
)
def test_los_demas_roles_reciben_403(client, login_como, rol):
    login_como(rol)

    assert client.get("/estudios/nuevo/1").status_code == 403


def test_sin_sesion_redirige_al_login(client):
    respuesta = client.get("/estudios/nuevo/1")

    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]
