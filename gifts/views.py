#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic
from django.views.decorators.http import require_POST
from django.db.models.functions import Lower

from .models import Gift, Person


def public_queryset(queryset, request):
    """Si el visitante no está registrado, deja fuera los regalos privados."""
    if not request.user.is_authenticated:
        return queryset.filter(is_public=True)
    return queryset


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
