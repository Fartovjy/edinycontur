import logging

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_SUPPLY, ROLE_TRANSPORT, ROLE_WAREHOUSE
from apps.accounts.models import UserProfile
from apps.logistics.constants import (
    STATUS_CREATED,
    STATUS_DELIVERED,
    STATUS_IN_TRANSIT,
    STATUS_IN_WAREHOUSE,
    STATUS_PROBLEM,
    STATUS_READY_TO_SHIP,
    STATUS_TRANSPORT_ASSIGNED,
)
from apps.logistics.models import RequestStatusHistory
from apps.problems.models import ProblemReport


logger = logging.getLogger(__name__)

ROLE_RECIPIENTS_BY_STATUS = {
    STATUS_CREATED: {ROLE_SUPPLY},
    STATUS_IN_WAREHOUSE: {ROLE_WAREHOUSE},
    STATUS_READY_TO_SHIP: {ROLE_TRANSPORT},
    STATUS_PROBLEM: {ROLE_MANAGER, ROLE_ADMIN},
}


def _telegram_api(method):
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}"


def _chat_id_for_user(user):
    if not user or not user.is_active:
        return ""
    try:
        profile = user.profile
    except ObjectDoesNotExist:
        profile = None
    return getattr(profile, "telegram_id", "")


def _users_by_roles(roles):
    """Return users in roles who want Telegram notifications and have telegram_id set."""
    if not roles:
        return []

    users_by_id = {}

    for profile in UserProfile.objects.select_related("user").filter(
        role__in=roles,
        is_active=True,
        user__is_active=True,
        notify_via_telegram=True,
    ):
        if _chat_id_for_user(profile.user):
            users_by_id[profile.user_id] = profile.user

    return list(users_by_id.values())


def _users_by_roles_for_email(roles):
    """Return users in roles who want email notifications and have email address set."""
    if not roles:
        return []

    users_by_id = {}

    for profile in UserProfile.objects.select_related("user").filter(
        role__in=roles,
        is_active=True,
        user__is_active=True,
        notify_via_email=True,
    ):
        if profile.user.email:
            users_by_id[profile.user_id] = profile.user

    return list(users_by_id.values())


def _latest_open_problem(request_obj):
    return (
        ProblemReport.objects.select_related("responsible_user", "responsible_user__profile")
        .filter(request=request_obj)
        .filter(status__in=[ProblemReport.OPEN, ProblemReport.IN_PROGRESS])
        .order_by("-created_at")
        .first()
    )


def _recipient_chat_ids(status, request_obj):
    chat_ids = set()

    for user in _users_by_roles(ROLE_RECIPIENTS_BY_STATUS.get(status, set())):
        chat_id = _chat_id_for_user(user)
        if chat_id:
            chat_ids.add(str(chat_id))

    if status in {STATUS_TRANSPORT_ASSIGNED, STATUS_IN_TRANSIT} and request_obj.assigned_driver:
        driver_chat_id = request_obj.assigned_driver.chat_id
        if driver_chat_id:
            chat_ids.add(str(driver_chat_id))

    if status == STATUS_DELIVERED:
        # Notify request creator (if they have Telegram and notifications enabled)
        creator = request_obj.created_by
        if creator:
            try:
                prof = creator.profile
                if prof.notify_via_telegram and prof.telegram_id:
                    chat_ids.add(str(prof.telegram_id))
            except ObjectDoesNotExist:
                pass
        for user in _users_by_roles({ROLE_TRANSPORT}):
            chat_id = _chat_id_for_user(user)
            if chat_id:
                chat_ids.add(str(chat_id))

    if status == STATUS_PROBLEM:
        problem = _latest_open_problem(request_obj)
        if problem and problem.responsible_user:
            try:
                prof = problem.responsible_user.profile
                if prof.notify_via_telegram and prof.telegram_id:
                    chat_ids.add(str(prof.telegram_id))
            except ObjectDoesNotExist:
                pass

    return chat_ids


def _recipient_emails(status, request_obj):
    """Collect email recipients for a status change."""
    emails = set()

    for user in _users_by_roles_for_email(ROLE_RECIPIENTS_BY_STATUS.get(status, set())):
        if user.email:
            emails.add(user.email)

    if status == STATUS_DELIVERED:
        creator = request_obj.created_by
        if creator:
            try:
                prof = creator.profile
                if prof.notify_via_email and creator.email:
                    emails.add(creator.email)
            except ObjectDoesNotExist:
                pass
        for user in _users_by_roles_for_email({ROLE_TRANSPORT}):
            if user.email:
                emails.add(user.email)

    if status == STATUS_PROBLEM:
        problem = _latest_open_problem(request_obj)
        if problem and problem.responsible_user:
            try:
                prof = problem.responsible_user.profile
                if prof.notify_via_email and problem.responsible_user.email:
                    emails.add(problem.responsible_user.email)
            except ObjectDoesNotExist:
                pass

    return emails


def _message_text(history, link):
    request_obj = history.request
    return (
        f"Заявка {request_obj.request_number}\n"
        f"Статус: {history.get_old_status_display() or '-'} -> {history.get_new_status_display()}\n"
        f"Клиент: {request_obj.client_name}\n"
        f"Регион: {request_obj.region}\n"
        f"{link}"
    )


def _keyboard(request_obj, link, include_driver_actions=False):
    buttons = []
    if include_driver_actions:
        driver_buttons = []
        if request_obj.status == STATUS_IN_TRANSIT:
            driver_buttons.append({"text": "Доставлено", "callback_data": f"request:{request_obj.id}:{STATUS_DELIVERED}"})
        driver_buttons.append({"text": "Проблема", "callback_data": f"request:{request_obj.id}:{STATUS_PROBLEM}"})
        buttons.append(driver_buttons)
    buttons.append([{"text": "Открыть заявку", "url": link}])
    return {"inline_keyboard": buttons}


def _send_telegram(chat_id, text, keyboard):
    try:
        requests.post(
            _telegram_api("sendMessage"),
            json={"chat_id": chat_id, "text": text, "reply_markup": keyboard},
            timeout=5,
        )
    except requests.RequestException as exc:
        logger.warning("Telegram notification failed for chat_id=%s: %s", chat_id, exc)


def _send_email(subject, text, recipient_list):
    if not recipient_list or not settings.EMAIL_HOST_USER:
        return
    try:
        send_mail(subject, text, settings.DEFAULT_FROM_EMAIL, list(recipient_list), fail_silently=False)
    except Exception as exc:
        logger.warning("Email notification failed for %s: %s", recipient_list, exc)


@receiver(post_save, sender=RequestStatusHistory)
def notify_responsible_roles_on_status_change(sender, instance, created, **kwargs):
    if not created:
        return

    request_obj = instance.request
    link = f"{settings.WEB_APP_BASE_URL}{request_obj.get_absolute_url()}"
    text = _message_text(instance, link)

    # ── Telegram ──────────────────────────────────────────────────────────
    if settings.TELEGRAM_BOT_TOKEN:
        chat_ids = _recipient_chat_ids(instance.new_status, request_obj)
        for chat_id in chat_ids:
            include_driver_actions = (
                request_obj.assigned_driver
                and str(request_obj.assigned_driver.chat_id) == str(chat_id)
            )
            _send_telegram(chat_id, text, _keyboard(request_obj, link, include_driver_actions=include_driver_actions))

    # ── Email ─────────────────────────────────────────────────────────────
    emails = _recipient_emails(instance.new_status, request_obj)
    if emails:
        subject = f"Единый Контур: заявка {request_obj.request_number} — {instance.get_new_status_display()}"
        _send_email(subject, text, emails)
