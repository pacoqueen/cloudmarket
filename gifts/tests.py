#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.test import RequestFactory, TestCase

# Create your tests here.

from .models import Gift, Person, Item
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
