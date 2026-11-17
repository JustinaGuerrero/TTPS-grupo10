// Mapas con Leaflet del macro templates/mapa/_mapa.html (E19, E25).
// Sin Leaflet o sin conexión, la página sigue andando: cada pantalla muestra también la lista.
(function () {
  "use strict";

  const mapas = {};

  if (typeof L !== "undefined") {
    document.querySelectorAll(".mapa[data-puntos]").forEach(function (div) {
      const puntos = JSON.parse(div.dataset.puntos || "[]");
      const mapa = L.map(div);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(mapa);
      const marcadores = puntos.map(function (punto) {
        return L.marker([punto.lat, punto.lon]).addTo(mapa).bindPopup(globo(punto));
      });
      if (marcadores.length) {
        mapa.fitBounds(L.featureGroup(marcadores).getBounds().pad(0.2));
      } else {
        mapa.setView([-38.4, -63.6], 4); // Argentina entera
      }
      mapas[div.id] = mapa;
    });
  }

  // Contenido del globo armado con nodos, no con HTML: los textos vienen de la base.
  function globo(punto) {
    const contenedor = document.createElement("div");
    const titulo = document.createElement("strong");
    titulo.textContent = punto.titulo;
    contenedor.appendChild(titulo);
    if (punto.texto) {
      contenedor.appendChild(document.createElement("br"));
      contenedor.appendChild(document.createTextNode(punto.texto));
    }
    if (punto.url) {
      const enlace = document.createElement("a");
      enlace.href = punto.url;
      enlace.textContent = punto.link || "Ver";
      enlace.className = "d-block mt-1";
      contenedor.appendChild(enlace);
    }
    return contenedor;
  }

  // E19.2: el paciente elige el centro más cercano. La ubicación no sale del navegador.
  document.querySelectorAll("[data-ubicarme]").forEach(function (boton) {
    const estado = document.getElementById(boton.dataset.estado || "");
    if (!navigator.geolocation) {
      boton.hidden = true;
      return;
    }
    boton.addEventListener("click", function () {
      if (estado) estado.textContent = "Buscando tu ubicación…";
      navigator.geolocation.getCurrentPosition(
        function (posicion) {
          const lat = posicion.coords.latitude;
          const lon = posicion.coords.longitude;
          const mapa = mapas[boton.dataset.ubicarme];
          if (mapa) {
            L.circleMarker([lat, lon], { radius: 8 }).addTo(mapa).bindPopup("Estás acá");
            mapa.setView([lat, lon], 11);
          }
          ordenarPorCercania(document.getElementById(boton.dataset.lista || ""), lat, lon);
          if (estado) estado.textContent = "Ordenamos los centros del más cercano al más lejano.";
        },
        function () {
          if (estado) estado.textContent = "No pudimos obtener tu ubicación.";
        },
        { timeout: 10000 }
      );
    });
  });

  function ordenarPorCercania(lista, lat, lon) {
    if (!lista) return;
    const items = Array.from(lista.querySelectorAll("[data-lat][data-lon]"));
    items.forEach(function (item) {
      item.dataset.km = kilometros(lat, lon, Number(item.dataset.lat), Number(item.dataset.lon));
      const distancia = item.querySelector(".distancia");
      if (distancia) distancia.textContent = "A " + Math.round(item.dataset.km) + " km";
    });
    items
      .sort(function (a, b) {
        return a.dataset.km - b.dataset.km;
      })
      .forEach(function (item) {
        lista.appendChild(item);
      });
  }

  // Distancia en línea recta (fórmula del haversine).
  function kilometros(lat1, lon1, lat2, lon2) {
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad;
    const dLon = (lon2 - lon1) * rad;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
    return 6371 * 2 * Math.asin(Math.sqrt(a));
  }
})();
