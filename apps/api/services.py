"""FCM push-уведомления через firebase-admin."""

import logging
import os

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _init_firebase():
    """Инициализация firebase-admin (один раз при первом вызове)."""
    global _firebase_initialized
    if _firebase_initialized:
        return True

    credentials_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    if not credentials_path:
        logger.warning("FIREBASE_CREDENTIALS_PATH не задан — push-уведомления отключены.")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        return True
    except Exception as exc:
        logger.error("Ошибка инициализации Firebase: %s", exc)
        return False


def send_push_to_user(user, title: str, body: str, request_id: int | None = None):
    """
    Отправить FCM push-уведомление всем устройствам пользователя.

    Возвращает количество успешно отправленных сообщений.
    Токены с ошибкой 'unregistered' удаляются автоматически.
    """
    if not _init_firebase():
        return 0

    from .models import DeviceToken

    tokens = list(
        DeviceToken.objects.filter(user=user).values_list("fcm_token", flat=True)
    )
    if not tokens:
        return 0

    try:
        from firebase_admin import messaging

        data_payload = {"title": title, "body": body}
        if request_id is not None:
            data_payload["request_id"] = str(request_id)

        # Отправляем data-only сообщение с высоким приоритетом.
        # Это гарантирует, что onMessageReceived() будет вызван на устройстве
        # в любом состоянии (foreground / background / killed) и приложение само
        # отобразит уведомление через правильный канал "ek_default".
        # notification-payload намеренно не используется: при background-доставке
        # Android выбирает канал из него, а несовпадение channel_id приводит к
        # тихому удалению уведомления на Android 8+.
        messages = [
            messaging.Message(
                data=data_payload,
                android=messaging.AndroidConfig(
                    priority="high",
                ),
                token=token,
            )
            for token in tokens
        ]

        response = messaging.send_each(messages)
        success_count = response.success_count

        # Удаляем невалидные токены (устройство удалило приложение)
        invalid_tokens = []
        for i, resp in enumerate(response.responses):
            if not resp.success:
                exc = resp.exception
                if exc and hasattr(exc, "code") and exc.code in (
                    "registration-token-not-registered",
                    "invalid-registration-token",
                ):
                    invalid_tokens.append(tokens[i])
                else:
                    logger.warning("FCM ошибка для токена …%s: %s", tokens[i][-8:], exc)

        if invalid_tokens:
            deleted, _ = DeviceToken.objects.filter(fcm_token__in=invalid_tokens).delete()
            logger.info("Удалено %d невалидных FCM-токенов", deleted)

        logger.debug("FCM: отправлено %d/%d пользователю %s", success_count, len(tokens), user)
        return success_count

    except Exception as exc:
        logger.error("Ошибка отправки FCM push пользователю %s: %s", user, exc)
        return 0
