from django import forms
from django.core.validators import URLValidator
from django.db.models.functions import Lower
from django.utils import timezone

from .models import Person


PUBLIC_URL_VALIDATOR = URLValidator(schemes=["http", "https"])


class GiftFormBase(forms.Form):
    """Campos comunes para crear y editar un regalo."""

    url = forms.URLField(
        label="URL del artículo",
        max_length=2000,
        required=False,
        validators=[PUBLIC_URL_VALIDATOR],
        help_text="URL de la página del producto.",
    )
    person = forms.ModelChoiceField(
        label="Destinatario",
        queryset=Person.objects.order_by(Lower("name")),
        help_text="Para quién es el regalo.",
    )
    date = forms.DateField(
        label="Fecha prevista del regalo",
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Puedes cambiarla antes de guardar.",
    )
    description = forms.CharField(
        label="Descripción",
        max_length=256,
        help_text="Descripción del artículo.",
    )
    price = forms.FloatField(
        label="Precio (€)",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
    )
    image_url = forms.URLField(
        label="URL de la imagen",
        required=False,
        validators=[PUBLIC_URL_VALIDATOR],
        help_text="URL de la imagen del producto.",
    )
    notes = forms.CharField(
        label="Notas",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    is_public = forms.BooleanField(
        label="Visible para visitantes no registrados",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial")
        if initial is None:
            initial = {}
            kwargs["initial"] = initial
        initial.setdefault("date", timezone.localdate())
        super().__init__(*args, **kwargs)


class GiftCreateForm(GiftFormBase):
    """Formulario para crear un regalo a partir de una URL de producto."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["url"].required = True


class GiftEditForm(GiftFormBase):
    """Formulario para editar todos los datos de un regalo y su artículo."""

    photo = forms.ImageField(
        label="Foto subida",
        required=False,
    )
    done = forms.BooleanField(label="Ya regalado", required=False)
    remove_photo = forms.BooleanField(
        label="Eliminar la foto subida",
        required=False,
    )
