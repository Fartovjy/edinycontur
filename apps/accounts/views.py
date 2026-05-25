import secrets
import string

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def _gen_token():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


@login_required
def profile_view(request):
    profile = request.user.profile

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "gen_token":
            profile.telegram_link_token = _gen_token()
            profile.save(update_fields=["telegram_link_token"])
            messages.success(request, "Новый код сгенерирован. Отправьте его боту: /start КОД")
            return redirect("profile")

        if action == "clear_telegram":
            profile.telegram_id = ""
            profile.telegram_link_token = ""
            profile.notify_via_telegram = False
            profile.save(update_fields=["telegram_id", "telegram_link_token", "notify_via_telegram"])
            messages.success(request, "Telegram отвязан.")
            return redirect("profile")

        # save preferences
        notify_telegram = "notify_via_telegram" in request.POST
        notify_email = "notify_via_email" in request.POST
        email = request.POST.get("email", "").strip()

        profile.notify_via_telegram = notify_telegram
        profile.notify_via_email = notify_email
        profile.save(update_fields=["notify_via_telegram", "notify_via_email"])

        if email != request.user.email:
            request.user.email = email
            request.user.save(update_fields=["email"])

        messages.success(request, "Настройки уведомлений сохранены.")
        return redirect("profile")

    from django.conf import settings as django_settings
    bot_name = getattr(django_settings, "TELEGRAM_BOT_NAME", "biovetk_bot")

    return render(request, "accounts/profile.html", {
        "profile": profile,
        "bot_name": bot_name,
    })
