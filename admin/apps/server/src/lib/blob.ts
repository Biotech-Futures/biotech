import { BlobServiceClient } from "@azure/storage-blob";
import { Readable } from "node:stream";

function getConnectionString() {
  return process.env.AZURE_STORAGE_CONNECTION_STRING?.trim();
}

function getContainerName() {
  return process.env.AZURE_STORAGE_CONTAINER?.trim() || "resources";
}

function ensureConfigured() {
  const connectionString = getConnectionString();
  if (!connectionString) {
    throw new Error(
      "Missing AZURE_STORAGE_CONNECTION_STRING. Please configure Azure Blob storage env vars.",
    );
  }
  return {
    connectionString,
    containerName: getContainerName(),
  };
}

async function getContainerClient() {
  const { connectionString, containerName } = ensureConfigured();
  const serviceClient = BlobServiceClient.fromConnectionString(connectionString);
  const containerClient = serviceClient.getContainerClient(containerName);
  await containerClient.createIfNotExists();
  return containerClient;
}

export async function uploadBlobFile(
  storageKey: string,
  bytes: ArrayBuffer,
  contentType?: string,
) {
  const containerClient = await getContainerClient();
  const blobClient = containerClient.getBlockBlobClient(storageKey);

  await blobClient.uploadData(Buffer.from(bytes), {
    blobHTTPHeaders: {
      blobContentType: contentType || "application/octet-stream",
    },
  });
}

export async function downloadBlobFile(storageKey: string) {
  const containerClient = await getContainerClient();
  const blobClient = containerClient.getBlobClient(storageKey);
  const exists = await blobClient.exists();
  if (!exists) return null;

  const response = await blobClient.download();
  const stream = response.readableStreamBody;
  if (!stream) return null;
  const bytes = await streamToArrayBuffer(stream);

  return {
    bytes,
    mime_type: response.contentType || "application/octet-stream",
  };
}

export async function deleteBlobFile(storageKey: string) {
  const containerClient = await getContainerClient();
  const blobClient = containerClient.getBlobClient(storageKey);
  await blobClient.deleteIfExists();
}

async function streamToArrayBuffer(stream: NodeJS.ReadableStream) {
  const chunks: Buffer[] = [];
  for await (const chunk of stream as Readable) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const merged = Buffer.concat(chunks);
  return merged.buffer.slice(
    merged.byteOffset,
    merged.byteOffset + merged.byteLength,
  );
}
