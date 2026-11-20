export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/gateway/${path}`, {
    ...options,
    cache: "no-store",
    // A whole frame can require up to 100 sequential ESP32 predictions.
    signal: AbortSignal.timeout(300000),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Không thể kết nối hệ thống (${response.status}). Kiểm tra backend và BACKEND_URL.`,
    );
  return body as T;
}
