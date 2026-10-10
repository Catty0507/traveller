import type { DailyWeather } from "../api/types";
import { todayStr } from "../utils/date";

export default function WeatherStrip({ days }: { days: DailyWeather[] }) {
  const today = todayStr();
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {days.map((d) => (
        <div
          key={d.date}
          className="flex min-w-[4.25rem] flex-col items-center gap-1 rounded-2xl bg-slate-50 px-2 py-3 ring-1 ring-slate-100 transition-colors hover:bg-sky-50"
        >
          <span
            className={`text-xs ${
              d.date === today ? "font-semibold text-sky-600" : "text-slate-400"
            }`}
          >
            {d.date === today ? "今天" : d.date.slice(5)}
          </span>
          <span className="text-2xl" title={d.desc}>
            {d.emoji}
          </span>
          <span className="text-xs font-medium text-slate-600">
            {Math.round(d.t_min)}~{Math.round(d.t_max)}°C
          </span>
          <span className="text-[10px] text-sky-500">
            {d.rain_prob !== null ? `雨${d.rain_prob}%` : d.desc}
          </span>
        </div>
      ))}
    </div>
  );
}
