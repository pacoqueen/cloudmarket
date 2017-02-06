from django.db import models

# Create your models here.

class Item(models.Model):
    description = models.CharField(max_length = 256)
    url = models.URLField(blank = True)
    notes = models.TextField(blank = True)
    photo = models.ImageField(upload_to = "img", blank = True)

    def __str__(self):
        return self.description


class Person(models.Model):
    name = models.CharField(max_length=128)
    birthdate = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class Gift(models.Model):
    person = models.ForeignKey(Person)
    item = models.ForeignKey(Item)
    date = models.DateField()
    done = models.BooleanField(default=False)
    price = models.FloatField(default=None, blank=True)

    def __str__(self):
        return self.item.description + " → " + self.person.name
