// Buscador de términos SNOMED (E07.1 a E07.5). Espera que la URL devuelva [{codigo, termino}].
(() => {
  "use strict";

  const ESPERA_MS = 300;
  const MINIMO = 3;

  function iniciar(contenedor) {
    const entrada = contenedor.querySelector("input[type=search]");
    const resultados = contenedor.querySelector("[data-resultados]");
    const estado = contenedor.querySelector("[data-estado]");
    const elegidos = contenedor.querySelector("[data-elegidos]");
    const { url, nombre } = contenedor.dataset;
    const multiple = contenedor.dataset.multiple === "true";
    let temporizador = null;
    let pedido = null;

    const codigosElegidos = () =>
      new Set([...elegidos.querySelectorAll("[data-codigo]")].map((li) => li.dataset.codigo));

    function limpiar() {
      resultados.replaceChildren();
    }

    function crearChip(codigo, termino) {
      const li = document.createElement("li");
      li.className = "badge text-bg-primary fs-6 fw-normal d-inline-flex align-items-center gap-2";
      li.dataset.codigo = codigo;
      li.append(termino);

      const oculto = document.createElement("input");
      oculto.type = "hidden";
      oculto.name = nombre;
      oculto.value = `${codigo}|${termino}`;

      const quitar = document.createElement("button");
      quitar.type = "button";
      quitar.className = "btn-close btn-close-white";
      quitar.dataset.quitar = "";
      quitar.setAttribute("aria-label", `Quitar ${termino}`);

      li.append(oculto, quitar);
      return li;
    }

    function elegir(termino) {
      if (!multiple) elegidos.replaceChildren();
      if (!codigosElegidos().has(termino.codigo)) {
        elegidos.append(crearChip(termino.codigo, termino.termino));
      }
      entrada.value = "";
      limpiar();
      estado.textContent = `Se agregó ${termino.termino}.`;
      entrada.focus();
    }

    function mostrar(terminos) {
      limpiar();
      const ya = codigosElegidos();
      const nuevos = terminos.filter((t) => !ya.has(t.codigo));
      if (nuevos.length === 0) {
        estado.textContent = "No se encontraron términos.";
        const vacio = document.createElement("div");
        vacio.className = "list-group-item text-body-secondary";
        vacio.textContent = "No se encontraron términos.";
        resultados.append(vacio);
        return;
      }
      estado.textContent = `${nuevos.length} resultado${nuevos.length === 1 ? "" : "s"}.`;
      for (const termino of nuevos) {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "list-group-item list-group-item-action";
        boton.textContent = termino.termino;
        boton.addEventListener("click", () => elegir(termino));
        resultados.append(boton);
      }
    }

    async function buscar(texto) {
      if (pedido) pedido.abort();
      pedido = new AbortController();
      try {
        const respuesta = await fetch(`${url}?q=${encodeURIComponent(texto)}`, {
          headers: { Accept: "application/json" },
          signal: pedido.signal,
        });
        if (!respuesta.ok) throw new Error(String(respuesta.status));
        mostrar(await respuesta.json());
      } catch (error) {
        if (error.name === "AbortError") return;
        limpiar();
        estado.textContent = "No se pudo consultar SNOMED. Probá de nuevo.";
        const aviso = document.createElement("div");
        aviso.className = "list-group-item text-danger";
        aviso.textContent = "No se pudo consultar SNOMED. Probá de nuevo.";
        resultados.append(aviso);
      }
    }

    entrada.addEventListener("input", () => {
      clearTimeout(temporizador);
      const texto = entrada.value.trim();
      if (texto.length < MINIMO) {
        if (pedido) pedido.abort();
        limpiar();
        return;
      }
      temporizador = setTimeout(() => buscar(texto), ESPERA_MS);
    });

    entrada.addEventListener("keydown", (evento) => {
      // Enter no debe enviar el formulario mientras se está buscando.
      if (evento.key === "Enter") evento.preventDefault();
      if (evento.key === "Escape") limpiar();
    });

    elegidos.addEventListener("click", (evento) => {
      const quitar = evento.target.closest("[data-quitar]");
      if (!quitar) return;
      quitar.closest("li").remove();
      entrada.focus();
    });
  }

  document.querySelectorAll("[data-buscador]").forEach(iniciar);
})();