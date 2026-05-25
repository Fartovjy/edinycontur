import mimetypes
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from apps.accounts.constants import ROLE_DRIVER
from apps.accounts.permissions import get_user_role

from .models import Attachment


def _can_download_attachment(user, attachment):
    role = get_user_role(user)
    if role == ROLE_DRIVER:
        driver = attachment.request.assigned_driver
        return bool(driver and driver.user_id == user.id)
    return user.is_authenticated


@login_required
def attachment_download(request, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("request", "request__assigned_driver"), pk=pk)
    if not _can_download_attachment(request.user, attachment):
        raise PermissionDenied
    if not attachment.file:
        raise Http404

    try:
        file_handle = attachment.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc

    filename = Path(attachment.file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(file_handle, as_attachment=False, filename=filename, content_type=content_type)
