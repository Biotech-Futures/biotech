# apps/chat/management/azure_storage.py
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from django.conf import settings

def _account_name():
    # btfuturesblobstorage.blob.core.windows.net -> btfuturesblobstorage
    return settings.AZURE_CUSTOM_DOMAIN.split(".")[0]

def blob_service():
    return BlobServiceClient(
        f"https://{settings.AZURE_CUSTOM_DOMAIN}",
        credential=settings.AZURE_ACCOUNT_KEY
    )

def upload_stream(file_obj, blob_name: str, content_type: str | None = None):
    container = blob_service().get_container_client(settings.AZURE_CONTAINER)
    if content_type:
        from azure.storage.blob import ContentSettings
        container.upload_blob(name=blob_name, data=file_obj, overwrite=True,
                              content_settings=ContentSettings(content_type=content_type))
    else:
        container.upload_blob(name=blob_name, data=file_obj, overwrite=True)
    # canonical (no SAS) URL to store in DB
    return f"https://{settings.AZURE_CUSTOM_DOMAIN}/{settings.AZURE_CONTAINER}/{blob_name}"

def generate_sas_url(canonical_url: str, minutes: int = 5) -> str:
    prefix = f"https://{settings.AZURE_CUSTOM_DOMAIN}/"
    container_and_blob = canonical_url.replace(prefix, "", 1)
    container, blob_name = container_and_blob.split("/", 1)

    sas = generate_blob_sas(
        account_name=_account_name(),
        container_name=container,
        blob_name=blob_name,
        account_key=settings.AZURE_ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=minutes),
    )
    return f"{canonical_url}?{sas}"
