# Casos de uso de Cloudmarket

**cloudmarket.es** — *"Get track of your wishlists and gifts."* (frase de partida del
[README.rst](README.rst)). Es una aplicación web para apuntar artículos que quieres
regalar, decidir a quién se los das y cuándo, y marcarlos como entregados a medida que van
saliendo.

Contexto del proyecto, según el repositorio:

- Código abierto en [github.com/pacoqueen/cloudmarket](https://github.com/pacoqueen/cloudmarket),
  licencia **GPLv3** (Francisco José Rodríguez Bogado, 2017). Dos ramas en uso:
  `master` (lo que hay en producción) y `experimental` (funcionalidad en desarrollo);
  `privacy` ya quedó absorbida en ambas tras la rama de visibilidad pública/privada de los
  regalos.
- Construida con **cookiecutter-django** y ya en Django 6.1 sobre Python 3.13; conserva su
  ADN heredado: dos apps (`gifts` y `cloudmarket.users`), django-allauth, settings partidos
  en `config/settings/`, y la documentación Sphinx de `docs/` (instalación, despliegue con
  Apache + WSGI, Docker/EC2) más los pendientes de `TODO.md`.
- Se despliega manualmente en el dominio `cloudmarket.es` con Apache + WSGI
  (`docs/apache2site.conf`) y `gunicorn` como entrada en `Procfile`; los cambios de código
  no se publican solos.
- Las cuentas se crean con django-allauth y **la verificación de email es obligatoria**.

Este documento recoge:

- **Casos de uso implementados** (UC-01 … UC-10): lo que la aplicación hace hoy.
- **Casos de uso propuestos** (UC-11 …): ideas documentadas, todavía sin código.
- **Gaps**: lo que se ha detectado y no está resuelto, incluida la app móvil.

Mapa de rutas para orientarse: `/` portada con accesos rápidos · `/about/` página estática ·
`gifts/` lista, alta, edición, detalle y filtros · `users/` perfil y usuarios ·
`/accounts/` django-allauth (login, registro, verificación) · `/adminpanel/` admin de Django.

---

## Casos de uso implementados

### UC-01 · Consultar la lista de regalos
**Actor:** cualquiera, con o sin sesión.

**Dónde:** `/gifts/`.

- Los regalos se **agrupan por destinatario** y dentro de cada grupo se ordenan por estado
  y fecha, de modo que los pendientes salen primero (`order_by("done", "-date")`).
- **Filtro por estado**: *Todos* / *Pendientes* / *Regalados* (`?status=`).
- **Filtro por destinatario**: casillas por persona (`?person=<id>`), combinables con el de
  estado, y un buscador que filtra las casillas en el navegador (`static/gifts/filter.js`).
- Cada tarjeta muestra miniatura, fecha, precio (si lo hay) y el estado con un distintivo.
  La miniatura sale de la foto que se subió, o de la imagen del producto, o del favicon del
  dominio del artículo.
- En cabecera se indica cuántos regalos hay y para cuántas personas.

**Notas:** sin sesión solo se ven los regalos públicos. El buscador de destinatarios es
solo de cliente: el filtro real viaja en la query string y sobrevive al "Aplicar".

### UC-02 · Ver el detalle de un regalo
**Actor:** cualquiera (con restricciones de visibilidad).

**Dónde:** `/gifts/<id>/`.

- Título con la descripción del artículo y el destinatario.
- Interruptor *Ya regalado / Pendiente* con su botón de guardar.
- Con sesión: interruptor *Público / Privado* y enlace en el título para editar.
- Un regalo privado pedido sin sesión devuelve 404.

### UC-03 · Marcar un regalo como entregado o pendiente
**Dónde:** desde el detalle, con un POST a `/gifts/<id>/mark/`; al guardar vuelve al índice.

**Nota de seguridad:** esta vista **no exige iniciar sesión** (a diferencia de editar o
cambiar la visibilidad). Un visitante anónimo puede marcar como entregado cualquier regalo
público. Puede ser intencionado (cualquiera puede confirmar que ya está entregado) o un
hueco pendiente de decidir.

### UC-04 · Añadir un regalo a mano
**Actor:** usuario con sesión. **Dónde:** `/gifts/add/`.

- Campos: URL del artículo (obligatoria), descripción, precio, URL de la imagen, notas,
  destinatario, fecha (por defecto, hoy) y visibilidad.
- Al guardar se hace `Item.objects.get_or_create(url=...)`: si el artículo ya existe se
  reutiliza y solo se rellenan `notes` o `image_url` si estaban vacías; si no, se crea.
  Después se crea el `Gift` con destinatario, fecha, precio y visibilidad.
- Mensaje de éxito y redirección al detalle del regalo creado.

### UC-05 · Analizar una URL y autocompletar los datos
**Actor:** usuario con sesión. **Dónde:** `/gifts/add/`, botón *Analizar URL*.

- El análisis ocurre en el servidor, en `gifts/services.py`:
  - `validate_public_url()` evita SSRF: solo `http`/`https`, sin credenciales, nada de
    `localhost` ni `.local`, y el dominio debe resolver a IPs públicas.
  - La descarga usa `requests` en streaming, con timeout de 10 s, User-Agent de navegador,
    máximo 2 MB y 5 redirecciones (revalidando la URL en cada salto).
  - `OpenGraphExtractor` (subclase de `html.parser.HTMLParser`, sin dependencias extra)
    extrae descripción, precio e imagen con esta prioridad:
    JSON-LD `Product` → OpenGraph/Twitter → `<title>`/`<h1>`; y para la foto:
    JSON-LD → `og:image` → `twitter:image` → primera `<img>`.
- Los datos detectados **solo rellenan el formulario**: no se guarda nada hasta pulsar
  *Guardar regalo*.
- Si el análisis falla, se avisa con un mensaje en la página y la descripción cae al
  dominio de la URL.
- También se dispara automáticamente al entrar con `?url=...` (lo usa el bookmarklet).

**Límites conocidos:** no se ejecuta JavaScript, así que las tiendas que montan el producto
en el cliente no devuelven nada; y Amazon suele responder con su muro antispam, por lo que
el análisis falla antes incluso de parsear.

### UC-06 · Capturar un artículo desde cualquier tienda con el bookmarklet
**Actor:** usuario con sesión. **Dónde:** `/gifts/bookmarklet/`.

- La página explica la instalación (arrastrar el botón a la barra de favoritos) y ofrece
  el acceso directo, que es un enlace `javascript:` que abre `/gifts/add/?url=<url actual>`
  en una pestaña nueva.
- Es la vía rápida desde el escritorio: se navega por la tienda y, al encontrar algo, se
  pulsa el acceso y se elige destinatario y fecha con los datos ya rellenos.
- La propia página ofrece alternativas para cuando el navegador no deja arrastrar el
  enlace: copiarlo y crear el favorito a mano, o abrir el formulario y pegar la URL.

### UC-07 · Editar un regalo
**Actor:** usuario con sesión. **Dónde:** `/gifts/<id>/edit/`.

- Bloque *Artículo*: descripción, URL (con un botón **Abrir** que abre el enlace en una
  pestaña nueva y se va sincronizando con lo que se escribe), notas, URL de la imagen,
  subir foto y quitar la foto existente.
- Bloque *Regalo*: destinatario, fecha, precio, *ya regalado* y *público*.
- Al guardar, mensaje de éxito y vuelta al detalle.

### UC-08 · Publicar o privatizar un regalo
**Actor:** usuario con sesión. **Dónde:** interruptor en el detalle (POST a
`/gifts/<id>/set_public/`).

- Decide si el regalo aparece en `/gifts/` para quien no ha iniciado sesión.

### UC-09 · Completar las fotos de producto en lote (mantenimiento)
**Actor:** quien administra la instancia. **Dónde:** consola.

- `bin/python manage.py fetch_item_images [--force] [--limit N]` recorre los artículos que
  tienen URL pero no imagen, la descarga y la guarda. Es la red de seguridad para cuando el
  análisis automático falló; se ejecuta a mano, no desde la web.

### UC-10 · Gestión de la cuenta
**Actor:** usuario registrado.

- Registro, acceso y cambio de contraseña con django-allauth en `/accounts/`.
- **La verificación de email es obligatoria**: sin verificar no se puede entrar.
- `/users/` lista de usuarios, `/users/<username>/` muestra un perfil y `/users/~update/`
  permite cambiar el campo `name`. Todo con `LoginRequiredMixin`.

---

## Casos de uso propuestos

### UC-11 · Añadir un regalo enviando el enlace a un bot de Telegram
**Estado:** propuesta, sin código.

**Motivación.** Hoy el artículo se captura con el bookmarklet (que pide escritorio y
arrastrar un acceso) o pegando la URL en un formulario. La idea es que baste con
**compartir el enlace del producto con un bot desde el móvil**: es un gesto que ya se hace
con cualquier contacto, no hay que instalar nada y funciona igual en el teléfono que en el
ordenador.

**Flujo del usuario**

1. **Vincular la cuenta (una vez).** En la web, el usuario identificado genera un token y
   abre el enlace profundo `https://t.me/<bot>?start=<token>`. Al pulsar *Iniciar* en
   Telegram, el backend recibe su `chat_id` y lo asocia a su cuenta. A partir de ahí,
   escribirle al bot es como escribirle a un contacto.
2. **Enviar el enlace.** En la tienda, el usuario usa *Compartir → … → bot* y elige el
   enlace del producto (o lo pega como texto en un mensaje).
3. **El bot responde.** El backend valida la URL, reutiliza el análisis de metadatos
   (`fetch_product_metadata`) y crea `Item` + `Gift` igual que el formulario de alta, con
   destinatario y fecha por defecto (pendiente de decidir cuáles).
4. **Confirmación en la tarjeta del chat.** Respuesta con título, precio e imagen
   detectados y botones *Abrir en la web*, *Editar* y *Marcar como pendiente*, para
   corregir en el móvil lo que haga falta y confirmar que el regalo se registró.

**Cómo encajaría en el código**

- **Dependencia nueva:** cliente de Telegram (`python-telegram-bot` o `httpx` contra la API)
  con *webhook* HTTPS en producción y *polling* o túnel (ngrok) en desarrollo.
- **Modelo nuevo:** tabla que una un `User` con su `telegram_chat_id` (y token, estado y
  fechas), más lo que haga falta para los regalos creados por el bot a los que todavía les
  falta destinatario o fecha.
- **Reutilización:** `_metadata_initial()` y `fetch_product_metadata()` de `gifts/services.py`,
  y la redirección al login de allauth con token de un solo uso para confirmar la vinculación
  desde la web sin tener que memorizar nada.
- **Privacidad:** las respuestas del bot no deben filtrar tokens ni datos privados, y
  conviene recordar que hoy los regalos no tienen propietario: cualquier usuario registrado
  ve el listado completo.

**Decisiones pendientes**

- ¿Un chat por usuario, o se admiten varios usuarios en un mismo grupo de Telegram?
- ¿Qué destinatario y qué fecha se ponen por defecto, y cómo se corrigen después?
- ¿Se acepta cualquier URL o se filtra por dominios de confianza?
- ¿Quién puede ver los regalos creados desde el bot? Hoy `Gift` no tiene propietario: todo
  lo ve cualquiera que esté registrado.

---

## Gaps

- **App móvil: no existe en este repositorio.** La web pública es responsiva y conserva un
  `site.webmanifest` heredado de cookiecutter (que todavía se llama "MyWebSite"), pero no
  es una PWA instalable.
- **App móvil planificada en Kivy, en otro repositorio.** Está en
  [`cloud-market`](https://github.com/pacoqueen/cloud-market)
  (`git@github.com:pacoqueen/cloud-market.git`), descrito en su README como *"Kivy client
  for cloudmarket"*, con licencia GPL-3.0. De momento solo contiene el esqueleto heredado del
  tutorial de Pong de Kivy (`cloudmarket.py` + `pong.kv`, dependencias Kivy 1.9.1 / pygame /
  Cython de 2016) **sin ninguna conexión con esta web**: no hay API que consumir ni cliente
  escrito. Para que ese repositorio sea útil, el primer paso es definir una API (o compartir
  la sesión con la web) y decidir si el cliente la consume, así que sigue pendiente de decisión.
- El detalle de un regalo no muestra precio ni imagen: solo descripción, destinatario e
  interruptores. En el índice sí se ve el precio.
- `Person.birthdate` existe en el modelo pero no se usa en ningún formulario.
- No hay listas de deseos por persona. Apuntado en `TODO.md` desde 2021.
- Las fotos y el precio se extraen del HTML del sitio de compra: Amazon, y en general las
  tiendas con renderizado en cliente o muro antispam, no aportan imagen ni precio.
- Sin rate limiting en el registro: se han visto altas automatizadas desde IPs externas.
