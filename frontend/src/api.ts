let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body)
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-Documind-CSRF", csrf);
  const response = await fetch("/api/v1" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const message =
      typeof result.detail === "string"
        ? result.detail
        : Array.isArray(result.detail)
          ? result.detail.map((item: { msg: string }) => item.msg).join("; ")
          : "Request failed. Try again.";
    throw new Error(message);
  }
  return response.json();
}
export function money(value: string | null | undefined) {
  if (value == null) return "—";
  const parsed = /^(-?)(\d+)(?:\.(\d{0,2}))?$/.exec(value);
  if (!parsed) return value;
  // Keep server decimal strings exact, even above JavaScript's safe-number range.
  const whole = new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 0,
  }).format(BigInt(parsed[2]));
  return `${parsed[1]}₹${whole}.${(parsed[3] || "").padEnd(2, "0")}`;
}
export function label(value: string) {
  return value.replaceAll("_", " ");
}
