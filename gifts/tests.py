#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

# Create your tests here.

from .models import Gift, Person, Item
from .services import (
    extract_product_image,
    extract_product_metadata,
    fetch_product_metadata,
    parse_price,
    validate_public_url,
)
from .views import IndexView


class GiftsMethodTests(TestCase):

    def test_gift_is_gifted_to_someone(self):
        """
        Every gift has 1 item and 1 person. Price, url, date, etc. not needed.
        """
        # Silly test just for... testing. I've just invented METATESTING!
        person = Person()
        item = Item()
        gift = Gift(person=person, item=item)
        self.assertIs(gift.person is not None and gift.item is not None, True)


class ItemMethodTests(TestCase):

    def test_url_host_with_url(self):
        item = Item(url="https://www.amazon.es/coche-de-juguete-1234")
        self.assertEqual(item.url_host(), "www.amazon.es")

    def test_url_host_empty_when_no_url(self):
        self.assertEqual(Item().url_host(), "")

    def test_url_host_tolerates_bad_url(self):
        self.assertEqual(Item(url="::::").url_host(), "")

    def test_favicon_url_uses_host(self):
        item = Item(url="https://shop.example.com/item/1")
        self.assertIn("shop.example.com", item.favicon_url())

    def test_favicon_url_empty_without_host(self):
        self.assertEqual(Item().favicon_url(), "")

    def test_preview_url_falls_back_to_favicon(self):
        item = Item(url="https://shop.example.com/item/1")
        self.assertEqual(item.preview_url(), item.favicon_url())

    def test_preview_url_uses_photo_when_present(self):
        item = Item(url="https://shop.example.com/item/1", photo="img/regalo.png")
        self.assertEqual(item.preview_url(), "/media/img/regalo.png")

    def test_preview_url_uses_image_url_when_no_photo(self):
        item = Item(
            url="https://shop.example.com/item/1",
            image_url="https://shop.example.com/img/producto.jpg",
        )
        self.assertEqual(item.preview_url(), "https://shop.example.com/img/producto.jpg")

    def test_preview_url_prefers_photo_over_image_url(self):
        item = Item(
            url="https://shop.example.com/item/1",
            photo="img/manual.png",
            image_url="https://shop.example.com/img/producto.jpg",
        )
        self.assertEqual(item.preview_url(), "/media/img/manual.png")

    def test_preview_url_falls_back_to_favicon(self):
        item = Item(url="https://shop.example.com/item/1")
        self.assertIn("shop.example.com", item.preview_url())


class ProductImageTests(TestCase):

    def test_extracts_og_image(self):
        html = (
            '<html><head>'
            '<meta property="og:title" content="Coche" />'
            '<meta property="og:image" content="https://shop.example.com/foto.jpg" />'
            '</head><body></body></html>'
        )
        self.assertEqual(
            extract_product_image(html, "https://shop.example.com/item/1"),
            "https://shop.example.com/foto.jpg",
        )

    def test_extracts_twitter_image_as_fallback(self):
        html = (
            '<meta name="twitter:image" '
            'content="https://shop.example.com/twitter.jpg" />'
        )
        self.assertEqual(
            extract_product_image(html, "https://shop.example.com/item/1"),
            "https://shop.example.com/twitter.jpg",
        )

    def test_og_image_wins_over_twitter_and_img(self):
        html = (
            '<meta property="og:image" content="/og.jpg" />'
            '<meta name="twitter:image" content="/tw.jpg" />'
            '<img src="/thumbs/thumb.jpg" />'
        )
        self.assertEqual(
            extract_product_image(html, "https://shop.example.com/item/1"),
            "https://shop.example.com/og.jpg",
        )

    def test_falls_back_to_first_img(self):
        html = '<img src="https://cdn.example.com/producto.jpg" alt="x" />'
        self.assertEqual(
            extract_product_image(html, "https://shop.example.com/item/1"),
            "https://cdn.example.com/producto.jpg",
        )

    def test_resolves_relative_img_url(self):
        html = '<img src="/media/photos/regalo.jpg" />'
        self.assertEqual(
            extract_product_image(html, "https://shop.example.com/item/1"),
            "https://shop.example.com/media/photos/regalo.jpg",
        )

    def test_empty_when_no_image_found(self):
        html = "<html><head><title>nada</title></head></html>"
        self.assertEqual(extract_product_image(html, "https://shop.example.com/i"), "")


class IndexViewGroupingTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")

    def test_gifts_grouped_by_person(self):
        persona_ana = Person.objects.create(name="Ana")
        persona_luis = Person.objects.create(name="Luis")
        item_a = Item.objects.create(description="Regalo A", url="")
        item_b = Item.objects.create(description="Regalo B", url="")
        item_c = Item.objects.create(description="Regalo C", url="")
        Gift.objects.create(person=persona_luis, item=item_a, date="2026-01-02", price=10.0)
        Gift.objects.create(person=persona_ana, item=item_b, date="2026-01-03", price=20.0)
        Gift.objects.create(person=persona_luis, item=item_c, date="2026-01-01", price=30.0)

        view = IndexView()
        view.request = RequestFactory().get("/gifts/")
        view.request.user = self.user
        view.object_list = view.get_queryset()
        context = view.get_context_data()

        groups = context["person_groups"]
        self.assertEqual([g["person"] for g in groups], [persona_ana, persona_luis])
        self.assertEqual(
            [gift.item.description for gift in groups[0]["gifts"]],
            ["Regalo B"],
        )
        self.assertEqual(
            [gift.item.description for gift in groups[1]["gifts"]],
            ["Regalo A", "Regalo C"],
        )


class IndexViewFilterTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.persona = Person.objects.create(name="Ana")
        item_given = Item.objects.create(description="Entregado", url="")
        item_pending = Item.objects.create(description="Pendiente", url="")
        Gift.objects.create(person=self.persona, item=item_given, date="2026-01-01", price=10.0, done=True)
        Gift.objects.create(person=self.persona, item=item_pending, date="2026-02-01", price=20.0, done=False)

    def _query(self, status=""):
        url = "/gifts/"
        if status:
            url = "{}?status={}".format(url, status)
        view = IndexView()
        view.request = RequestFactory().get(url)
        view.request.user = self.user
        view.object_list = view.get_queryset()
        return view.get_context_data()

    def test_pending_gifts_come_first(self):
        self.assertEqual(
            [gift.item.description for gift in self._query()["gift_list"]],
            ["Pendiente", "Entregado"],
        )

    def test_filter_pending(self):
        context = self._query(status="pending")
        self.assertEqual([gift.item.description for gift in context["gift_list"]], ["Pendiente"])
        self.assertEqual(context["current_status"], "pending")

    def test_filter_done(self):
        context = self._query(status="done")
        self.assertEqual([gift.item.description for gift in context["gift_list"]], ["Entregado"])
        self.assertEqual(context["current_status"], "done")


class IndexViewPersonFilterTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.ana = Person.objects.create(name="Ana")
        self.luis = Person.objects.create(name="Luis")
        self.sin_regalos = Person.objects.create(name="Sin Regalos")
        item_a = Item.objects.create(description="Regalo Ana", url="")
        item_b = Item.objects.create(description="Regalo Luis 1", url="")
        item_c = Item.objects.create(description="Regalo Luis 2", url="")
        Gift.objects.create(person=self.ana, item=item_a, date="2026-01-01", price=10.0)
        Gift.objects.create(person=self.luis, item=item_b, date="2026-02-01", price=20.0)
        Gift.objects.create(person=self.luis, item=item_c, date="2026-03-01", price=30.0)

    def _query(self, query_string=""):
        url = "/gifts/"
        if query_string:
            url = "{}?{}".format(url, query_string)
        view = IndexView()
        view.request = RequestFactory().get(url)
        view.request.user = self.user
        view.object_list = view.get_queryset()
        return view.get_context_data()

    def test_no_selection_shows_all_gifts(self):
        context = self._query()
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Regalo Luis 2", "Regalo Luis 1", "Regalo Ana"],
        )
        self.assertEqual(context["person_qs"], "")

    def test_filter_single_person(self):
        context = self._query("person={}".format(self.ana.id))
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Regalo Ana"],
        )
        self.assertEqual(context["current_person_ids"], [self.ana.id])

    def test_filter_multiple_persons(self):
        context = self._query("person={}&person={}".format(self.ana.id, self.luis.id))
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Regalo Luis 2", "Regalo Luis 1", "Regalo Ana"],
        )
        self.assertEqual(context["person_qs"], "person={}&person={}".format(self.ana.id, self.luis.id))

    def test_filter_combined_with_status(self):
        item_done = Item.objects.create(description="Hecho Luis", url="")
        Gift.objects.create(person=self.luis, item=item_done, date="2026-04-01",
                            price=40.0, done=True)
        context = self._query("person={}&status=pending".format(self.luis.id))
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Regalo Luis 2", "Regalo Luis 1"],
        )
        self.assertEqual(context["current_status"], "pending")

    def test_invalid_person_param_is_ignored(self):
        context = self._query("person=abc")
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Regalo Luis 2", "Regalo Luis 1", "Regalo Ana"],
        )

    def test_all_persons_only_those_with_gifts(self):
        context = self._query()
        self.assertEqual(
            [person.name for person in context["all_persons"]],
            ["Ana", "Luis"],
        )


class IndexViewVisibilityTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.ana = Person.objects.create(name="Ana")
        self.luis = Person.objects.create(name="Luis")
        item_public = Item.objects.create(description="Publico", url="")
        item_private = Item.objects.create(description="Privado", url="")
        self.gift_public = Gift.objects.create(
            person=self.ana, item=item_public, date="2026-01-01", price=10.0, is_public=True,
        )
        self.gift_private = Gift.objects.create(
            person=self.luis, item=item_private, date="2026-02-01", price=20.0, is_public=False,
        )

    def _context(self, user):
        view = IndexView()
        view.request = RequestFactory().get("/gifts/")
        view.request.user = user
        view.object_list = view.get_queryset()
        return view.get_context_data()

    def test_anonymous_sees_only_public_gifts(self):
        context = self._context(AnonymousUser())
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Publico"],
        )

    def test_anonymous_all_persons_excludes_private_only_person(self):
        context = self._context(AnonymousUser())
        self.assertEqual(
            [person.name for person in context["all_persons"]],
            ["Ana"],
        )

    def test_authed_sees_public_and_private(self):
        context = self._context(self.user)
        self.assertEqual(
            [gift.item.description for gift in context["gift_list"]],
            ["Privado", "Publico"],
        )

    def test_authed_all_persons_includes_private_only_person(self):
        context = self._context(self.user)
        self.assertEqual(
            [person.name for person in context["all_persons"]],
            ["Ana", "Luis"],
        )

    def test_anonymous_detail_of_private_gift_is_404(self):
        response = self.client.get(reverse("gifts:detail", args=[self.gift_private.id]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_detail_of_public_gift_is_200(self):
        response = self.client.get(reverse("gifts:detail", args=[self.gift_public.id]))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_mark_private_gift_is_404(self):
        response = self.client.post(reverse("gifts:mark", args=[self.gift_private.id]), {"done": "on"})
        self.assertEqual(response.status_code, 404)

    def test_anonymous_mark_public_gift_redirects(self):
        response = self.client.post(reverse("gifts:mark", args=[self.gift_public.id]), {"done": "on"})
        self.assertRedirects(response, reverse("gifts:index"))

    def test_authed_detail_private_is_200(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("gifts:detail", args=[self.gift_private.id]))
        self.assertEqual(response.status_code, 200)

    def test_index_keeps_site_header_and_title(self):
        response = self.client.get(reverse("gifts:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cloudmarket.es")
        self.assertContains(response, "Regalos")

    def test_authed_mark_private_gift_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("gifts:mark", args=[self.gift_private.id]), {"done": "on"})
        self.assertRedirects(response, reverse("gifts:index"))

    def test_anonymous_set_public_redirects_to_login(self):
        response = self.client.post(
            reverse("gifts:set_public", args=[self.gift_private.id]), {"is_public": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_set_public_get_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("gifts:set_public", args=[self.gift_private.id]))
        self.assertEqual(response.status_code, 405)

    def test_authed_set_public_marks_gift_public(self):
        self.client.force_login(self.user)
        self.gift_private.refresh_from_db()
        self.assertFalse(self.gift_private.is_public)
        response = self.client.post(
            reverse("gifts:set_public", args=[self.gift_private.id]), {"is_public": "on"},
        )
        self.assertRedirects(response, reverse("gifts:detail", args=[self.gift_private.id]))
        self.gift_private.refresh_from_db()
        self.assertTrue(self.gift_private.is_public)

    def test_authed_set_public_marks_gift_private(self):
        self.client.force_login(self.user)
        self.gift_public.refresh_from_db()
        self.assertTrue(self.gift_public.is_public)
        response = self.client.post(reverse("gifts:set_public", args=[self.gift_public.id]))
        self.assertRedirects(response, reverse("gifts:detail", args=[self.gift_public.id]))
        self.gift_public.refresh_from_db()
        self.assertFalse(self.gift_public.is_public)


class ProductMetadataTests(TestCase):

    def test_extracts_json_ld_product_metadata(self):
        html = """
        <html>
          <head>
            <meta property="og:title" content="Título de la tienda">
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Camiseta azul",
                "description": "Camiseta de algodón",
                "image": "/images/camiseta.jpg",
                "offers": {"@type": "Offer", "price": "19,99 EUR"}
              }
            </script>
          </head>
        </html>
        """

        metadata = extract_product_metadata(html, "https://shop.example.com/products/1")

        self.assertEqual(metadata["description"], "Camiseta de algodón")
        self.assertEqual(metadata["price"], 19.99)
        self.assertEqual(metadata["image_url"], "https://shop.example.com/images/camiseta.jpg")

    def test_falls_back_to_open_graph_metadata(self):
        html = """
        <html>
          <head>
            <meta property="og:title" content="Artículo">
            <meta property="og:description" content="Descripción del artículo">
            <meta property="og:image" content="https://cdn.example.com/article.jpg">
            <meta property="product:price:amount" content="24.50">
          </head>
        </html>
        """

        metadata = extract_product_metadata(html, "https://shop.example.com/products/1")

        self.assertEqual(metadata["description"], "Descripción del artículo")
        self.assertEqual(metadata["price"], 24.5)
        self.assertEqual(metadata["image_url"], "https://cdn.example.com/article.jpg")

    def test_parses_european_and_anglosaxon_prices(self):
        self.assertEqual(parse_price("19,99 €"), 19.99)
        self.assertEqual(parse_price("1.234,56 €"), 1234.56)
        self.assertEqual(parse_price("$1,234.56"), 1234.56)
        self.assertIsNone(parse_price("precio no disponible"))

    def test_rejects_private_network_urls(self):
        with self.assertRaises(ValueError):
            validate_public_url("http://127.0.0.1:8000/product")

    @patch("gifts.services._fetch_page")
    def test_fetch_product_metadata_uses_final_url(self, fetch_page):
        fetch_page.return_value = (
            '<html><head><title>Producto</title></head></html>',
            "https://shop.example.com/products/final",
        )

        metadata = fetch_product_metadata("https://shop.example.com/products/1")

        self.assertEqual(metadata["url"], "https://shop.example.com/products/final")
        self.assertEqual(metadata["description"], "Producto")
        fetch_page.assert_called_once_with("https://shop.example.com/products/1")


class AddGiftViewTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.person = Person.objects.create(name="Ana")

    def test_add_requires_login(self):
        response = self.client.get(reverse("gifts:add"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    @patch("gifts.views.fetch_product_metadata")
    def test_get_prefills_metadata_and_current_date(self, fetch_metadata):
        fetch_metadata.return_value = {
            "url": "https://shop.example.com/products/1",
            "description": "Regalo detectado",
            "price": 19.99,
            "image_url": "https://cdn.example.com/gift.jpg",
        }
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("gifts:add"),
            {"url": "https://shop.example.com/products/1"},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["description"], "Regalo detectado")
        self.assertEqual(form.initial["price"], 19.99)
        self.assertEqual(form.initial["image_url"], "https://cdn.example.com/gift.jpg")
        self.assertEqual(form.initial["date"], timezone.localdate())
        fetch_metadata.assert_called_once_with("https://shop.example.com/products/1")

    @patch("gifts.views.fetch_product_metadata", return_value={})
    def test_get_explains_when_metadata_cannot_be_fetched(self, fetch_metadata):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("gifts:add"),
            {"url": "https://shop.example.com/products/1"},
        )

        self.assertContains(response, "No se pudo obtener la información automáticamente")
        fetch_metadata.assert_called_once()

    @patch("gifts.views.fetch_product_metadata")
    def test_analyze_button_prefills_form_without_creating_gift(self, fetch_metadata):
        fetch_metadata.return_value = {
            "url": "https://shop.example.com/products/final",
            "description": "Descripción detectada",
            "price": 19.99,
            "image_url": "https://cdn.example.com/gift.jpg",
        }
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("gifts:add"),
            {
                "url": "https://shop.example.com/products/1",
                "date": "2026-12-24",
                "description": "Descripción manual",
                "analyze": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertFalse(form.is_bound)
        self.assertEqual(form.initial["url"], "https://shop.example.com/products/final")
        self.assertEqual(form.initial["description"], "Descripción detectada")
        self.assertEqual(form.initial["price"], 19.99)
        self.assertEqual(form.initial["date"], "2026-12-24")
        self.assertEqual(Gift.objects.count(), 0)
        self.assertContains(response, "Analizar URL")

    @patch("gifts.views.fetch_product_metadata")
    def test_analyze_preserves_long_product_urls(self, fetch_metadata):
        long_url = "https://shop.example.com/products/1?" + "&".join(
            "option_{}=value".format(index) for index in range(20)
        )
        fetch_metadata.return_value = {
            "url": long_url,
            "description": "Artículo con URL larga",
            "price": 12.5,
            "image_url": "https://cdn.example.com/long.jpg",
        }
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("gifts:add"),
            {"url": long_url, "analyze": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["url"], long_url)
        self.assertEqual(response.context["form"].initial["description"], "Artículo con URL larga")

    def test_post_creates_item_and_gift(self):
        self.client.force_login(self.user)
        data = {
            "url": "https://shop.example.com/products/1",
            "person": self.person.pk,
            "date": "2026-12-24",
            "description": "Regalo de prueba",
            "price": "19.99",
            "image_url": "https://cdn.example.com/gift.jpg",
            "notes": "Comprarlo antes de diciembre.",
        }

        response = self.client.post(reverse("gifts:add"), data)

        gift = Gift.objects.get()
        self.assertRedirects(
            response,
            reverse("gifts:detail", args=[gift.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(gift.person, self.person)
        self.assertEqual(gift.item.url, data["url"])
        self.assertEqual(gift.date.isoformat(), data["date"])
        self.assertEqual(gift.price, 19.99)
        self.assertFalse(gift.is_public)
        self.assertEqual(gift.item.description, "Regalo de prueba")

    def test_post_reuses_existing_item(self):
        existing_item = Item.objects.create(
            description="Artículo existente",
            url="https://shop.example.com/products/1",
        )
        self.client.force_login(self.user)
        data = {
            "url": existing_item.url,
            "person": self.person.pk,
            "date": "2026-12-24",
            "description": "Otro título",
            "price": "10",
        }

        response = self.client.post(reverse("gifts:add"), data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Item.objects.count(), 1)
        gift = Gift.objects.get()
        self.assertEqual(gift.item, existing_item)

    def test_post_allows_public_gift(self):
        self.client.force_login(self.user)
        data = {
            "url": "https://shop.example.com/products/public",
            "person": self.person.pk,
            "date": "2026-12-24",
            "description": "Regalo público",
            "is_public": "on",
        }

        self.client.post(reverse("gifts:add"), data)

        self.assertTrue(Gift.objects.get().is_public)

    def test_bookmarklet_page_is_available_to_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:bookmarklet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Añadir a Cloudmarket")
        self.assertTrue(response.context["bookmarklet_url"].startswith("javascript:"))
        self.assertIn("/gifts/add/", response.context["bookmarklet_url"])

    def test_get_prefills_the_date_sent_in_the_query_string(self):
        # El botón "Crear regalo" del calendario enlaza con ?date=...
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:add"), {"date": "2026-12-25"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["date"], date(2026, 12, 25))

    def test_the_suggested_date_wins_over_today(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:add"), {"date": "1999-01-03"})

        self.assertEqual(response.context["form"].initial["date"], date(1999, 1, 3))

    def test_without_a_date_it_still_defaults_to_today(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:add"))

        self.assertEqual(response.context["form"].initial["date"], timezone.localdate())

    def test_a_malformed_date_is_ignored_instead_of_raising(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:add"), {"date": "no-es-una-fecha"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["date"], timezone.localdate())

    @patch("gifts.views.fetch_product_metadata", return_value={})
    def test_the_suggested_date_survives_the_metadata_prefill(self, fetch_metadata):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("gifts:add"),
            {"date": "2026-12-25", "url": "https://shop.example.com/products/1"},
        )

        self.assertEqual(response.context["form"].initial["date"], date(2026, 12, 25))


class GiftEditViewTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.person = Person.objects.create(name="Ana")
        self.other_person = Person.objects.create(name="Luis")
        self.item = Item.objects.create(
            description="Artículo original",
            url="https://shop.example.com/products/1",
            notes="Nota original",
            image_url="https://cdn.example.com/original.jpg",
        )
        self.gift = Gift.objects.create(
            person=self.person,
            item=self.item,
            date="2026-12-24",
            price=19.99,
        )

    def test_edit_requires_login(self):
        response = self.client.get(reverse("gifts:edit", args=[self.gift.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_edit_prefills_item_and_gift_attributes(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:edit", args=[self.gift.pk]))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["description"], self.item.description)
        self.assertEqual(form.initial["url"], self.item.url)
        self.assertEqual(form.initial["notes"], self.item.notes)
        self.assertEqual(form.initial["image_url"], self.item.image_url)
        self.assertEqual(form.initial["person"], self.person.pk)
        self.assertEqual(form.initial["date"].isoformat(), "2026-12-24")
        self.assertEqual(form.initial["price"], self.gift.price)

    def test_edit_updates_item_and_gift_attributes(self):
        self.client.force_login(self.user)
        data = {
            "description": "Artículo actualizado",
            "url": "https://shop.example.com/products/2",
            "notes": "Nota actualizada",
            "image_url": "https://cdn.example.com/updated.jpg",
            "person": self.other_person.pk,
            "date": "2026-12-31",
            "price": "29.95",
            "done": "on",
            "is_public": "on",
        }

        response = self.client.post(reverse("gifts:edit", args=[self.gift.pk]), data)

        self.assertRedirects(
            response,
            reverse("gifts:detail", args=[self.gift.pk]),
            fetch_redirect_response=False,
        )
        self.item.refresh_from_db()
        self.gift.refresh_from_db()
        self.assertEqual(self.item.description, "Artículo actualizado")
        self.assertEqual(self.item.url, "https://shop.example.com/products/2")
        self.assertEqual(self.item.notes, "Nota actualizada")
        self.assertEqual(self.item.image_url, "https://cdn.example.com/updated.jpg")
        self.assertEqual(self.gift.person, self.other_person)
        self.assertEqual(self.gift.date.isoformat(), "2026-12-31")
        self.assertEqual(self.gift.price, 29.95)
        self.assertTrue(self.gift.done)
        self.assertTrue(self.gift.is_public)

    def test_detail_shows_description_edit_link_only_to_authenticated_users(self):
        self.gift.is_public = True
        self.gift.save(update_fields=["is_public"])

        anonymous_response = self.client.get(reverse("gifts:detail", args=[self.gift.pk]))
        self.assertNotContains(anonymous_response, "gift-detail__description-link")
        self.assertNotContains(anonymous_response, reverse("gifts:edit", args=[self.gift.pk]))

        self.client.force_login(self.user)
        authenticated_response = self.client.get(reverse("gifts:detail", args=[self.gift.pk]))
        self.assertContains(authenticated_response, "gift-detail__description-link")
        self.assertContains(authenticated_response, self.item.description)
        self.assertContains(
            authenticated_response,
            reverse("gifts:edit", args=[self.gift.pk]),
        )

    def test_edit_shows_open_link_with_saved_url(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:edit", args=[self.gift.pk]))

        self.assertContains(response, "gift-add__open-link")
        self.assertContains(response, 'href="https://shop.example.com/products/1"')
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener noreferrer"')

    def test_edit_omits_open_link_when_url_is_empty(self):
        self.item.url = ""
        self.item.save(update_fields=["url"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("gifts:edit", args=[self.gift.pk]))

        self.assertNotContains(response, "gift-add__open-link")

    def test_edit_open_link_uses_submitted_url_after_invalid_post(self):
        self.client.force_login(self.user)
        data = {
            "description": "Artículo actualizado",
            "url": "https://shop.example.com/products/3",
            "notes": "",
            "image_url": "",
            "person": 999999,
            "date": "2026-12-31",
            "price": "",
        }

        response = self.client.post(reverse("gifts:edit", args=[self.gift.pk]), data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, 'href="https://shop.example.com/products/3"')
        self.assertNotContains(response, 'href="https://shop.example.com/products/1"')


class UpcomingViewMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester")
        self.client.force_login(self.user)
        self.ana = Person.objects.create(name="Ana")
        self.luis = Person.objects.create(name="Luis")
        self.item = Item.objects.create(description="Algo", url="")

    def _gift(self, person, month, day, year=2017, done=False):
        return Gift.objects.create(
            person=person, item=self.item,
            date="%d-%02d-%02d" % (year, month, day), done=done,
        )

    def _context(self, query=""):
        response = self.client.get(reverse("gifts:upcoming") + query)
        self.assertEqual(response.status_code, 200)
        return response.context

    def _flat_dates(self, context):
        """(mes, día) de todos los regalos, en el orden en que se muestran."""
        return [
            (gift.date.month, gift.date.day)
            for group in context["person_groups"]
            for gift in group["gifts"]
        ]

    def _flat_with_status(self, context, person=None):
        """(mes, día, 'pendiente'/'hecho') en el orden en que se muestran.

        Con person= se limita a un único grupo, que es donde se aplica la regla de
        "pendientes arriba" y, dentro de cada bloque, proximidad ascendente.
        """
        return [
            (gift.date.month, gift.date.day, "hecho" if gift.done else "pendiente")
            for group in context["person_groups"]
            if person is None or group["person"].name == person
            for gift in group["gifts"]
        ]

    def _groups(self, query=""):
        """(nombre, desplegado, nº de regalos) de cada <details> de la página."""
        html = self.client.get(reverse("gifts:upcoming") + query).content.decode()
        return [
            (name, bool(opened), int(count))
            for opened, name, count in re.findall(
                r'<details class="person-group"( open)?>\s*<summary[^>]*>\s*'
                r'<span class="person-group__summary-text">([^<]*)</span>\s*'
                r'<span class="person-group__count">(\d+)</span>',
                html,
            )
        ]


class UpcomingViewOrderingTests(UpcomingViewMixin, TestCase):
    """La vista de calendario ordena por proximidad a la fecha seleccionada.

    Las fechas de regalo son recurrentes, así que el año se ignora siempre: un
    regalo guardado como 25/12/2017 vuelve a caer el 25 de diciembre.
    """

    def test_ignores_the_stored_year_and_sorts_nearest_first(self):
        # Años muy distintos: el orden sólo puede depender de mes/día.
        self._gift(self.ana, 12, 25, year=2017)
        self._gift(self.ana, 1, 3, year=2031)
        self._gift(self.ana, 2, 14, year=2001)

        # Desde el 1 de marzo: 25/12 (9 meses), 3/1 (10 meses), 14/2 (11 meses).
        context = self._context("?date=1999-03-01")
        self.assertEqual(self._flat_dates(context), [(12, 25), (1, 3), (2, 14)])

    def test_same_month_earlier_day_rolls_over_to_next_year(self):
        # 20/12 está antes que el 25/12 seleccionado: no se descarta, cae dentro
        # de 12 meses, justo el último del ciclo.
        self._gift(self.ana, 12, 20, year=2005)
        self._gift(self.ana, 12, 25, year=2017)

        context = self._context("?date=2017-12-25")
        self.assertEqual(self._flat_dates(context), [(12, 25), (12, 20)])

    def test_all_gifts_are_listed_regardless_of_the_selected_date(self):
        # Ignorando el año, todo vuelve a tocar en los próximos 12 meses: elegir
        # un día cambia el orden, nunca hace desaparecer regalos.
        self._gift(self.ana, 1, 3)
        self._gift(self.ana, 6, 15)
        self._gift(self.ana, 12, 25)

        for query in ("?date=1999-12-25", "?date=2026-10-05", "?date=2026-06-15"):
            context = self._context(query)
            self.assertEqual(len(self._flat_dates(context)), 3, query)

    def test_wraps_around_the_end_of_the_year(self):
        self._gift(self.ana, 1, 3, year=2001)
        self._gift(self.ana, 12, 5, year=2017)
        self._gift(self.ana, 12, 25, year=2017)

        # Desde el 20/12: 25/12 llega en 5 días, el 3/1 en 14 (ya en el "año
        # siguiente", pero sin esperar un año real) y el 5/12 tardaría casi un
        # año, así que va el último.
        context = self._context("?date=2017-12-20")
        self.assertEqual(
            self._flat_dates(context),
            [(12, 25), (1, 3), (12, 5)],
        )

    def test_person_groups_follow_nearest_gift(self):
        # Desde el 1 de enero, Ana (3/1) es lo más próximo y Luis (25/12) lo más
        # lejano, así que el grupo de Ana va primero.
        self._gift(self.luis, 12, 25)
        self._gift(self.ana, 1, 3)

        context = self._context("?date=2026-01-01")
        self.assertEqual(
            [group["person"].name for group in context["person_groups"]],
            ["Ana", "Luis"],
        )

    def test_gift_count_matches_the_listed_gifts(self):
        self._gift(self.ana, 1, 3)
        self._gift(self.ana, 2, 14)
        self._gift(self.ana, 3, 8)

        context = self._context("?date=1999-12-25")
        self.assertEqual(context["gift_count"], 3)
        self.assertEqual(len(self._flat_dates(context)), 3)

    def test_pending_gifts_come_first_within_a_person(self):
        # El regalo entregado es el más próximo, pero el pendiente va igualmente
        # por delante dentro del grupo.
        self._gift(self.ana, 10, 6, done=True)
        self._gift(self.ana, 12, 25, done=False)

        context = self._context("?date=2026-10-01")
        self.assertEqual(self._flat_dates(context), [(12, 25), (10, 6)])

    def test_proximity_still_orders_each_pending_and_delivered_block(self):
        self._gift(self.ana, 3, 1, done=False)
        self._gift(self.ana, 12, 25, done=True)
        self._gift(self.ana, 10, 6, done=False)
        self._gift(self.ana, 11, 3, done=True)

        # Pendientes 10/6 y 3/1; entregados 11/3 y 12/25.
        context = self._context("?date=2026-10-01")
        self.assertEqual(
            self._flat_dates(context),
            [(10, 6), (3, 1), (11, 3), (12, 25)],
        )

    def test_the_group_order_is_not_changed_by_the_pending_first_rule(self):
        # El pendiente de Ana está lejísimos y el entregado de Luis es el más
        # próximo: Luis sigue encabezando la lista de grupos.
        self._gift(self.ana, 3, 1, done=False)
        self._gift(self.luis, 10, 6, done=True)

        context = self._context("?date=2026-10-01")
        self.assertEqual(
            [group["person"].name for group in context["person_groups"]],
            ["Luis", "Ana"],
        )

    def test_the_rule_applies_to_each_person_independently(self):
        self._gift(self.ana, 1, 1, done=True)
        self._gift(self.ana, 12, 25, done=False)
        self._gift(self.luis, 2, 2, done=True)
        self._gift(self.luis, 11, 11, done=False)

        context = self._context("?date=2026-10-01")
        by_person = {
            group["person"].name: [(g.date.month, g.date.day, g.done) for g in group["gifts"]]
            for group in context["person_groups"]
        }
        self.assertEqual(by_person["Ana"], [(12, 25, False), (1, 1, True)])
        self.assertEqual(by_person["Luis"], [(11, 11, False), (2, 2, True)])

    def test_each_block_runs_ascending_from_the_nearest_date(self):
        # Regla completa dentro de un grupo: primero los pendientes, luego los
        # hechos, y en cada bloque de menor a mayor proximidad a la fecha elegida.
        self._gift(self.ana, 12, 20, done=False)   # +10 días
        self._gift(self.ana, 12, 5, done=False)    # +1 año (el 5 ya pasó)
        self._gift(self.ana, 12, 10, done=False)   # hoy
        self._gift(self.ana, 12, 18, done=True)    # +8 días
        self._gift(self.ana, 12, 31, done=True)    # +21 días
        self._gift(self.ana, 12, 2, done=True)     # +1 año (el 2 ya pasó)

        context = self._context("?date=2026-12-10")
        self.assertEqual(
            self._flat_with_status(context, person="Ana"),
            [
                (12, 10, "pendiente"),
                (12, 20, "pendiente"),
                (12, 5, "pendiente"),
                (12, 18, "hecho"),
                (12, 31, "hecho"),
                (12, 2, "hecho"),
            ],
        )

    def test_a_day_already_passed_this_month_goes_to_the_end_of_its_block(self):
        # El 5/12 es "ascendente" respecto al 10/12 sólo dentro del ciclo anual:
        # como ya pasó, su próximo aniversario cae dentro de un año y se va detrás.
        self._gift(self.ana, 12, 5, done=False)
        self._gift(self.ana, 12, 6, done=True)

        context = self._context("?date=2026-12-10")
        self.assertEqual(
            self._flat_with_status(context, person="Ana"),
            [(12, 5, "pendiente"), (12, 6, "hecho")],
        )

    def test_both_blocks_wrap_into_the_next_years_months(self):
        # Cruzando diciembre, enero y marzo quedan "cerca" (este año que viene) y
        # el propio diciembre se va al final, en ambos bloques por igual.
        self._gift(self.ana, 12, 20, done=False)
        self._gift(self.ana, 1, 5, done=False)
        self._gift(self.ana, 3, 3, done=True)
        self._gift(self.ana, 1, 8, done=True)

        context = self._context("?date=2026-12-10")
        self.assertEqual(
            self._flat_with_status(context, person="Ana"),
            [
                (12, 20, "pendiente"),
                (1, 5, "pendiente"),
                (1, 8, "hecho"),
                (3, 3, "hecho"),
            ],
        )

    def test_gifts_on_the_same_date_fall_back_to_the_description(self):
        # _gift() reutiliza un único item, así que aquí hace falta crear dos
        # descripciones distintas para que el desempate sea observable.
        zorro = Item.objects.create(description="Zorro", url="https://x.es/z")
        oso = Item.objects.create(description="Oso", url="https://x.es/o")
        for item in (zorro, oso):
            Gift.objects.create(person=self.ana, item=item, date="2011-11-05")

        context = self._context("?date=2026-10-01")
        descriptions = [
            gift.item.description for gift in context["person_groups"][0]["gifts"]
        ]
        self.assertEqual(descriptions, ["Oso", "Zorro"])

    def test_pending_toggle_hides_delivered_gifts(self):
        self._gift(self.ana, 1, 3, done=True)
        self._gift(self.ana, 2, 14, done=False)

        context = self._context("?date=1999-12-25&pending=1")
        self.assertEqual(self._flat_dates(context), [(2, 14)])

    def test_days_with_gifts_ignores_year_and_done_status(self):
        self._gift(self.ana, 12, 25, year=1999, done=True)

        context = self._context("?date=2026-12-01")
        # 25/12 se marca aunque el regalo sea de 1999 y esté entregado.
        self.assertIn("25", context["days_with_gifts"])

    def test_days_with_gifts_only_covers_the_visible_month(self):
        self._gift(self.ana, 12, 25)

        context = self._context("?date=2026-12-01")
        self.assertEqual(context["days_with_gifts"], {"25"})


class UpcomingViewTemplateTests(UpcomingViewMixin, TestCase):
    """La vista de calendario debe verse igual que la lista de regalos."""

    def setUp(self):
        super().setUp()
        today = date.today()
        self._gift(self.ana, today.month, today.day, year=1999)

    def test_loads_the_shared_design_system_stylesheet(self):
        # style.css define las variables de color y el fondo de la página; sin él
        # el calendario se ve sin estilos y los marcadores verdes tampoco salen.
        response = self.client.get(reverse("gifts:upcoming"))
        self.assertContains(response, "gifts/style.css")
        self.assertContains(response, "gifts/calendar.css")

    def test_renders_month_navigation_arrows(self):
        response = self.client.get(reverse("gifts:upcoming"))
        self.assertContains(response, 'data-nav="prev"')
        self.assertContains(response, 'data-nav="next"')

    def test_marks_today_and_gift_days(self):
        response = self.client.get(reverse("gifts:upcoming"))
        self.assertContains(response, "calendar__day--today")
        # El regalo de hoy (guardado en 1999) marca el día.
        self.assertContains(response, "calendar__day--has-gifts")
        self.assertContains(response, "calendar__day-link--has-gifts")

    def test_links_back_to_the_gift_list(self):
        response = self.client.get(reverse("gifts:upcoming"))
        self.assertContains(response, reverse("gifts:index"))

    def test_a_gift_marks_only_one_cell(self):
        # Un regalo no debe marcar dos celdas: la del mes visible y la del mes
        # contiguo que cae en la misma rejilla.
        html = self.client.get(reverse("gifts:upcoming")).content.decode()
        self.assertEqual(html.count("calendar__day-link--has-gifts"), 1)

    def test_does_not_mark_days_of_the_adjacent_months(self):
        # El día 1 aparece también al principio de la rejilla del mes siguiente
        # (celda "contigua"): ese 1 no debe marcarse por el regalo del mes visible.
        Gift.objects.all().delete()
        today = date.today()
        self._gift(self.ana, today.month, 1, year=1999)

        html = self.client.get(reverse("gifts:upcoming")).content.decode()
        self.assertEqual(html.count("calendar__day-link--has-gifts"), 1)


class UpcomingViewCollapsibleTests(UpcomingViewMixin, TestCase):
    """Cada persona es un desplegable: abierto si tiene algún regalo pendiente."""

    def test_person_with_a_pending_gift_starts_open(self):
        self._gift(self.ana, 11, 3)

        self.assertEqual(self._groups(), [("Ana", True, 1)])

    def test_person_with_only_delivered_gifts_starts_collapsed(self):
        self._gift(self.luis, 11, 8, done=True)

        self.assertEqual(self._groups(), [("Luis", False, 1)])

    def test_one_pending_gift_opens_a_group_that_also_has_delivered_ones(self):
        self._gift(self.ana, 11, 3, done=True)
        self._gift(self.ana, 11, 20, done=False)

        self.assertEqual(self._groups(), [("Ana", True, 2)])

    def test_pending_filter_leaves_every_listed_group_open(self):
        # Con el filtro activo todos los grupos los gifts son pendientes, así que
        # ninguno queda plegado por sorpresa.
        self._gift(self.ana, 11, 3)
        self._gift(self.luis, 11, 8)

        groups = self._groups("?pending=1")
        self.assertEqual([name for name, _, _ in groups], ["Ana", "Luis"])
        self.assertEqual([opened for _, opened, _ in groups], [True, True])

    def test_the_group_title_is_the_clickable_summary(self):
        self._gift(self.ana, 11, 3)

        html = self.client.get(reverse("gifts:upcoming")).content.decode()
        # <summary> es el elemento que hace clic para plegar/desplegar; el
        # <h2> de la lista de regalos ya no debe aparecer aquí.
        self.assertIn("<summary", html)
        self.assertNotIn('<h2 class="person-group__title"', html)


class UpcomingViewEmptyStateTests(UpcomingViewMixin, TestCase):
    """Si nada concuerda con el filtro, se ofrece crear el regalo de ese día."""

    def _html(self, query=""):
        return self.client.get(reverse("gifts:upcoming") + query).content.decode()

    def test_offers_to_create_a_gift_when_there_are_no_gifts_at_all(self):
        html = self._html()

        self.assertIn('class="upcoming__create"', html)

    def test_offers_to_create_a_gift_when_the_filter_hides_everything(self):
        # Día marcado en el calendario pero con los regalos ya entregados: el
        # filtro "solo pendientes" deja la lista vacía.
        self._gift(self.ana, 11, 3, done=True)

        html = self._html("?pending=1")
        self.assertIn('class="upcoming__create"', html)
        self.assertNotIn("person-group", html)

    def test_the_create_button_carries_the_selected_date(self):
        html = self._html("?date=2026-12-25")

        self.assertIn(reverse("gifts:add") + "?date=2026-12-25", html)

    def test_names_the_selected_day_in_the_button(self):
        html = self._html("?date=2026-12-25")

        self.assertIn("Crear regalo para el 25 de diciembre", html)

    def test_the_old_empty_message_is_gone(self):
        self.assertNotIn("No hay regalos próximos", self._html())

    def test_the_button_is_shown_to_anonymous_visitors_too(self):
        # add es @login_required, así que el enlace lleva a iniciar sesión, pero
        # conviene que exista siempre en vez de dejar un hueco en blanco.
        self.client.logout()
        html = self.client.get(reverse("gifts:upcoming")).content.decode()

        self.assertIn('class="upcoming__create"', html)


class UpcomingViewOnlyDayFilterTests(UpcomingViewMixin, TestCase):
    """El filtro "solo este día" deja únicamente los regalos del día seleccionado."""

    def test_only_shows_gifts_falling_on_the_selected_day(self):
        self._gift(self.ana, 12, 25)
        self._gift(self.ana, 12, 26)
        self._gift(self.ana, 6, 10)
        self._gift(self.luis, 12, 25)

        context = self._context("?date=2026-12-25&only_day=1")
        self.assertEqual(
            [(gift.date.month, gift.date.day) for gift in context["person_groups"][0]["gifts"]],
            [(12, 25)],
        )
        self.assertEqual(
            sorted(group["person"].name for group in context["person_groups"]),
            ["Ana", "Luis"],
        )

    def test_ignores_the_stored_year(self):
        # El filtro compara día y mes, no la fecha completa: un regalo de 1999
        # sigue apareciendo en el 25/12 de cualquier año.
        self._gift(self.ana, 12, 25, year=1999)
        self._gift(self.ana, 12, 25, year=2031)

        context = self._context("?date=2026-12-25&only_day=1")
        self.assertEqual(len(self._flat_dates(context)), 2)

    def test_hides_people_without_a_gift_that_day(self):
        self._gift(self.ana, 12, 25)
        self._gift(self.luis, 6, 10)

        context = self._context("?date=2026-12-25&only_day=1")
        self.assertEqual([g["person"].name for g in context["person_groups"]], ["Ana"])

    def test_is_off_by_default_and_behaves_as_before(self):
        self._gift(self.ana, 12, 25)
        self._gift(self.ana, 6, 10)

        context = self._context("?date=2026-12-25")
        self.assertEqual(len(self._flat_dates(context)), 2)
        self.assertFalse(context["only_day"])

    def test_combines_with_the_pending_filter(self):
        self._gift(self.ana, 12, 25)
        self._gift(self.ana, 12, 25, done=True)
        self._gift(self.ana, 6, 10)

        context = self._context("?date=2026-12-25&only_day=1&pending=1")
        self.assertEqual(self._flat_with_status(context), [(12, 25, "pendiente")])

    def test_pending_still_wins_when_both_filters_are_active(self):
        self._gift(self.ana, 12, 25, done=True)

        context = self._context("?date=2026-12-25&only_day=1&pending=1")
        self.assertEqual(context["person_groups"], [])

    def test_offers_to_create_a_gift_when_the_day_is_empty(self):
        self._gift(self.ana, 6, 10)

        html = self.client.get(
            reverse("gifts:upcoming") + "?date=2026-12-25&only_day=1",
        ).content.decode()
        self.assertIn('class="upcoming__create"', html)
        self.assertIn(reverse("gifts:add") + "?date=2026-12-25", html)

    def test_the_subtitle_names_the_day_instead_of_the_order(self):
        self._gift(self.ana, 12, 25)

        response = self.client.get(reverse("gifts:upcoming") + "?date=2026-12-25&only_day=1")
        self.assertContains(response, "1 regalo el 25 de diciembre")


class UpcomingViewFilterLinkTests(UpcomingViewMixin, TestCase):
    """Los enlaces de filtro conservan el estado del otro filtro y del día."""

    def _filter_links(self, query):
        """Los dos href de la barra de filtros, con la fecha seleccionada."""
        html = self.client.get(reverse("gifts:upcoming") + query).content.decode()
        return [
            href.replace("&amp;", "&").split("?", 1)[1]
            for href in re.findall(r'class="filter-link[^"]*"\s*\n\s*href="([^"]+)"', html)
        ]

    def test_the_page_offers_both_filters(self):
        self._gift(self.ana, 12, 25)

        html = self.client.get(reverse("gifts:upcoming")).content.decode()
        self.assertIn("Solo pendientes", html)
        self.assertIn("Solo este día", html)

    def test_toggling_pending_keeps_the_day_filter(self):
        links = self._filter_links("?date=2026-12-25&pending=1&only_day=1")

        self.assertEqual(links[0], "date=2026-12-25&pending=0&only_day=1")

    def test_toggling_the_day_filter_keeps_pending(self):
        links = self._filter_links("?date=2026-12-25&pending=1&only_day=1")

        self.assertEqual(links[1], "date=2026-12-25&pending=1&only_day=0")

    def test_the_two_filter_links_are_never_the_same(self):
        # Usar el mismo tag de alternancia en los dos enlaces los deja idénticos
        # y desactiva ambos filtros de golpe.
        for query in ("?date=2026-12-25",
                      "?date=2026-12-25&pending=1",
                      "?date=2026-12-25&only_day=1",
                      "?date=2026-12-25&pending=1&only_day=1"):
            links = self._filter_links(query)
            self.assertEqual(len(links), 2, query)
            self.assertNotEqual(links[0], links[1], query)

    def test_both_filters_start_from_a_clean_state(self):
        links = self._filter_links("?date=2026-12-25")

        self.assertEqual(
            links,
            ["date=2026-12-25&pending=1&only_day=0", "date=2026-12-25&pending=0&only_day=1"],
        )

    def test_day_links_carry_both_filters_over(self):
        # Al pulsar otro día se cambia de día, no de filtro.
        html = self.client.get(
            reverse("gifts:upcoming") + "?date=2026-12-25&pending=1&only_day=1",
        ).content.decode()
        href = re.search(r'class="calendar__day-link[^"]*"\s*\n?\s*href="([^"]+)"', html).group(1)

        self.assertIn("&pending=1&only_day=1", href.replace("&amp;", "&"))

    def test_month_arrows_carry_both_filters_over(self):
        html = self.client.get(
            reverse("gifts:upcoming") + "?date=2026-12-25&pending=1&only_day=1",
        ).content.decode()
        arrow = re.search(r'href="([^"]*only_day[^"]*)"', html).group(1)

        self.assertIn("&pending=1&only_day=1", arrow.replace("&amp;", "&"))
