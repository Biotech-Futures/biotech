from datetime import datetime, timedelta
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions
)
import os

ACCOUNT_NAME = "btfuturesblobstorage"
ACCOUNT_KEY = "SLreKCgSbLMq9th/QXYaSfPGwsRo75J/JxV0OFOp9ZkrRcnuTULShfhpID3aLzxYixGlKSzrWkFR+AStamaR4g==" # Turn into env variable later
CONTAINER_NAME = "media"

blob_service = BlobServiceClient(
    f"https://{ACCOUNT_NAME}.blob.core.windows.net",
    credential=ACCOUNT_KEY
)
container = blob_service.get_container_client(CONTAINER_NAME)

def upload_file(local_path: str, blob_name: str):
    with open(local_path, "rb") as data:
        container.upload_blob(name=blob_name, data=data, overwrite=True)
    return blob_name

def generate_sas_url(blob_name: str, expiry_minutes: int = 60):
    '''This generates a signed URL, but read access is only temporary. It's for dev use only, for now.'''
    sas = generate_blob_sas(
        account_name=ACCOUNT_NAME,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=ACCOUNT_KEY,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes)
    )
    return f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}?{sas}"
