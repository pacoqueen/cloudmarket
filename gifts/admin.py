from django.contrib import admin

# Register your models here.

from .models import Gift, Person, Item
from .services import fetch_product_image

class ItemAdmin(admin.ModelAdmin):
    fieldsets = [
            (None,          {'fields': ['description', 'url']}),
            ('Más info',    {'fields': ['notes', 'photo', 'image_url'],
                             'classes': ['collapse']}),
            ]
    list_display = ('description', 'photo', 'image_url')
    actions = ['fetch_image']

    def fetch_image(self, request, queryset):
        updated = 0
        for item in queryset:
            if not item.url:
                continue
            found = fetch_product_image(item.url)
            if found:
                item.image_url = found
                item.save(update_fields=['image_url'])
                updated += 1
        if updated:
            self.message_user(
                request,
                '{} imagen(es) de producto actualizada(s).'.format(updated),
            )
        else:
            self.message_user(
                request,
                'No se encontró ninguna imagen de producto.',
                level='warning',
            )

    fetch_image.short_description = "Buscar imagen del producto"


class GiftInline(admin.StackedInline):
    model = Gift
    extra = 1


class GiftAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'date', 'price', 'done')
    list_filter = ('date', 'price')
    fields = ['person', 'item', 'date', 'price', 'done']


class PersonAdmin(admin.ModelAdmin):
    filedsets = [
            (None,      {'fields': ['name']}),
            ('Fecha',   {'fields': ['date'], 'classes': ['collapse']}),
            ]
    inlines = [GiftInline]

admin.site.register(Person, PersonAdmin)
admin.site.register(Gift, GiftAdmin)
admin.site.register(Item, ItemAdmin)
