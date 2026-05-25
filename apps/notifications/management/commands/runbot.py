import asyncio
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.constants import ROLE_DRIVER, ROLE_TRANSPORT
from apps.accounts.models import UserProfile
from apps.logistics.constants import (
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_DELIVERED,
    STATUS_PROBLEM,
    STATUS_READY_TO_SHIP,
    STATUS_SHIPPED,
    STATUS_TRANSPORT_ASSIGNED,
)
from apps.logistics.models import LogisticsRequest, RequestStatusHistory
from apps.logistics.services import change_request_status
from apps.notifications.services import create_role_notification
from apps.problems.models import ProblemReport
from apps.transport.models import Driver, Vehicle


router = Router()
PENDING_TRANSPORT_DATE = {}


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


def _driver_start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мои заявки", callback_data="driver:list")],
        ]
    )


def _transport_start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заявки транспорта", callback_data="transport:list")],
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


def _transport_request_text(request_obj):
    return (
        f"Заявка {request_obj.request_number}\n"
        f"Клиент: {request_obj.client_name}\n"
        f"Адрес: {request_obj.client_address or '-'}\n"
        f"Статус: {request_obj.get_status_display()}\n"
        f"Отправка: {request_obj.planned_ship_date.strftime('%d.%m.%Y') if request_obj.planned_ship_date else '-'}\n"
        f"Машина: {request_obj.assigned_vehicle or '-'}\n"
        f"Водитель: {request_obj.assigned_driver or '-'}"
    )


def _transport_request_keyboard(request_obj):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Машина", callback_data=f"transport:vehicles:{request_obj.id}"),
                InlineKeyboardButton(text="Водитель", callback_data=f"transport:drivers:{request_obj.id}"),
                InlineKeyboardButton(text="Дата", callback_data=f"transport:date:{request_obj.id}"),
            ],
            [InlineKeyboardButton(text="Открыть заявку", url=_web_url(request_obj))],
        ]
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

    driver = getattr(user, "driver_profile", None) if user else None
    if not driver:
        driver = Driver.objects.select_related("user", "user__profile").filter(telegram_chat_id=chat_id, is_active=True).first()
        user = driver.user if driver else None
        profile = getattr(user, "profile", None) if user else None

    if not driver or not user or not profile or profile.role != ROLE_DRIVER:
        return None

    if profile.telegram_id != telegram_id:
        profile.telegram_id = telegram_id
        profile.save(update_fields=["telegram_id"])

    if driver.telegram_chat_id != chat_id:
        driver.telegram_chat_id = chat_id
        driver.save(update_fields=["telegram_chat_id"])

    return driver


def _profile_for_telegram(telegram_id, chat_id, role):
    telegram_id = str(telegram_id)
    chat_id = str(chat_id)
    profile = (
        UserProfile.objects.select_related("user")
        .filter(telegram_id=telegram_id, role=role, is_active=True, user__is_active=True)
        .first()
    )
    if not profile:
        return None

    if profile.telegram_id != telegram_id:
        profile.telegram_id = telegram_id
        profile.save(update_fields=["telegram_id"])
    return profile


def _get_driver_start_context_sync(telegram_id, chat_id):
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
def get_driver_start_context(telegram_id, chat_id):
    return _get_driver_start_context_sync(telegram_id, chat_id)


@sync_to_async
def get_start_context(telegram_id, chat_id):
    driver_context = _get_driver_start_context_sync(telegram_id, chat_id)
    if driver_context["is_driver"]:
        driver_context["role"] = ROLE_DRIVER
        return driver_context

    transport_profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if transport_profile:
        user = transport_profile.user
        return {
            "found": True,
            "role": ROLE_TRANSPORT,
            "full_name": user.get_full_name() or user.username,
            "role_label": transport_profile.get_role_display(),
        }

    return {"found": driver_context["found"], "role": None}


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
def get_transport_requests(telegram_id, chat_id):
    profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if not profile:
        return None

    return list(
        LogisticsRequest.objects.filter(is_archived=False)
        .exclude(status__in=[STATUS_CLOSED, STATUS_CANCELLED, STATUS_DELIVERED])
        .select_related("assigned_vehicle", "assigned_driver")
        .order_by("planned_ship_date", "-updated_at")[:10]
    )


def _get_transport_request_sync(request_id, telegram_id, chat_id):
    profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if not profile:
        return None, "Бот доступен только транспортному отделу."
    request_obj = (
        LogisticsRequest.objects.select_related("assigned_vehicle", "assigned_driver")
        .filter(id=request_id, is_archived=False)
        .first()
    )
    if not request_obj:
        return None, "Заявка не найдена."
    return request_obj, ""


@sync_to_async
def get_transport_request(request_id, telegram_id, chat_id):
    return _get_transport_request_sync(request_id, telegram_id, chat_id)


@sync_to_async
def get_transport_vehicle_options(request_id, telegram_id, chat_id):
    request_obj, error = _get_transport_request_sync(request_id, telegram_id, chat_id)
    if error:
        return None, [], error
    vehicles = list(Vehicle.objects.filter(is_active=True).order_by("plate_number")[:10])
    return request_obj, vehicles, ""


@sync_to_async
def get_transport_driver_options(request_id, telegram_id, chat_id):
    request_obj, error = _get_transport_request_sync(request_id, telegram_id, chat_id)
    if error:
        return None, [], error
    drivers = list(Driver.objects.filter(is_active=True).order_by("full_name")[:10])
    return request_obj, drivers, ""


@sync_to_async
def set_transport_vehicle(request_id, vehicle_id, telegram_id, chat_id):
    profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if not profile:
        return None, "Бот доступен только транспортному отделу."
    request_obj = LogisticsRequest.objects.filter(id=request_id, is_archived=False).first()
    vehicle = Vehicle.objects.filter(id=vehicle_id, is_active=True).first()
    if not request_obj or not vehicle:
        return None, "Заявка или машина не найдена."
    request_obj.assigned_vehicle = vehicle
    request_obj.save(update_fields=["assigned_vehicle", "updated_at"])
    return request_obj, ""


@sync_to_async
def set_transport_driver(request_id, driver_id, telegram_id, chat_id):
    profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if not profile:
        return None, "Бот доступен только транспортному отделу."
    request_obj = LogisticsRequest.objects.filter(id=request_id, is_archived=False).first()
    driver = Driver.objects.filter(id=driver_id, is_active=True).first()
    if not request_obj or not driver:
        return None, "Заявка или водитель не найдены."
    request_obj.assigned_driver = driver
    request_obj.save(update_fields=["assigned_driver", "updated_at"])
    return request_obj, ""


@sync_to_async
def set_transport_ship_date(request_id, raw_date, telegram_id, chat_id):
    profile = _profile_for_telegram(telegram_id, chat_id, ROLE_TRANSPORT)
    if not profile:
        return None, "Бот доступен только транспортному отделу."
    request_obj = LogisticsRequest.objects.filter(id=request_id, is_archived=False).first()
    if not request_obj:
        return None, "Заявка не найдена."
    try:
        ship_date = datetime.strptime(raw_date.strip(), "%d.%m.%Y").date()
    except ValueError:
        return request_obj, "Введите дату в формате ДД.ММ.ГГГГ, например 25.05.2026."

    request_obj.planned_ship_date = ship_date
    request_obj.save(update_fields=["planned_ship_date", "updated_at"])
    return request_obj, ""


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
            create_role_notification(
                ROLE_TRANSPORT,
                request_obj,
                f"Заявка {request_obj.request_number} доставлена водителем.",
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


async def answer_transport_requests(message_or_callback):
    message = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    telegram_id = message_or_callback.from_user.id if message_or_callback.from_user else message.chat.id
    requests = await get_transport_requests(telegram_id, message.chat.id)
    if requests is None:
        await message.answer("Telegram ID не найден у транспортного отдела. Обратитесь к администратору.")
        return
    if not requests:
        await message.answer("Активных заявок для транспортного отдела пока нет.")
        return

    await message.answer("Заявки транспортного отдела:")
    for request_obj in requests:
        await message.answer(_transport_request_text(request_obj), reply_markup=_transport_request_keyboard(request_obj))


@router.message(F.text == "/start")
async def start(message: Message):
    telegram_id = message.from_user.id if message.from_user else message.chat.id
    context = await get_start_context(telegram_id, message.chat.id)
    if not context["found"]:
        await message.answer(
            "Telegram ID не найден в системе.\n"
            "Обратитесь к администратору, чтобы он привязал Telegram ID к профилю пользователя."
        )
        return

    if context["role"] == ROLE_DRIVER:
        await message.answer(
            "Единый Контур: режим водителя.\n"
            f"Пользователь: {context['full_name']}\n"
            f"Роль: {context['role_label']}\n\n"
            "Доступные команды:\n"
            "- /start\n"
            "- /requests - показать мои заявки\n\n"
            "В заявке доступны кнопки: Доставлено, Проблема и ссылка на веб-карточку.",
            reply_markup=_driver_start_keyboard(),
        )
        return
    if context["role"] != ROLE_TRANSPORT:
        await message.answer("Этот Telegram-бот доступен водителям и транспортному отделу.")
        return

    await message.answer(
        "Единый Контур: транспортный отдел.\n"
        f"Пользователь: {context['full_name']}\n"
        f"Роль: {context['role_label']}\n\n"
        "Доступные команды:\n"
        "- /start\n"
        "- /requests - показать заявки транспорта\n\n"
        "В заявке доступны кнопки: Машина, Водитель, Дата и ссылка на веб-карточку.",
        reply_markup=_transport_start_keyboard(),
    )


@router.message(F.text == "/requests")
async def requests_command(message: Message):
    telegram_id = message.from_user.id if message.from_user else message.chat.id
    context = await get_start_context(telegram_id, message.chat.id)
    if context.get("role") == ROLE_TRANSPORT:
        await answer_transport_requests(message)
    else:
        await answer_driver_requests(message)


@router.callback_query(F.data == "driver:list")
async def requests_callback(callback: CallbackQuery):
    await callback.answer()
    await answer_driver_requests(callback)


@router.callback_query(F.data == "transport:list")
async def transport_requests_callback(callback: CallbackQuery):
    await callback.answer()
    await answer_transport_requests(callback)


@router.callback_query(F.data.startswith("transport:vehicles:"))
async def transport_vehicles_callback(callback: CallbackQuery):
    request_id = int(callback.data.rsplit(":", 1)[1])
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, vehicles, error = await get_transport_vehicle_options(request_id, telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(vehicle), callback_data=f"transport:set_vehicle:{request_obj.id}:{vehicle.id}")]
            for vehicle in vehicles
        ]
    )
    await callback.answer()
    await callback.message.answer(f"Выберите машину для заявки {request_obj.request_number}:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("transport:drivers:"))
async def transport_drivers_callback(callback: CallbackQuery):
    request_id = int(callback.data.rsplit(":", 1)[1])
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, drivers, error = await get_transport_driver_options(request_id, telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(driver), callback_data=f"transport:set_driver:{request_obj.id}:{driver.id}")]
            for driver in drivers
        ]
    )
    await callback.answer()
    await callback.message.answer(f"Выберите водителя для заявки {request_obj.request_number}:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("transport:set_vehicle:"))
async def transport_set_vehicle_callback(callback: CallbackQuery):
    _, _, request_id, vehicle_id = callback.data.split(":", 3)
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, error = await set_transport_vehicle(int(request_id), int(vehicle_id), telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return
    await callback.answer("Готово")
    await callback.message.answer(_transport_request_text(request_obj), reply_markup=_transport_request_keyboard(request_obj))


@router.callback_query(F.data.startswith("transport:set_driver:"))
async def transport_set_driver_callback(callback: CallbackQuery):
    _, _, request_id, driver_id = callback.data.split(":", 3)
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, error = await set_transport_driver(int(request_id), int(driver_id), telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return
    await callback.answer("Готово")
    await callback.message.answer(_transport_request_text(request_obj), reply_markup=_transport_request_keyboard(request_obj))


@router.callback_query(F.data.startswith("transport:date:"))
async def transport_date_callback(callback: CallbackQuery):
    request_id = int(callback.data.rsplit(":", 1)[1])
    telegram_id = callback.from_user.id if callback.from_user else callback.message.chat.id
    request_obj, error = await get_transport_request(request_id, telegram_id, callback.message.chat.id)
    if error:
        await callback.answer("Не выполнено", show_alert=True)
        await callback.message.answer(error)
        return

    PENDING_TRANSPORT_DATE[callback.message.chat.id] = request_id
    await callback.answer()
    await callback.message.answer(
        f"Введите дату отправки для заявки {request_obj.request_number} в формате ДД.ММ.ГГГГ."
    )


@router.message(F.text.regexp(r"^\d{2}\.\d{2}\.\d{4}$"))
async def transport_date_message(message: Message):
    request_id = PENDING_TRANSPORT_DATE.get(message.chat.id)
    if not request_id:
        return
    telegram_id = message.from_user.id if message.from_user else message.chat.id
    request_obj, error = await set_transport_ship_date(request_id, message.text, telegram_id, message.chat.id)
    if error:
        await message.answer(error)
        return

    PENDING_TRANSPORT_DATE.pop(message.chat.id, None)
    await message.answer(_transport_request_text(request_obj), reply_markup=_transport_request_keyboard(request_obj))


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
    help = "Runs aiogram Telegram bot for driver and transport actions."

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
