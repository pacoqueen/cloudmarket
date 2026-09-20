#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.test import RequestFactory, TestCase

# Create your tests here.

from .models import Gift, Person, Item
from .services import extract_product_image
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
