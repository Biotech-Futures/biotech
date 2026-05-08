import tempfile
from pathlib import Path

from azure.storage.blob import BlobServiceClient

'''
For testing blob uploads. If upload successful but URL is not authorised, it will return "PublicAccessNotPermitted"
'''
account_name = "btfuturesblobstorage"
account_key = "SLreKCgSbLMq9th/QXYaSfPGwsRo75J/JxV0OFOp9ZkrRcnuTULShfhpID3aLzxYixGlKSzrWkFR+AStamaR4g=="
container_name = "media"

connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

blob_name = "azure_test_upload.txt"

# Stage the payload in the OS temp dir so the artifact never lands in the repo,
# even if the script aborts before cleanup.
with tempfile.TemporaryDirectory() as tmpdir:
    local_path = Path(tmpdir) / blob_name
    local_path.write_text("This is a test file uploaded from Django.")

    with local_path.open("rb") as data:
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(data, overwrite=True)

print(f"Uploaded '{blob_name}' successfully")

blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
print(f"📂 Accessible at: {blob_url}")
