from django import template


register = template.Library()


@register.filter
def status_label(statuses, code):
    return statuses.get(code, code)
