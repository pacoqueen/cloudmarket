#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import re_path
from . import views

app_name = 'gifts'
urlpatterns = [# por ejemplo: /gifts/
               re_path(r'^$', views.IndexView.as_view(), name = "index"),
               # por ejemplo: /gifts/5
               re_path(r'^(?P<pk>[0-9]+)/$', views.DetailView.as_view(), name = "detail"),
               # por ejemplo: /gifts/5/mark
               re_path(r'^(?P<gift_id>[0-9]+)/mark/$', views.mark, name = "mark"),
               # por ejemplo: /gifts/5/set_public
               re_path(r'^(?P<gift_id>[0-9]+)/set_public/$', views.set_public, name = "set_public"),
              ]
