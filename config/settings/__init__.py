# -*- coding: utf-8 -*-

# Ugly hacks to fix some Django versioning changes
import django
from django.utils.translation import gettext, gettext_lazy
django.utils.translation.ugettext = gettext
django.utils.translation.ugettext_lazy = gettext_lazy

from django.utils.encoding import force_str
django.utils.encoding.force_text = force_str

