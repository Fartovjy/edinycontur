import asyncio
import time

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import ROLE_DRIVER
from apps.accounts.models import UserProfile
from apps.logistics.constants import STATUS_CANCELLED, STATUS_CLOSED, STATUS_DELIVERED, STATUS_PROBLEM
from apps.logistics.models import LogisticsRequest, RequestStatusHistory
from apps.logistics.services import change_request_status
from apps.problems.models import ProblemReport
from apps.transport.models import Driver


router = Router()


def _web_url(request_obj):
    return f"{settings.WEB_APP_BASE_URL}{request_obj.get_absolute_url()}"


def _request_keyboard(request_obj):
    buttons = []
    if request_obj.status != STATUS_DELIVERED:
        buttons.append(
            [
                InlineKeyboardButton(text="Доставлено", callback_data=f"driver:delivered:{request_obj.id}"),
                InlineKeyboardButton(text="Проблема", callback_data=f"driver:problem:{request_obj.id}"),
            ]
        )
    else:
        buttons.append([InlineKeyboardButton(text="Проблема", callback_data=f"driver:problem:{request_obj.id}")])
    buttons.append([InlineKeyboardButton(text="Открыть заявку", url=_web_url(request_obj))])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мои заявки", callback_data="driver:list")],
        ]
    )


def _request_text(request_obj):
    return (
        f"Заявка {request_obj.request_number}\n"
        f"Клиент: {request_obj.client_name}\n"
        f"Адрес: {request_obj.client_address or '-'}\n"
        f"Груз: {request_obj.cargo_description}\n"
        f"Статус: {request_obj.get_status_display()}\n"
        f"План доставки: {request_obj.planned_delivery_date.strftime('%d.%m.%Y') if request_obj.planned_delivery_date else '-'}"
    )


def _driver_for_telegram(telegram_id, chat_id):
    telegram_id = str(telegram_id)
    chat_id = str(chat_id)

    profile = (
        UserProfile.objects.select_related("user", "user__driver_profile")
        .filter(telegram_id=telegram_id, role=ROLE_DRIVER, is_active=True, user__is_active=True)
        .first()
    )
    user = profile.user if profile else None

    if not user:
        profile = (
            UserProfile.objects.select_related("user", "user__driver_profile")
            .filter(user__telegram_chat_id=chat_id, role=ROLE_DRIVER, is_active=True, user__is_active=True)
            .first()
        )
        user = profile.user if profile else None

    driver = getattr(user, "driver_profile", None) if user else None
    if not driver:
        driver = Driver.objects.select_related("user", "user__profile").filter(telegram_chat_id=chat_id, is_active=True).first()
        user = driver.user if driver else None
        profile = getattr(user, "profile", None) if user else None

    if not driver or not user or not profile or profile.role != ROLE_DRIVER:
        return None

    changed_user = False
    if user.telegram_chat_id != chat_id:
        user.telegram_chat_id = chat_id
        changed_user = True
    if changed_user:
        user.save(update_fields=["telegram_chat_id"])

    if profile.telegram_id != telegram_id:
        profile.telegram_id = telegram_id
        profile.save(update_fields=["telegram_id"])

    if driver.telegram_chat_id != chat_id:
        driver.telegram_chat_id = chat_id
        driver.save(update_fields=["telegram_chat_id"])

    return driver


@sync_to_async
def get_driver_start_context(telegram_id, chat_id):
    driver = _driver_for_telegram(telegram_id, chat_id)
    if not driver:
        known_profile = UserProfile.objects.filter(telegram_id=str(telegram_id), is_active=True).first()
        return {"found": bool(known_profile), "is_driver": False}

    user = driver.user
    return {
        "found": True,
        "is_driver": True,
        "full_name": user.get_full_name() or user.username,
        "role_label": user.profile.get_role_display(),
    }


@sync_to_async
def get_driver_requests(telegram_id, chat_id):
    driver = _driver_for_telegram(telegram_id, chat_id)
    if not driver:
        return None

    requests = list(
        LogisticsRequest.objects.filter(assigned_driver=driver, is_archived=False)
        .exclude(status__in=[STATUS_CLOSED, STATUS_CANCELLED])
        .select_related("assigned_driver")
        .order_by("planned_delivery_date", "-updated_at")[:10]
    )
    return requests


@sync_to_async
def mark_driver_delivered(request_id, telegram_id, chat_id):
    driver = _driver_for_telegram(telegram_id, chat_id)
    if not driver:
        return None, "Бот доступен только привязанному водителю."

    request_obj = LogisticsRequest.objects.select_related("assigned_driver", "assigned_driver__user").filter(id=request_id).first()
    if not request_obj:
        return None, "Заявка не найдена."
    if request_obj.assigned_driver_id != driver.id:
        return request_obj, "Заявка не назначена этому водителю."
    if request_obj.status in {STATUS_CLOSED, STATUS_CANCELLED}:
        return request_obj, "Заявка уже закрыта или отменена."

    with transaction.atomic():
        old_status = request_obj.status
        request_obj.status = STATUS_DELIVERED
        request_obj.actual_delivery_date = timezone.localdate()
        request_obj.save(update_fields=["status", "actual_delivery_date", "updated_at"])
        if old_status != STATUS_DELIVERED:
            RequestStatusHistory.objects.create(
                request=request_obj,
                old_status=old_status,
                new_status=STATUS_DELIVERED,
                changed_by=driver.user,
                comment="Доставка отмечена водителем из Telegram",
            )
    return request_obj, ""


@sync_to_async
def mark_driver_problem(request_id, telegram_id, chat_id):
    driver = _driver_for_telegram(telegram_id, chat_id)
    if not driver:
        return None, "Бот доступен только привязанному водителю."

    request_obj = LogisticsRequest.objects.select_related("assigned_driver", "created_by").filter(id=request_id).first()
    if not request_obj:
        return None, "Заявка не найдена."
    if request_obj.assigned_driver_id != driver.id:
        return request_obj, "Заявка не назначена этому водителю."
    if request_obj.status in {STATUS_CLOSED, STATUS_CANCELLED}:
        return request_obj, "Заявка уже закрыта или отменена."

    try:
        with transaction.atomic():
            ProblemReport.objects.create(
                request=request_obj,
                problem_type=ProblemReport.OTHER,
                description="Проблема отмечена водителем из Telegram.",
                responsible_user=request_obj.created_by,
                created_by=driver.user,
            )
            change_request_status(request_obj, STATUS_PROBLEM, driver.user, "Проблема отмечена водителем из Telegram")
    except ValidationError as exc:
        return request_obj, str(exc)

    return request_obj, ""


async def answer_driver_requests(message_or_callback):
    message = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    telegram_id = message_or_callback.from_user.id if message_or_callback.from_user else message.chat.id
    requests = await get_driver_requests(telegram_id, message.chat.id)
    if requests is None:
        await message.answer("Telegram ID не найден у водителя. Обратитесь к администратору.")
        return
    if not requests:
        await message.answer("Назначенных заявок пока нет.")
        return

    await message.answer("Ваши заявки:")
    for request_obj in requests:
        await message.answer(_request_text(request_obj), reply_markup=_request_keyboard(request_obj))


@router.message(F.text == "/start")
async def start(message: Message):
    telegram_id = message.from_user.id if message.from_user else message.chat.id
    context = await get_driver_start_context(telegram_id, message.chat.id)
    if not context["found"]:
        await message.answer(
            "Telegram ID не найден в системе.\n"
            "Обратитесь к администратору, чтобы он привязал Telegram ID к профилю водителя."
        )
        return
    if not context["is_driver"]:
        await message.answer("Этот Telegram-бот доступен только водителям.")
        return

    await message.answer(
        "Единый Контур: режим водителя.\n"
        f"Пользователь: {context['full_name']}\n"
        f"Роль: {context['role_label']}\n\n"
        "Доступные команды:\n"
        "- /start\n"
        "- /requests - показать мои заявки\n\n"
        "В заявке доступны кнопки: Доставлено, Проблема и ссылка на веб-карточку.",
        reply_markup=_start_keyboard(),
    )


@router.message(F.text == "/requests")
async def requests_command(message: Message):
    await answer_driver_requests(message)


@router.callback_query(F.data == "driver:list")
async def requests_callback(callback: CallbackQuery):
    await callback.answer()
    await answer_driver_requests(callback)


@router.callback_query(F.data.startswith("driver:delivered:"))
async def delivered_callback(callback: CallbackQuery):
    request_id = int(callback.data.rsplit(":", 1)[1])
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, error = await mark_driver_delivered(request_id, telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return

    await callback.answer("Готово")
    await callback.message.answer(
        f"Заявка {request_obj.request_number}: доставлена.\n"
        f"{_web_url(request_obj)}"
    )


@router.callback_query(F.data.startswith("driver:problem:"))
async def problem_callback(callback: CallbackQuery):
    request_id = int(callback.data.rsplit(":", 1)[1])
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, error = await mark_driver_problem(request_id, telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return

    await callback.answer("Готово")
    await callback.message.answer(
        f"Заявка {request_obj.request_number}: проблема зарегистрирована.\n"
        "Добавьте подробный комментарий в веб-карточке заявки:\n"
        f"{_web_url(request_obj)}"
    )


class Command(BaseCommand):
    help = "Runs aiogram Telegram bot for driver actions."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stdout.write("TELEGRAM_BOT_TOKEN is empty. Bot is idle.")
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                return

        async def main():
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            dp = Dispatcher()
            dp.include_router(router)
            await dp.start_polling(bot)

        asyncio.run(main())
