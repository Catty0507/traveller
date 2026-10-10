import { addDays, maxDateStr, thisWeekend, todayStr } from "../utils/date";

interface Props {
  start: string;
  end: string;
  onStart: (v: string) => void;
  onEnd: (v: string) => void;
}

export default function DateRangePicker({ start, end, onStart, onEnd }: Props) {
  const min = todayStr();
  const max = maxDateStr();

  const quickPicks: { label: string; range: [string, string] }[] = [
    { label: "本周末", range: thisWeekend() },
    { label: "未来3天", range: [min, addDays(min, 2)] },
    { label: "未来7天", range: [min, addDays(min, 6)] },
  ];

  const applyRange = (range: [string, string]) => {
    onStart(range[0]);
    onEnd(range[1]);
  };

  const isStartInvalid = end !== "" && start !== "" && end < start;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-slate-500 shrink-0">📅 空闲时间</span>
        <input
          type="date"
          value={start}
          min={min}
          max={max}
          onChange={(e) => onStart(e.target.value)}
          className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
        />
        <span className="text-slate-400">至</span>
        <input
          type="date"
          value={end}
          min={start || min}
          max={max}
          onChange={(e) => onEnd(e.target.value)}
          className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
        />
        <span className="text-xs text-slate-400">最多 16 天内</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {quickPicks.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => applyRange(p.range)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              start === p.range[0] && end === p.range[1]
                ? "bg-sky-100 text-sky-700 border-sky-300"
                : "bg-white text-slate-500 border-slate-200 hover:border-sky-400"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {isStartInvalid && (
        <p className="text-xs text-rose-500">结束日期不能早于出发日期</p>
      )}
    </div>
  );
}
