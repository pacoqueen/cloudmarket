#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand

from gifts.models import Item
from gifts.services import fetch_product_image


class Command(BaseCommand):
    help = "Busca la foto del producto en la página de compra de cada artículo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reintentar incluso los artículos que ya tienen image_url.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Número máximo de artículos a procesar.",
        )

    def handle(self, *args, **options):
        queryset = Item.objects.all()
        if not options["force"]:
            queryset = queryset.filter(url__gt="", image_url="")
        else:
            queryset = queryset.filter(url__gt="")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        total = updated = 0
        for item in queryset:
            total += 1
            found = fetch_product_image(item.url)
            if found:
                item.image_url = found
                item.save(update_fields=["image_url"])
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS("{} -> {}".format(item, found))
                )

        self.stdout.write(
            self.style.WARNING(
                "Procesados {}, actualizados {} ({} sin imagen).".format(
                    total, updated, total - updated
                )
            )
        )