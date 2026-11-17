"""Comandos de consola de la app (desde sistema/):

- `poetry run flask seeds`: un usuario de prueba por rol, con sus perfiles y el estudio del paciente.
- `poetry run flask demo <estado>`: un paciente de demo nuevo con su estudio en ese estado.
- `poetry run flask migrar-local`: aplica supabase/migrations a la base de DATABASE_URL_LOCAL.
- `poetry run flask tarea <id>`: corre ya una tarea programada de src/web/tareas.py.
- `poetry run flask bot simular <chat_id> <texto>`: simula un mensaje al bot de mensajería (E22).
"""

import os

import click
import sqlalchemy as sa
from flask import Flask, current_app

from src.core import demo, migraciones, muestras, seeds
from src.core.database import db
from src.core.estudios import EstadoEstudio
from src.web import tareas


def registrar(app: Flask) -> None:
    @app.cli.command("seeds")
    def cargar_seeds():
        """Carga un usuario de prueba por rol del LEL, sus perfiles y el estudio del paciente."""
        contrasena = _contrasena_de_seeds()
        for email, rol, creado in seeds.cargar_usuarios_de_prueba(contrasena):
            estado = "creado    " if creado else "ya existía"
            click.echo(f"{estado}  {rol:<22} {email}")
        click.echo("Los usuarios creados entran con la contraseña de SEEDS_CONTRASENA.")

    @app.cli.command("demo")
    @click.argument("estado", type=click.Choice([estado.value for estado in EstadoEstudio]))
    def crear_demo(estado: str):
        """Crea un paciente de demo con su estudio en ESTADO, para probar a mano."""
        contrasena = _contrasena_de_seeds()
        try:
            estudio = demo.crear_paciente_de_demo(estado, contrasena)
        except demo.DemoImposible as error:
            db.session.rollback()
            raise click.ClickException(str(error)) from None
        db.session.commit()
        email = estudio.paciente.usuario.email
        click.echo(f"Estudio {estudio.codigo} en {estudio.estado.nombre}.")
        click.echo(f"Paciente: {email} (contraseña de SEEDS_CONTRASENA).")
        click.echo(f"Médico tratante: {demo.MEDICO_DE_DEMO}.")

    @app.cli.command("migrar-local")
    @click.option("--si", is_flag=True, help="No pide confirmación.")
    def migrar_local(si: bool):
        """Borra el esquema public de DATABASE_URL_LOCAL y le aplica supabase/migrations."""
        url = os.getenv("DATABASE_URL_LOCAL")
        if not url:
            raise click.ClickException(
                "Falta DATABASE_URL_LOCAL: la base local donde probar (ver .env.example)."
            )
        motivo = migraciones.motivo_para_no_borrar(url, os.getenv("DATABASE_URL"))
        if motivo:
            raise click.ClickException(
                f"No se migra DATABASE_URL_LOCAL: {motivo}. Este comando borra el esquema public; "
                "las migraciones de Supabase las aplica una persona con `npx supabase db push`."
            )
        sin_clave = sa.make_url(url).render_as_string(hide_password=True)
        if not si:
            click.confirm(f"Se borran todos los datos de {sin_clave}. ¿Seguir?", abort=True)
        try:
            if migraciones.crear_base_si_falta(url):
                click.echo(f"Base creada: {sin_clave}")
            aplicadas = migraciones.aplicar_migraciones(url)
        except sa.exc.OperationalError as error:
            raise click.ClickException(f"No se pudo conectar a {sin_clave}: {error.orig}") from None
        except migraciones.MigracionFallida as error:
            raise click.ClickException(str(error)) from None
        for nombre in aplicadas:
            click.echo(f"aplicada  {nombre}")
        click.echo("Listo. Ahora: `flask seeds` y, si hace falta, `flask demo <estado>`.")

    @app.cli.command("tarea")
    @click.argument("tarea_id")
    def correr_tarea(tarea_id: str):
        """Corre ya la tarea programada TAREA_ID, sin esperar su hora (para probar a mano)."""
        tarea = tareas.buscar_tarea(tarea_id)
        if tarea is None:
            disponibles = ", ".join(t.id for t in tareas.TAREAS) or "ninguna"
            raise click.ClickException(f"No existe la tarea {tarea_id!r}. Tareas: {disponibles}.")
        resultado = tareas.ejecutar(current_app._get_current_object(), tarea)
        click.echo(f"Tarea {tarea.id}: {resultado}")

    @app.cli.group("bot")
    def bot():
        """Bot de mensajería de los centros de extracción (E22)."""

    @bot.command("simular")
    @click.argument("chat_id")
    @click.argument("texto")
    def simular(chat_id: str, texto: str):
        """Procesa TEXTO como si el chat CHAT_ID lo mandara al bot, sin pasar por Telegram.

        Ejemplo: flask bot simular 1000001 "Muestra tomada EX-2026-00042". Los chats de los
        centros de prueba son los de `flask seeds` (1000001 a 1000010).
        """
        update = muestras.update_simulado(chat_id, texto)
        resultado = muestras.registrar_toma(update)
        db.session.commit()
        mensaje = resultado.mensaje
        if mensaje.error:
            click.echo(f"Mensaje {mensaje.id} guardado con error: {mensaje.error}")
        else:
            click.echo(
                f"Mensaje {mensaje.id} procesado: estudio {mensaje.estudio.codigo} en "
                f"{mensaje.estudio.estado.nombre}."
            )
        click.echo(f"Respuesta al centro: {resultado.respuesta or '(ninguna)'}")


def _contrasena_de_seeds() -> str:
    contrasena = current_app.config.get("SEEDS_CONTRASENA")
    if not contrasena:
        raise click.ClickException(
            "Falta SEEDS_CONTRASENA: es la contraseña de los usuarios de prueba (ver .env.example)."
        )
    return contrasena
