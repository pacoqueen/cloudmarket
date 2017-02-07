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
