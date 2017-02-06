from django.contrib import admin

# Register your models here.

from gifts.models import Gift, Person, Item

admin.site.register(Person)
#admin.site.register(Item)
admin.site.register(Gift)

class ItemAdmin(admin.ModelAdmin):
    fieldsets = [
            (None,          {'fields': ['description', 'url']}),
            ('Más info',    {'fields': ['notes', 'photo'],
                             'classes': ['collapse']}),
            ]
admin.site.register(Item, ItemAdmin)
