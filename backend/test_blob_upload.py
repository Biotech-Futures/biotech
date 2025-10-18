from azure.storage.blob import BlobServiceClient
import os

'''
For testing blob uploads. If upload successful but URL is not authorised, it will return "PublicAccessNotPermitted"
'''
account_name = "btfuturesblobstorage"
account_key = "SLreKCgSbLMq9th/QXYaSfPGwsRo75J/JxV0OFOp9ZkrRcnuTULShfhpID3aLzxYixGlKSzrWkFR+AStamaR4g=="
container_name = "media"

connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

test_filename = "azure_test_upload.txt"
with open(test_filename, "w") as f:
    f.write("This is a test file uploaded from Django.")

with open(test_filename, "rb") as data:
    blob_client = container_client.get_blob_client(test_filename)
    blob_client.upload_blob(data, overwrite=True)

print(f"Uploaded '{test_filename}' successfully")

blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{test_filename}"
print(f"📂 Accessible at: {blob_url}")
os.remove(test_filename)
