from urllib.parse import urlparse

from django.db import models

# Create your models here.

class Item(models.Model):
    description = models.CharField(max_length = 256)
    url = models.URLField(blank = True)
    notes = models.TextField(blank = True)
    photo = models.ImageField(upload_to = "img", blank = True)
    image_url = models.URLField(blank = True, help_text = "Foto del producto obtenida de la página de compra.")

    def __str__(self):
        return self.description

    def url_host(self):
        """Devuelve el dominio del enlace del artículo (si lo hay)."""
        if not self.url:
            return ""
        try:
            return urlparse(self.url).netloc
        except ValueError:
            return ""

    def favicon_url(self):
        """Favicon del sitio del artículo, usado como miniatura."""
        host = self.url_host()
        if not host:
            return ""
        return ("https://www.google.com/s2/favicons?domain={}&sz=64").format(host)

    def preview_url(self):
        """Miniatura del artículo: la foto subida, la del producto o el favicon del sitio."""
        if self.photo:
            return self.photo.url
        if self.image_url:
            return self.image_url
        return self.favicon_url()


class Person(models.Model):
    name = models.CharField(max_length=128)
    birthdate = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class Gift(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    date = models.DateField()
    done = models.BooleanField(default=False)
    price = models.FloatField(default=None, blank=True)

    def __str__(self):
        return self.item.description + " → " + self.person.name
