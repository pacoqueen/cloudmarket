from django.contrib import admin

# Register your models here.

from .models import Gift, Person, Item

class ItemAdmin(admin.ModelAdmin):
    fieldsets = [
            (None,          {'fields': ['description', 'url']}),
            ('Más info',    {'fields': ['notes', 'photo'],
                             'classes': ['collapse']}),
            ]
    list_display = ('description', 'photo')


class GiftAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'date', 'price', 'done')
    list_filter = ('date', 'price')

admin.site.register(Person)
admin.site.register(Gift, GiftAdmin)
admin.site.register(Item, ItemAdmin)
