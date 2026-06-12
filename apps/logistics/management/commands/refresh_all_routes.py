from django.core.management.base import BaseCommand

from apps.logistics.models import LogisticsRequest


class Command(BaseCommand):
    help = "Пересчитать маршрут (направление и дни) для всех заявок с адресом клиента"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Обработать только первые N заявок (0 = все)",
        )

    def handle(self, *args, **options):
        qs = (
            LogisticsRequest.objects
            .select_related("warehouse")
            .exclude(client_address="")
            .filter(warehouse__isnull=False)
            .order_by("id")
        )
        limit = options["limit"]
        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f"Найдено заявок с адресом: {total}")

        ok = 0
        fail = 0
        for req in qs:
            try:
                result = req.refresh_route_info()
                if result:
                    ok += 1
                    self.stdout.write(f"  [{req.request_number}] {req.route_direction_arrow} {req.route_direction_label} {req.route_distance_km} км {req.route_days} дн.")
                else:
                    fail += 1
                    self.stdout.write(f"  [{req.request_number}] — не удалось (адрес или API)")
            except Exception as exc:
                fail += 1
                self.stdout.write(self.style.ERROR(f"  [{req.request_number}] ошибка: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"\nГотово: {ok} обновлено, {fail} пропущено из {total}"))
