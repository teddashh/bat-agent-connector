import { invoke, isTauri } from "@tauri-apps/api/core";

export const nativeDesktop = isTauri();
export interface ConnectorResponse { status: number; data: any }
export interface NativeStatus { endpoint: string | null; error: string | null; credential_available: boolean }
export const nativeStatus = () => invoke<NativeStatus>("native_status");
export const nativeConnect = () => invoke<any>("connector_connect");
export const nativeDisconnect = () => invoke<void>("connector_disconnect");
export const openExternal = (url: string) => invoke<void>("open_external", { url });

export async function connectorRequest(method: string, path: string, body: unknown, key: string | undefined,
  browserToken: string): Promise<ConnectorResponse> {
  if (nativeDesktop) {
    return invoke<ConnectorResponse>("connector_request", { input: {
      method, path, body: body ?? null, idempotency_key: key ?? null
    } });
  }
  const headers: Record<string, string> = { Authorization: `Bearer ${browserToken}` };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (key) headers["Idempotency-Key"] = key;
  const res = await fetch(`/api/v1${path}`, { method, headers,
    body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, data: await res.json().catch(() => ({})) };
}

export async function connectorUploadArtifact(operationId: string, bytes: ArrayBuffer,
  browserToken: string): Promise<ConnectorResponse> {
  if (!/^op_[0-9a-f]{32}$/.test(operationId)) throw new Error("Invalid artifact upload operation ID");
  if (nativeDesktop) {
    if (bytes.byteLength > 16 * 1024 * 1024) throw new Error("Artifact exceeds the native 16 MiB upload limit");
    return invoke<ConnectorResponse>("connector_upload_artifact", bytes, {headers: {"x-batc-upload-operation": operationId}});
  }
  // Ignore content_url from operation metadata. Tokens only reach this same-origin fixed route.
  const res = await fetch(`/api/v1/artifacts/uploads/${operationId}/content`, {method: "POST", redirect: "error",
    headers: {Authorization: `Bearer ${browserToken}`, "Content-Type": "application/octet-stream"}, body: bytes});
  return {status: res.status, data: await res.json().catch(() => ({}))};
}
