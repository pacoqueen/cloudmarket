# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.urls import re_path

from . import views

app_name = 'cloudmarket'

urlpatterns = [
    re_path(r'^$', views.UserListView.as_view(),
            name='list'
            ),
    re_path(r'^~redirect/$', views.UserRedirectView.as_view(),
            name='redirect'
            ),
    re_path(r'^(?P<username>[\w.@+-]+)/$', views.UserDetailView.as_view(),
            name='detail'
            ),
    re_path(r'^~update/$', views.UserUpdateView.as_view(),
            name='update'
            ),
]
