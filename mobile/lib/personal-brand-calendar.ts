import * as Calendar from "expo-calendar";
import { Platform } from "react-native";
import { weeklyVisibilityRoutine } from "@/lib/personal-brand-model";

const weekdayOffsets = [1, 2, 3, 4, 5];
function nextWeekday(offset: number) { const date = new Date(); const day = date.getDay(); const delta = (offset - day + 7) % 7 || 7; date.setDate(date.getDate() + delta); date.setHours(9, 0, 0, 0); return date; }
export async function addWeeklyVisibilityReminders() {
  if (Platform.OS === "web" || !(await Calendar.isAvailableAsync())) return { ok: false, reason: "Calendar reminders are available in the installed Android or iOS app." };
  const permission = await Calendar.requestCalendarPermissionsAsync();
  if (permission.status !== Calendar.PermissionStatus.GRANTED) return { ok: false, reason: "Calendar permission was not granted." };
  const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
  const calendar = calendars.find((item) => item.allowsModifications);
  if (!calendar) return { ok: false, reason: "No writable calendar is available on this device." };
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  await Promise.all(weeklyVisibilityRoutine.map(async (item, index) => { const startDate = nextWeekday(weekdayOffsets[index]); const endDate = new Date(startDate.getTime() + 20 * 60 * 1000); await Calendar.createEventAsync(calendar.id, { title: `NEXUS Personal Brand: ${item.title}`, notes: item.detail, startDate, endDate, timeZone: timezone, alarms: [{ relativeOffset: -10 }], recurrenceRule: { frequency: Calendar.Frequency.WEEKLY } }); }));
  return { ok: true, reason: "Five recurring visibility reminders were added to your device calendar." };
}
