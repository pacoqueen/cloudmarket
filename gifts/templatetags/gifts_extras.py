from django import template

register = template.Library()

# Los filtros de la página de calendario se enean entre sí: al activar o
# desactivar uno hay que conservar el resto y el día seleccionado. Escribir la
# query string a mano en cada enlace es la forma fácil de que un filtro borre al
# otro sin que se note, así que estos tags la reconstruyen desde la URL viva.
#
#   ?date=…{% query_toggle 'pending' %}{% query_keep 'only_day' %}
#
# query_toggle invierte el parámetro (el que cambia el enlace) y query_keep lo
# copia tal cual (los que sólo se arrastran). Usar query_toggle en ambos deja
# los dos enlaces idénticos y desactiva los filtros de golpe.


def _flag(context, name):
    """1 si el parámetro está activo en la query string actual, 0 si no."""
    request = context.get("request")
    return "1" if request is not None and request.GET.get(name) == "1" else "0"


@register.simple_tag(takes_context=True)
def query_toggle(context, name):
    """Devuelve «&nombre=1» o «&nombre=0», alternando el parámetro actual.

    Para el filtro que el enlace activa o desactiva.
    """
    return "&%s=%s" % (name, "0" if _flag(context, name) == "1" else "1")


@register.simple_tag(takes_context=True)
def query_keep(context, name):
    """Devuelve «&nombre=<valor actual>» sin tocarlo.

    Para arrastrar el resto de filtros. Si un enlace usa query_toggle sobre los
    dos parámetros acaba desactivándolos ambos a la vez, así que el que no es el
    asunto del enlace tiene que ir con query_keep.
    """
    return "&%s=%s" % (name, _flag(context, name))
