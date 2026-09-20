#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic

from .models import Gift


class IndexView(generic.ListView):
    template_name = 'gifts/index.html'
    context_object_name = 'gift_list'

    def get_queryset(self):
        """Devuelve los regalos ordenados por estado y fecha: primero los pendientes."""
        queryset = Gift.objects.order_by("done", "-date")
        status = self.request.GET.get("status")
        if status == "done":
            queryset = queryset.filter(done=True)
        elif status == "pending":
            queryset = queryset.filter(done=False)
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
        context["current_status"] = self.request.GET.get("status", "")
        return context


class DetailView(generic.DetailView):
    model = Gift
    template_name = 'gifts/detail.html'


def mark(request, gift_id):
    gift = get_object_or_404(Gift, pk=gift_id)
    done = "done" in request.POST  # Only "on" checkmarks are submitted.
    gift.done = done
    gift.save()
    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    #return HttpResponseRedirect(reverse('gifts:detail', args=(gift_id, )))
    return HttpResponseRedirect(reverse('gifts:index'))
