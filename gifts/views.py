#!/usr/bin/env python
# -*- coding: utf-8 -*-

import calendar
import json
from datetime import date, datetime
from urllib.parse import urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models.functions import Lower
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.views.decorators.http import require_POST, require_http_methods

from .forms import GiftCreateForm, GiftEditForm
from .models import Gift, Item, Person
from .services import fetch_product_metadata


def public_queryset(queryset, request):
    """Si el visitante no está registrado, deja fuera los regalos privados."""
    if not request.user.is_authenticated:
        return queryset.filter(is_public=True)
    return queryset


def _metadata_initial(source_url):
    """Construye los valores iniciales del formulario a partir de una URL."""
    initial = {"url": source_url}
    metadata = fetch_product_metadata(source_url)
    if metadata:
        for field in ("url", "description", "price", "image_url"):
            if metadata.get(field) not in (None, ""):
                initial[field] = metadata[field]
    if not initial.get("description"):
        try:
            initial["description"] = urlparse(source_url).netloc or source_url
        except ValueError:
            initial["description"] = source_url
    return initial, bool(metadata)


def _submitted_initial(data):
    """Conserva los valores escritos por el usuario al solicitar el análisis."""
    initial = {}
    for field in ("url", "person", "date", "description", "price", "image_url", "notes", "is_public"):
        if field not in data:
            continue
        value = data.get(field)
        if field == "is_public":
            initial[field] = bool(value)
        elif value not in (None, ""):
            initial[field] = value
    return initial


@login_required
@require_http_methods(["GET", "POST"])
def add(request):
    """Crea un regalo desde una URL de producto o manualmente."""
    initial = {}
    metadata_notice = ""

    if request.method == "POST" and request.POST.get("analyze"):
        initial = _submitted_initial(request.POST)
        source_url = request.POST.get("url", "").strip()
        if not source_url:
            metadata_notice = "Escribe una URL para analizar antes de continuar."
        else:
            detected_initial, metadata_found = _metadata_initial(source_url)
            if metadata_found:
                for field in ("url", "description", "price", "image_url"):
                    if detected_initial.get(field) not in (None, ""):
                        initial[field] = detected_initial[field]
                initial["url"] = detected_initial.get("url") or source_url
            else:
                initial["url"] = source_url
                if not initial.get("description") and detected_initial.get("description"):
                    initial["description"] = detected_initial["description"]
                metadata_notice = (
                    "No se pudo obtener la información automáticamente. "
                    "Completa los campos que falten."
                )
        form = GiftCreateForm(initial=initial)
        return render(
            request,
            "gifts/add.html",
            {"form": form, "metadata_notice": metadata_notice},
        )

    if request.method == "GET":
        source_url = request.GET.get("url", "").strip()
        if source_url:
            initial, metadata_found = _metadata_initial(source_url)
            if not metadata_found:
                metadata_notice = (
                    "No se pudo obtener la información automáticamente. "
                    "Completa los campos que falten."
                )
        # Fecha sugerida (p. ej. el día marcado que no tiene ningún regalo
        # pendiente). Si viene mal, se ignora y se deja el campo vacío.
        suggested_date = request.GET.get("date", "").strip()
        if suggested_date:
            try:
                initial["date"] = datetime.strptime(suggested_date, "%Y-%m-%d").date()
            except ValueError:
                pass

    if request.method == "POST":
        form = GiftCreateForm(request.POST)
    else:
        form = GiftCreateForm(initial=initial)

    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            item, created = Item.objects.get_or_create(
                url=data["url"],
                defaults={
                    "description": data["description"],
                    "notes": data["notes"],
                    "image_url": data["image_url"],
                },
            )
            if not created:
                update_fields = []
                if data["notes"] and not item.notes:
                    item.notes = data["notes"]
                    update_fields.append("notes")
                if data["image_url"] and not item.image_url:
                    item.image_url = data["image_url"]
                    update_fields.append("image_url")
                if update_fields:
                    item.save(update_fields=update_fields)

            gift = Gift.objects.create(
                person=data["person"],
                item=item,
                date=data["date"],
                price=data["price"],
                is_public=data["is_public"],
            )

        messages.success(request, "Regalo añadido a tu lista.")
        return HttpResponseRedirect(reverse("gifts:detail", args=[gift.pk]))

    return render(
        request,
        "gifts/add.html",
        {"form": form, "metadata_notice": metadata_notice},
    )


@login_required
@require_http_methods(["GET"])
def bookmarklet(request):
    """Muestra las instrucciones para instalar el acceso rápido desde el navegador."""
    add_url = request.build_absolute_uri(reverse("gifts:add"))
    bookmarklet_url = (
        "javascript:(function(){"
        f"window.open({json.dumps(add_url)} + '?url=' + encodeURIComponent(window.location.href), "
        "'_blank', 'noopener');"
        "})();"
    )
    return render(
        request,
        "gifts/bookmarklet.html",
        {"bookmarklet_url": bookmarklet_url, "add_url": add_url},
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit(request, gift_id):
    """Edita los datos del artículo y del regalo seleccionado."""
    gift = get_object_or_404(
        Gift.objects.select_related("item", "person"),
        pk=gift_id,
    )

    if request.method == "POST":
        form = GiftEditForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                item = gift.item
                old_photo = item.photo
                item.description = data["description"]
                item.url = data["url"]
                item.notes = data["notes"]
                item.image_url = data["image_url"]
                if data["remove_photo"]:
                    if old_photo:
                        old_photo.delete(save=False)
                    item.photo = None
                elif data["photo"]:
                    item.photo = data["photo"]
                item.save()

                gift.person = data["person"]
                gift.date = data["date"]
                gift.price = data["price"]
                gift.done = data["done"]
                gift.is_public = data["is_public"]
                gift.save()

            messages.success(request, "Regalo actualizado correctamente.")
            return HttpResponseRedirect(reverse("gifts:detail", args=[gift.pk]))
    else:
        item = gift.item
        form = GiftEditForm(
            initial={
                "description": item.description,
                "url": item.url,
                "notes": item.notes,
                "image_url": item.image_url,
                "person": gift.person_id,
                "date": gift.date,
                "price": gift.price,
                "done": gift.done,
                "is_public": gift.is_public,
            }
        )

    return render(request, "gifts/edit.html", {"form": form, "gift": gift})


class IndexView(generic.ListView):
    template_name = 'gifts/index.html'
    context_object_name = 'gift_list'

    def _selected_person_ids(self):
        """Devuelve los id de las personas seleccionadas en el filtro (ignora valores inválidos)."""
        ids = []
        for raw in self.request.GET.getlist("person"):
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        return ids

    def get_queryset(self):
        """Devuelve los regalos ordenados por estado y fecha: primero los pendientes."""
        queryset = public_queryset(Gift.objects.order_by("done", "-date"), self.request)
        status = self.request.GET.get("status")
        if status == "done":
            queryset = queryset.filter(done=True)
        elif status == "pending":
            queryset = queryset.filter(done=False)
        person_ids = self._selected_person_ids()
        if person_ids:
            queryset = queryset.filter(person_id__in=person_ids)
        return queryset

    def get_context_data(self, **kwargs):
        """Agrupa los regalos por persona destinataria."""
        context = super().get_context_data(**kwargs)
        grouped = {}
        for gift in context["gift_list"]:
            grouped.setdefault(gift.person, []).append(gift)
        context["person_groups"] = [
            {"person": person, "gifts": gifts}
            for person, gifts in sorted(grouped.items(), key=lambda pair: pair[0].name.lower())
        ]
        selected_ids = self._selected_person_ids()
        context["current_status"] = self.request.GET.get("status", "")
        context["current_person_ids"] = selected_ids
        context["all_persons"] = Person.objects.filter(gift__in=context["gift_list"]).distinct().order_by(Lower("name"))
        context["person_qs"] = "&".join("person={}".format(pid) for pid in selected_ids)
        return context


class DetailView(generic.DetailView):
    model = Gift
    template_name = 'gifts/detail.html'

    def get_queryset(self):
        """Evita que un visitante anónimo vea regalos privados (404)."""
        return public_queryset(Gift.objects.all(), self.request)


def mark(request, gift_id):
    gift = get_object_or_404(public_queryset(Gift.objects.all(), request), pk=gift_id)
    done = "done" in request.POST  # Only "on" checkmarks are submitted.
    gift.done = done
    gift.save()
    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    #return HttpResponseRedirect(reverse('gifts:detail', args=(gift_id, )))
    return HttpResponseRedirect(reverse('gifts:index'))


@login_required
@require_POST
def set_public(request, gift_id):
    """Cambia la visibilidad de un regalo. Solo usuarios registrados."""
    gift = get_object_or_404(Gift, pk=gift_id)
    gift.is_public = "is_public" in request.POST
    gift.save(update_fields=["is_public"])
    return HttpResponseRedirect(reverse('gifts:detail', args=(gift_id, )))


class UpcomingView(generic.View):
    """Vista de calendario con los próximos regalos a hacer.

    La fecha importante es el día y el mes; el año se ignora, porque las
    fechas de regalo son recurrentes (un cumpleaños pasa todos los años).
    Eso hace que cualquier regalo vuelva a tocar dentro de los próximos
    12 meses, así que la lista siempre los contiene todos y lo que cambia
    al elegir un día es el orden: del más próximo al más lejano.
    """

    template_name = "gifts/upcoming.html"

    def get(self, request):
        # Fecha seleccionada (por defecto, hoy)
        date_str = request.GET.get("date")
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = date.today()
        else:
            selected_date = date.today()

        # Toggle de solo pendientes
        only_pending = request.GET.get("pending") == "1"

        from django.db.models.functions import ExtractDay, ExtractMonth

        # Consulta de regalos. El año se ignora: las fechas de regalo son
        # recurrentes (cumpleaños, etc.), así que cualquier regalo vuelve a
        # tocar dentro de los próximos 12 meses. Por eso no filtramos por rango
        # de meses: todos los regalos están "pendientes de caer"; lo que cambia
        # al elegir un día es el orden, de la fecha más próxima a la más lejana.
        queryset = public_queryset(Gift.objects.all(), request)
        if only_pending:
            queryset = queryset.filter(done=False)
        queryset = queryset.select_related("person", "item")

        def proximity(gift):
            """Distancia a la fecha seleccionada, ignorando el año.

            Devuelve un entero que ordena de la fecha más próxima a la más
            lejana dentro de un ciclo anual: meses que faltan hasta el próximo
            aniversario, más el día dentro de ese mes.
            """
            months = (gift.date.month - selected_date.month) % 12
            # Mismo mes pero día ya pasado: el próximo aniversario es el del año
            # siguiente, es decir, dentro de 12 meses.
            if months == 0 and gift.date.day < selected_date.day:
                months = 12
            return months * 32 + gift.date.day

        gifts = sorted(
            queryset,
            key=lambda gift: (
                proximity(gift),
                gift.person.name.lower(),
                gift.item.description.lower(),
            ),
        )

        # Agrupar por persona. El orden de los grupos lo fija el primer regalo de
        # cada uno al recorrer la lista, que ya viene ordenada por proximidad.
        grouped = {}
        for gift in gifts:
            grouped.setdefault(gift.person, []).append(gift)

        # Dentro de cada persona los pendientes van arriba. sort() es estable, así
        # que basta con ordenar por "done" (False < True): los pendientes quedan
        # primero y cada bloque mantiene su orden por proximidad. No se toca el
        # orden de los grupos, que sigue siendo por regalo más próximo.
        for group_gifts in grouped.values():
            group_gifts.sort(key=lambda gift: gift.done)

        # Días con regalos para el calendario (mes visible, ignorando el año y el estado)
        year = selected_date.year
        month = selected_date.month

        days_with_gifts = set(
            str(day) for day in
            public_queryset(Gift.objects.all(), request)
            .annotate(
                gift_month=ExtractMonth("date"),
                gift_day=ExtractDay("date"),
            )
            .filter(gift_month=month)
            .values_list("gift_day", flat=True)
            .distinct()
        )

        # Construir calendario mensual
        cal = calendar.Calendar(firstweekday=calendar.MONDAY)
        weeks = cal.monthdatescalendar(year, month)

        return render(request, self.template_name, {
            "selected_date": selected_date,
            "weeks": weeks,
            "days_with_gifts": days_with_gifts,
            "person_groups": [
                {
                    "person": person,
                    "gifts": group_gifts,
                    # Se despliega de entrada quien tenga algún regalo pendiente;
                    # el resto, plegado. Con el filtro de "solo pendientes" todos
                    # los grupos salen desplegados, que es lo coherente.
                    "has_pending": any(not gift.done for gift in group_gifts),
                }
                for person, group_gifts in grouped.items()
            ],
            "only_pending": only_pending,
            "today": date.today(),
            "gift_count": len(gifts),
        })
