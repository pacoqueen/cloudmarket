#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.conf.urls import url
from . import views

app_name = 'gifts'
urlpatterns = [# por ejemplo: /gifts/
               url(r'^$', views.IndexView.as_view(), name = "index"),
               # por ejemplo: /gifts/5
               url(r'^(?P<pk>[0-9]+)/$', views.DetailView.as_view(), name = "detail"),
               # por ejemplo: /gifts/5/mark
               url(r'^(?P<gift_id>[0-9]+)/mark/$', views.mark, name = "mark"),
              ]
