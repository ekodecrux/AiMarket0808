export const locationCurrency: Record<string, string> = { "United States": "USD", "United Kingdom": "GBP", India: "INR", Canada: "CAD", Australia: "AUD", Germany: "EUR", France: "EUR", Singapore: "SGD", "United Arab Emirates": "AED", Japan: "JPY", Brazil: "BRL", Mexico: "MXN", "South Africa": "ZAR" };
export const currencyForLocation = (country: string, fallback = "USD") => locationCurrency[country] ?? fallback;
export const safeNumber = (value: string) => Math.max(0, Number(value) || 0);
export const entityId = (record: Record<string, unknown>) => String(record._id ?? record.id ?? "");
