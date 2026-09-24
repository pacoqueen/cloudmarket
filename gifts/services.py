#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

DEFAULT_TIMEOUT = 10
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
)
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def _absolute(page_url, url):
    """Resuelve una URL posiblemente relativa contra la URL de la página."""
    if not url:
        return ""
    try:
        return urljoin(page_url, url)
    except ValueError:
        return ""


def _clean_text(value, limit=None):
    """Normaliza texto procedente de etiquetas o de JSON-LD."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(part) for part in value if part)
    text = " ".join(str(value).split())
    if limit and len(text) > limit:
        return text[:limit].rstrip()
    return text


def parse_price(value):
    """Convierte un precio europeo o anglosajón a float; devuelve None si no es válido."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"[^0-9,\.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None

    if "," in text and "." in text:
        # El separador decimal suele ser el que aparece más a la derecha.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


class OpenGraphExtractor(HTMLParser):
    """Extrae metadatos de producto de HTML estático."""

    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.meta = {}
        self.canonical_url = ""
        self.first_img = ""
        self.og_image = ""
        self.twitter_image = ""
        self.title_parts = []
        self.h1_parts = []
        self.in_title = False
        self.in_h1 = False
        self.in_jsonld = False
        self.jsonld_parts = []
        self.jsonld_documents = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        data = {key.lower(): value or "" for key, value in attrs}

        if tag == "meta":
            key = (
                data.get("property")
                or data.get("name")
                or data.get("itemprop")
                or ""
            ).strip().lower()
            content = data.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
            if key in ("og:image", "image") and content and not self.og_image:
                self.og_image = _absolute(self.page_url, content)
            elif key == "twitter:image" and content and not self.twitter_image:
                self.twitter_image = _absolute(self.page_url, content)
        elif tag == "link":
            rel = data.get("rel", "").lower().split()
            if "canonical" in rel and data.get("href") and not self.canonical_url:
                self.canonical_url = _absolute(self.page_url, data["href"])
        elif tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
        elif tag == "script":
            if data.get("type", "").lower() == "application/ld+json":
                self.in_jsonld = True
                self.jsonld_parts = []
        elif tag == "img":
            image = data.get("src") or data.get("data-src") or data.get("data-lazy-src")
            if image and not self.first_img:
                self.first_img = _absolute(self.page_url, image)

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self.h1_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False
        elif tag == "script" and self.in_jsonld:
            raw_json = "".join(self.jsonld_parts).strip()
            if raw_json:
                try:
                    self.jsonld_documents.append(json.loads(raw_json))
                except (TypeError, ValueError):
                    pass
            self.in_jsonld = False
            self.jsonld_parts = []

    def _walk_json(self, value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from self._walk_json(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._walk_json(child)

    def _product_node(self):
        fallback = None
        for node in self._walk_json(self.jsonld_documents):
            node_type = node.get("@type") or node.get("type") or ""
            if isinstance(node_type, list):
                types = [str(item).lower() for item in node_type]
            else:
                types = [str(node_type).lower()]
            if any(item == "product" or item.endswith("/product") for item in types):
                return node
            if fallback is None and (node.get("offers") or node.get("name")):
                fallback = node
        return fallback

    @staticmethod
    def _string_or_url(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            for item in value:
                result = OpenGraphExtractor._string_or_url(item)
                if result:
                    return result
            return ""
        if isinstance(value, dict):
            for key in ("url", "contentUrl", "@id"):
                if value.get(key):
                    return str(value[key])
        return ""

    def _offer_price(self, value):
        if isinstance(value, list):
            for item in value:
                price = self._offer_price(item)
                if price is not None:
                    return price
            return None
        if not isinstance(value, dict):
            return parse_price(value)
        for key in ("price", "lowPrice", "minPrice", "highPrice"):
            if key in value:
                price = parse_price(value.get(key))
                if price is not None:
                    return price
        for key in ("priceSpecification", "offers"):
            if key in value:
                price = self._offer_price(value.get(key))
                if price is not None:
                    return price
        return None

    def _product_metadata(self):
        product = self._product_node() or {}
        title = self._string_or_url(product.get("name"))
        description = self._string_or_url(product.get("description"))
        image = self._string_or_url(product.get("image"))
        price = self._offer_price(product.get("offers"))
        return title, description, image, price

    def metadata(self):
        product_title, product_description, product_image, product_price = self._product_metadata()
        title = _clean_text(
            product_title
            or self.meta.get("og:title")
            or self.meta.get("twitter:title")
            or " ".join(self.title_parts)
            or " ".join(self.h1_parts),
            256,
        )
        description = _clean_text(
            product_description
            or self.meta.get("og:description")
            or self.meta.get("description")
            or title,
            256,
        )
        image = _absolute(self.page_url, product_image) or self.og_image or self.twitter_image
        image = image or self.first_img
        price = product_price
        if price is None:
            price = parse_price(
                self.meta.get("product:price:amount")
                or self.meta.get("og:price:amount")
                or self.meta.get("price")
            )
        return {
            "description": description,
            "price": price,
            "image_url": image,
        }

    def best_image(self):
        _, _, product_image, _ = self._product_metadata()
        product_image = _absolute(self.page_url, product_image)
        return self.og_image or self.twitter_image or product_image or self.first_img


def extract_product_image(html, page_url):
    """Devuelve la mejor URL de imagen del producto en el HTML de la página."""
    parser = OpenGraphExtractor(page_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    return parser.best_image()


def extract_product_metadata(html, page_url):
    """Devuelve título, precio e imagen de un producto presentes en el HTML."""
    parser = OpenGraphExtractor(page_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return {"description": "", "price": None, "image_url": ""}
    return parser.metadata()


def validate_public_url(url):
    """Valida una URL pública para evitar que el servidor acceda a la red interna."""
    if not url:
        raise ValueError("La URL está vacía.")
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("La URL no es válida.") from exc

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Solo se permiten URLs HTTP o HTTPS.")
    if parsed.username or parsed.password:
        raise ValueError("Las URLs con credenciales no están permitidas.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("No se permite acceder a localhost.")

    try:
        addresses = socket.getaddrinfo(hostname, port or (443 if parsed.scheme.lower() == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("No se pudo resolver el dominio.") from exc

    for address in addresses:
        raw_ip = address[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise ValueError("El dominio no resolvió a una IP válida.") from exc
        if not ip.is_global:
            raise ValueError("No se permite acceder a una red privada.")
    return url


def _response_text(response):
    content = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            content.extend(chunk)
            if len(content) > MAX_RESPONSE_BYTES:
                raise ValueError("La respuesta es demasiado grande.")
    except AttributeError:
        raw_content = response.content
        if isinstance(raw_content, str):
            raw_content = raw_content.encode("utf-8")
        content.extend(raw_content)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError("La respuesta es demasiado grande.")

    encoding = getattr(response, "encoding", None) or "utf-8"
    return bytes(content).decode(encoding, errors="replace")


def _fetch_page(url):
    """Descarga HTML validando la URL inicial y cada redirección."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        try:
            validate_public_url(current_url)
            response = requests.get(
                current_url,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
        except (requests.RequestException, ValueError, OSError):
            return "", current_url

        status_code = getattr(response, "status_code", 200)
        if status_code in REDIRECT_STATUSES:
            location = getattr(response, "headers", {}).get("Location")
            close = getattr(response, "close", None)
            if close:
                close()
            if not location:
                return "", current_url
            current_url = urljoin(current_url, location)
            continue

        try:
            response.raise_for_status()
            html = _response_text(response)
            final_url = getattr(response, "url", None) or current_url
            return html, final_url
        except (requests.RequestException, ValueError, OSError):
            return "", current_url
        finally:
            close = getattr(response, "close", None)
            if close:
                close()

    return "", current_url


def fetch_product_metadata(url):
    """Obtiene los metadatos de una página de producto; devuelve {} si falla."""
    if not url:
        return {}
    html, final_url = _fetch_page(url)
    if not html:
        return {}
    metadata = extract_product_metadata(html, final_url)
    metadata["url"] = final_url
    return metadata


def fetch_product_image(url):
    """
    Obtiene la URL de la foto del producto de la página de compra.

    Devuelve '' si la página no es accesible o no se encuentra imagen.
    """
    if not url:
        return ""
    html, final_url = _fetch_page(url)
    if not html:
        return ""
    return extract_product_image(html, final_url)
