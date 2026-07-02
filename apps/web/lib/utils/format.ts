export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function formatSnakeCase(value: string): string {
  return value.replaceAll("_", " ");
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
}
