"""integraciones/storage.py: archivos en Supabase Storage, con mock en disco (USE_MOCKS=1)."""

import httpx
import pytest
from storage3.exceptions import StorageApiError

from src.integraciones import storage
from src.integraciones.base import ErrorDeIntegracion


@pytest.fixture
def con_mock(app, tmp_path):
    app.config["STORAGE_CARPETA_MOCK"] = str(tmp_path)
    with app.app_context():
        yield tmp_path


def test_con_mock_sube_y_baja_el_archivo_en_disco(con_mock):
    ruta = storage.subir("estudios/42/resultado.pdf", b"%PDF-1.4 prueba")

    assert ruta == "estudios/42/resultado.pdf"
    assert (con_mock / "estudios" / "42" / "resultado.pdf").read_bytes() == b"%PDF-1.4 prueba"
    assert storage.bajar(ruta) == b"%PDF-1.4 prueba"


def test_no_pisa_un_archivo_salvo_que_se_pida(con_mock):
    storage.subir("a.pdf", b"uno")

    with pytest.raises(ErrorDeIntegracion, match="Ya hay un archivo en a.pdf"):
        storage.subir("a.pdf", b"dos")
    storage.subir("a.pdf", b"dos", reemplazar=True)

    assert storage.bajar("a.pdf") == b"dos"


def test_bajar_un_archivo_que_no_existe_da_un_error_legible(con_mock):
    with pytest.raises(ErrorDeIntegracion) as error:
        storage.bajar("estudios/no-existe.pdf")

    assert error.value.mensaje == "No existe el archivo estudios/no-existe.pdf."
    assert error.value.status == 404


@pytest.mark.parametrize(
    "ruta", ["", "/absoluta.pdf", "../afuera.pdf", "a/../../b.pdf", "a\\b.pdf", "a//b.pdf", "á.pdf"]
)
def test_rechaza_rutas_que_podrian_salirse_de_la_carpeta(con_mock, ruta):
    with pytest.raises(ValueError, match="Ruta de archivo inválida"):
        storage.subir(ruta, b"x")


# --- Sin mocks: se llama a Supabase con un timeout y las fallas se vuelven mensajes ---


class BucketFalso:
    def __init__(self, falla: Exception | None = None, contenido: bytes = b"") -> None:
        self.falla = falla
        self.contenido = contenido
        self.subidos: list[tuple[str, bytes, dict]] = []

    def upload(self, ruta, contenido, opciones):
        if self.falla:
            raise self.falla
        self.subidos.append((ruta, contenido, opciones))

    def download(self, ruta):
        if self.falla:
            raise self.falla
        return self.contenido


@pytest.fixture
def sin_mock(app, monkeypatch):
    """Configura storage sin mocks y devuelve una función para elegir el bucket falso."""
    app.config.update(
        USE_MOCKS=False,
        SUPABASE_URL="https://proyecto.supabase.co",
        SUPABASE_KEY="clave-de-test",
        SUPABASE_BUCKET="documentos",
    )
    creados = []

    def usar(bucket: BucketFalso) -> list:
        class ClienteFalso:
            class storage:
                @staticmethod
                def from_(nombre):
                    creados.append(nombre)
                    return bucket

        def create_client(url, clave, options):
            creados.append(options.storage_client_timeout)
            return ClienteFalso()

        monkeypatch.setattr(storage, "create_client", create_client)
        return creados

    with app.app_context():
        yield usar


def test_sin_mock_sube_al_bucket_con_timeout_de_5_segundos(sin_mock):
    bucket = BucketFalso()
    creados = sin_mock(bucket)

    storage.subir("estudios/1/orden.pdf", b"pdf")

    assert creados == [5, "documentos"]
    assert bucket.subidos == [
        ("estudios/1/orden.pdf", b"pdf", {"content-type": "application/pdf", "upsert": "false"})
    ]


def test_sin_mock_baja_del_bucket(sin_mock):
    sin_mock(BucketFalso(contenido=b"contenido"))

    assert storage.bajar("estudios/1/orden.pdf") == b"contenido"


@pytest.mark.parametrize(
    ("falla", "mensaje"),
    [
        (httpx.ReadTimeout("timed out"), "Supabase Storage no respondió a tiempo."),
        (httpx.ConnectError("sin red"), "No se pudo conectar con Supabase Storage."),
        (StorageApiError("Object not found", "not_found", 404), "No existe el archivo a.pdf."),
        (StorageApiError("Duplicate", "Duplicate", "409"), "Ya hay un archivo en a.pdf."),
        (StorageApiError("Unauthorized", "Unauthorized", 403), "rechazó la clave de acceso"),
        (StorageApiError("Error", "InternalError", 500), "respondió con un error"),
        (RuntimeError("algo raro"), "tuvo un error inesperado"),
    ],
)
def test_sin_mock_las_fallas_se_vuelven_un_mensaje_legible(sin_mock, falla, mensaje):
    sin_mock(BucketFalso(falla=falla))

    with pytest.raises(ErrorDeIntegracion, match=mensaje):
        storage.bajar("a.pdf")


def test_sin_configuracion_avisa_que_falta(app):
    app.config.update(USE_MOCKS=False, SUPABASE_URL=None, SUPABASE_KEY=None)
    with app.app_context(), pytest.raises(ErrorDeIntegracion, match="Falta configurar"):
        storage.subir("a.pdf", b"x")
