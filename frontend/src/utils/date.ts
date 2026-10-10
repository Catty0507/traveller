export function toLocalISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function todayStr(): string {
  return toLocalISO(new Date());
}

/** 天气预报窗口:今天起最多 16 天(今天 + 15)。 */
export function maxDateStr(): string {
  return addDays(todayStr(), 15);
}

export function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + n);
  return toLocalISO(d);
}

/** 最近的一个周六日(若今天就是周末,则从今天开始)。 */
export function thisWeekend(): [string, string] {
  const now = new Date();
  const day = now.getDay();
  const deltaToSat = day === 6 ? 0 : (6 - day) % 7;
  const sat = addDays(toLocalISO(now), deltaToSat);
  return [sat, addDays(sat, 1)];
}
