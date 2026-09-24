#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
