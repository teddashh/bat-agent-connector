import { invoke, isTauri } from "@tauri-apps/api/core";

export const nativeDesktop = isTauri();
export interface ConnectorResponse { status: number; data: any }
export interface NativeStatus { endpoint: string | null; error: string | null; credential_available: boolean }
export const nativeStatus = () => invoke<NativeStatus>("native_status");
export const nativeConnect = () => invoke<any>("connector_connect");
export const nativeDisconnect = () => invoke<void>("connector_disconnect");
export const openExternal = (url: string) => invoke<void>("open_external", { url });
export const fleetAvailability = () => invoke<{configured: boolean; platform_supported: boolean; error?: string}>("fleet_availability");
export type FleetRequest = {action: "status" | "contract" | "validate_configuration"}
  | {action: "set_connections"; connections: string[]; expected_configuration_binding: string; expected_selection_revision: string; expected_monitor_epoch: string | null}
  | {action: "ensure_monitor"; expected_configuration_binding: string}
  | {action: "quit_owned"; expected_configuration_binding: string; expected_monitor_epoch: string};
export const fleetRequest = (input: FleetRequest) => invoke<any>("fleet_request", {input});

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
