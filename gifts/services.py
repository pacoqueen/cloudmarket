#!/usr/bin/env python
# -*- coding: utf-8 -*-

from html.parser import HTMLParser
from urllib.parse import urljoin

import requests

DEFAULT_TIMEOUT = 10
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
)


def _absolute(page_url, url):
    """Resuelve una URL posiblemente relativa contra la URL de la página."""
    if not url:
        return ""
    try:
        return urljoin(page_url, url)
    except ValueError:
        return ""


class OpenGraphExtractor(HTMLParser):
    """Extrae las imágenes relevantes de una página de producto."""

    def __init__(self, page_url):
        super().__init__()
        self.page_url = page_url
        self.og_image = ""
        self.twitter_image = ""
        self.first_img = ""

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "meta":
            key = data.get("property") or data.get("name")
            content = data.get("content", "")
            if key in ("og:image", "image"):
                if not self.og_image and content:
                    self.og_image = _absolute(self.page_url, content)
            elif key in ("twitter:image",) and content:
                if not self.twitter_image:
                    self.twitter_image = _absolute(self.page_url, content)
        elif tag == "img":
            if not self.first_img and data.get("src"):
                self.first_img = _absolute(self.page_url, data["src"])


def extract_product_image(html, page_url):
    """Devuelve la mejor URL de imagen del producto en el HTML de la página."""
    parser = OpenGraphExtractor(page_url)
    try:
        parser.feed(html)
    except Exception:
        return ""
    return parser.og_image or parser.twitter_image or parser.first_img


def fetch_product_image(url):
    """
    Obtiene la URL de la foto del producto de la página de compra.

    Devuelve '' si la página no es accesible o no se encuentra imagen.
    """
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""
    if not response.url:
        page_url = url
    else:
        page_url = response.url
    return extract_product_image(response.text, page_url)