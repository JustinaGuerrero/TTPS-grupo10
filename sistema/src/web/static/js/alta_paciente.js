// Interacciones del alta clínica: familiares repetibles y dictado del resumen.
(() => {
  "use strict";

  const form = document.querySelector('form[action$="/pacientes/nuevo"], form[data-pacientes-alta]');
  if (!form) return;

  const familiares = form.querySelector("[data-familiares]");
  const plantilla = form.querySelector("[data-familiar-template]");
  const botonAgregar = form.querySelector("[data-agregar-familiar]");

  function renumerar() {
    familiares.querySelectorAll("[data-familiar]").forEach((fila, indice) => {
      fila.querySelectorAll("*").forEach((elemento) => {
        for (const atributo of ["id", "for"]) {
          if (elemento.hasAttribute(atributo)) {
            elemento.setAttribute(
              atributo,
              elemento.getAttribute(atributo).replace(/-\d+$/, `-${indice}`),
            );
          }
        }
        for (const atributo of ["name", "data-nombre"]) {
          if (elemento.hasAttribute(atributo)) {
            elemento.setAttribute(
              atributo,
              elemento
                .getAttribute(atributo)
                .replace(/familiares_sintomas_\d+$/, `familiares_sintomas_${indice}`)
                .replace(/familiares_patologias_\d+$/, `familiares_patologias_${indice}`),
            );
          }
        }
      });
    });
  }

  botonAgregar.addEventListener("click", () => {
    const fragmento = plantilla.content.cloneNode(true);
    const indice = familiares.querySelectorAll("[data-familiar]").length;
    fragmento.querySelectorAll("*").forEach((elemento) => {
      for (const atributo of ["id", "for", "name", "data-nombre"]) {
        if (elemento.hasAttribute(atributo)) {
          elemento.setAttribute(
            atributo,
            elemento.getAttribute(atributo).replaceAll("__INDICE__", String(indice)),
          );
        }
      }
    });
    familiares.append(fragmento);
    renumerar();
    const ultima = familiares.querySelector("[data-familiar]:last-child");
    if (ultima) {
      ultima.querySelector("select[name=familiares_parentesco]").focus();
    }
  });

  familiares.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-quitar-familiar]");
    if (!boton) return;
    boton.closest("[data-familiar]").remove();
    if (familiares.querySelectorAll("[data-familiar]").length === 0) {
      botonAgregar.click();
      const ultima = familiares.querySelector("[data-familiar]:last-child");
      if (ultima) ultima.querySelector("select[name=familiares_parentesco]").value = "";
    }
    renumerar();
  });

  const grabar = form.querySelector("[data-grabar]");
  const detener = form.querySelector("[data-detener]");
  const estado = form.querySelector("[data-transcripcion-estado]");
  const entradaAudio = form.querySelector("[data-audio]");
  const resumen = form.querySelector("#resumen_historia_clinica");

  if (!navigator.mediaDevices || !window.MediaRecorder) {
    grabar.disabled = true;
    estado.textContent = "La grabación no está disponible en este navegador; podés escribir el resumen.";
    return;
  }

  let grabador = null;
  let flujo = null;
  let fragmentos = [];

  grabar.addEventListener("click", async () => {
    try {
      flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
      fragmentos = [];
      grabador = new MediaRecorder(flujo);
      grabador.addEventListener("dataavailable", (evento) => {
        if (evento.data.size) fragmentos.push(evento.data);
      });
      grabador.addEventListener("stop", transcribirGrabacion, { once: true });
      grabador.start();
      grabar.disabled = true;
      detener.disabled = false;
      estado.textContent = "Grabando…";
    } catch {
      estado.textContent = "No se pudo acceder al micrófono. Podés escribir el resumen.";
    }
  });

  detener.addEventListener("click", () => {
    if (grabador && grabador.state !== "inactive") grabador.stop();
    if (flujo) flujo.getTracks().forEach((pista) => pista.stop());
    detener.disabled = true;
    grabar.disabled = false;
  });

  async function transcribirGrabacion() {
    const blob = new Blob(fragmentos, { type: grabador.mimeType || "audio/webm" });
    const archivo = new File([blob], "resumen.webm", { type: "audio/webm" });
    const transferencia = new DataTransfer();
    transferencia.items.add(archivo);
    entradaAudio.files = transferencia.files;
    estado.textContent = "Transcribiendo…";

    const datos = new FormData();
    datos.append("audio", archivo);
    const csrf = form.querySelector('[name="csrf_token"]').value;
    try {
      const respuesta = await fetch(form.dataset.urlTranscripcion, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, Accept: "application/json" },
        body: datos,
      });
      const resultado = await respuesta.json();
      if (!respuesta.ok) throw new Error(resultado.error || "No se pudo transcribir.");
      resumen.value = resultado.texto;
      estado.textContent = "Transcripción lista; podés corregir el texto antes de guardar.";
    } catch (error) {
      estado.textContent = `${error.message || "No se pudo transcribir."} Podés escribir el resumen.`;
    }
  }
})();
