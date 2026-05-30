"""Сервисный слой для чек-листов."""

from .models import ChecklistTemplate, RequestChecklistItem


def create_checklist_for_request(request_obj):
    """Создаёт snapshot чек-листов из активных шаблонов для новой заявки.

    Вызывается из views при создании заявки (обычной и из PDF).
    Идемпотентно: если у заявки уже есть пункты — повторно не создаёт.
    """
    if RequestChecklistItem.objects.filter(request=request_obj).exists():
        return 0

    items_to_create = []
    templates = (
        ChecklistTemplate.objects
        .filter(is_active=True)
        .prefetch_related("items")
    )
    for tpl in templates:
        for tpl_item in tpl.items.filter(is_active=True):
            items_to_create.append(RequestChecklistItem(
                request=request_obj,
                role=tpl.role,
                text=tpl_item.text,
                order=tpl_item.order,
                template_item=tpl_item,
            ))

    if items_to_create:
        RequestChecklistItem.objects.bulk_create(items_to_create)
    return len(items_to_create)
