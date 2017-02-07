#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.test import TestCase

# Create your tests here.

from .models import Gift, Person, Item


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
