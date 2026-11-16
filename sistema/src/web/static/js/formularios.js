// Validación en el cliente y campos que dependen de otro, para los formularios con data-validar.
//
// Es una ayuda para quien completa el formulario: el servidor valida todo igual, y sin
// JavaScript el formulario funciona (se ven todos los campos y los errores llegan del servidor).
//
// - Antes de enviar, usa la validación del navegador (required, type, maxlength, pattern) y
//   muestra cada error con el estilo de Bootstrap en el .invalid-feedback del campo.
// - Un bloque con data-segun="rol_codigo" data-valores="a b" se muestra solo si el campo
//   rol_codigo vale a o b. Al ocultarse, sus campos se deshabilitan (no se envían); al
//   mostrarse, los que tienen data-requerido pasan a ser obligatorios.
(() => {
  "use strict";

  const CAMPOS = "input, select, textarea";

  function feedbackDe(campo) {
    return document.getElementById(`${campo.id}-error`);
  }

  function mostrarError(campo) {
    const feedback = feedbackDe(campo);
    const valido = campo.checkValidity();
    campo.classList.toggle("is-invalid", !valido);
    campo.toggleAttribute("aria-invalid", !valido);
    if (feedback && !valido) feedback.textContent = campo.validationMessage;
    return valido;
  }

  function actualizarDependientes(formulario) {
    formulario.querySelectorAll("[data-segun]").forEach((bloque) => {
      const control = formulario.elements[bloque.dataset.segun];
      const valores = (bloque.dataset.valores || "").split(/\s+/);
      const visible = Boolean(control) && valores.includes(control.value);
      bloque.classList.toggle("d-none", !visible);
      bloque.querySelectorAll(CAMPOS).forEach((campo) => {
        campo.disabled = !visible;
        if (campo.hasAttribute("data-requerido")) campo.required = visible;
      });
    });
  }

  function preparar(formulario) {
    actualizarDependientes(formulario);
    formulario.addEventListener("change", (evento) => {
      if (evento.target.name) actualizarDependientes(formulario);
    });

    // Un error (del servidor o del navegador) se va apenas el campo pasa a ser válido.
    formulario.addEventListener("input", (evento) => {
      const campo = evento.target;
      if (campo.classList.contains("is-invalid")) mostrarError(campo);
    });
    formulario.addEventListener("change", (evento) => {
      const campo = evento.target;
      if (campo.classList.contains("is-invalid")) mostrarError(campo);
    });

    formulario.addEventListener("submit", (evento) => {
      const campos = [...formulario.querySelectorAll(CAMPOS)].filter(
        (campo) => !campo.disabled && campo.willValidate,
      );
      const invalidos = campos.filter((campo) => !mostrarError(campo));
      if (invalidos.length > 0) {
        evento.preventDefault();
        invalidos[0].focus();
        return;
      }
      // Evita el doble envío, que daría de alta dos veces o mandaría dos mails.
      formulario.querySelectorAll("[type=submit]").forEach((boton) => {
        boton.disabled = true;
      });
    });
  }

  document.querySelectorAll("form[data-validar]").forEach(preparar);
})();
