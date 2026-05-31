"""Бэкфилл чек-листов для уже существующих активных заявок.

Применяет текущие активные шаблоны ко всем заявкам в рабочих
(не завершённых) статусах, у которых ещё нет пунктов чек-листа.

Использование:
    python manage.py backfill_checklists                  # все активные заявки без чек-листа
    python manage.py backfill_checklists --include-done   # включая Доставлено / Закрыто / Отменено
    python manage.py backfill_checklists --dry-run        # показать что будет сделано, не записывать
"""

from django.core.management.base import BaseCommand

from apps.checklists.services import create_checklist_for_request
from apps.logistics.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_DELIVERED
from apps.logistics.models import LogisticsRequest


COMPLETED_STATUSES = {STATUS_DELIVERED, STATUS_CLOSED, STATUS_CANCELLED}


class Command(BaseCommand):
    help = "Создать snapshot-чек-листы для существующих заявок без пунктов."

    def add_arguments(self, parser):
        parser.add_argument("--include-done", action="store_true",
                            help="Включить заявки в завершённых статусах.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Не записывать в БД, только показать.")

    def handle(self, *args, **opts):
        include_done = opts["include_done"]
        dry_run = opts["dry_run"]

        qs = LogisticsRequest.objects.filter(checklist_items__isnull=True).distinct()
        if not include_done:
            qs = qs.exclude(status__in=COMPLETED_STATUSES)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Заявок к обработке: {total}"))
        if dry_run:
            for r in qs.order_by("id")[:50]:
                self.stdout.write(f"  → #{r.id} {r.request_number} ({r.status})")
            if total > 50:
                self.stdout.write(f"  … и ещё {total - 50}")
            self.stdout.write(self.style.WARNING("DRY RUN — записи не сделаны."))
            return

        created_items = 0
        touched_requests = 0
        for r in qs:
            n = create_checklist_for_request(r)
            if n > 0:
                created_items += n
                touched_requests += 1

        self.stdout.write(self.style.SUCCESS(
            f"Готово. Обновлено заявок: {touched_requests}; пунктов создано: {created_items}."
        ))
