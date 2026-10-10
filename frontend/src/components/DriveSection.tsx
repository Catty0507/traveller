import type { DriveState } from "../hooks/useRecommend";

interface Props {
  state: DriveState | undefined;
  cityName: string;
  onRetry: () => void;
}

const TIP_STYLES: Record<string, string> = {
  路线: "bg-sky-50 text-sky-600",
  驾驶: "bg-violet-50 text-violet-600",
  天气: "bg-amber-50 text-amber-600",
  费用: "bg-emerald-50 text-emerald-600",
  其他: "bg-slate-100 text-slate-500",
};

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse rounded-2xl bg-sky-50/60 p-4 ring-1 ring-sky-100">
      <div className="h-4 w-2/3 rounded bg-sky-100" />
      <div className="h-16 rounded-xl bg-sky-100" />
      <div className="h-24 rounded-xl bg-sky-100" />
      <p className="text-center text-xs text-slate-400">正在规划自驾路线…</p>
    </div>
  );
}

export default function DriveSection({ state, cityName, onRetry }: Props) {
  if (!state) return null;

  if (state.status === "loading") return <Skeleton />;

  if (state.status === "error") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3">
        <p className="text-sm text-slate-500">{state.error}</p>
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 rounded-full border border-sky-300 px-3 py-1 text-xs text-sky-600 hover:bg-sky-50"
        >
          重试
        </button>
      </div>
    );
  }

  const { plan, origin_name, est_drive_km, est_drive_hours } = state.data!;

  return (
    <div className="space-y-4 rounded-2xl bg-sky-50/60 p-4 ring-1 ring-sky-100">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold text-slate-700">
          {plan.mode === "drive" ? "🚗 自驾方案" : "🚙 当地租车自驾"}
        </h4>
        <span className="text-xs text-slate-400">
          {origin_name} → {cityName}
        </span>
      </div>

      <p className="text-sm leading-6 text-slate-600">{plan.summary}</p>

      {plan.mode === "drive" && (
        <div className="flex flex-wrap gap-2 text-xs">
          {plan.total_km != null && (
            <span className="rounded-full bg-white px-3 py-1 text-slate-600 ring-1 ring-slate-200">
              往返约 {plan.total_km.toLocaleString()} km
            </span>
          )}
          {plan.total_drive_hours != null && (
            <span className="rounded-full bg-white px-3 py-1 text-slate-600 ring-1 ring-slate-200">
              纯驾驶约 {plan.total_drive_hours} 小时
            </span>
          )}
          {plan.depart_date && (
            <span className="rounded-full bg-white px-3 py-1 text-slate-600 ring-1 ring-slate-200">
              建议 {plan.depart_date} 出发
            </span>
          )}
          {plan.return_date && (
            <span className="rounded-full bg-white px-3 py-1 text-slate-600 ring-1 ring-slate-200">
              {plan.return_date} 返回
            </span>
          )}
        </div>
      )}

      {plan.route.length > 0 && (
        <section className="space-y-2">
          <h5 className="text-xs font-semibold text-slate-500">🛣️ 路线走法(单程约 {est_drive_km.toLocaleString()} km · 纯驾驶约 {est_drive_hours} 小时)</h5>
          <div className="space-y-1.5">
            {plan.route.map((leg) => (
              <div key={leg.title} className="rounded-xl bg-white px-3.5 py-2.5 ring-1 ring-slate-100">
                <span className="mr-2 inline-flex h-5 items-center rounded-md bg-sky-100 px-1.5 text-[11px] font-bold text-sky-700">
                  {leg.title}
                </span>
                <span className="text-xs leading-5 text-slate-500">{leg.desc}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {plan.mode === "rental" && plan.rentals.length > 0 && (
        <section className="space-y-2">
          <h5 className="text-xs font-semibold text-slate-500">🔑 当地租车推荐</h5>
          <div className="grid gap-2 sm:grid-cols-2">
            {plan.rentals.map((r) => (
              <div key={r.name} className="rounded-xl bg-white px-3.5 py-2.5 ring-1 ring-slate-100">
                <p className="text-sm font-medium text-slate-700">{r.name}</p>
                <p className="mt-0.5 text-xs leading-5 text-slate-500">{r.desc}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {plan.daily_plan.length > 0 && (
        <section className="space-y-2">
          <h5 className="text-xs font-semibold text-slate-500">🗓️ 逐日安排</h5>
          <div className="space-y-1.5">
            {plan.daily_plan.map((d) => (
              <div key={d.day} className="rounded-xl bg-white px-3.5 py-2.5 ring-1 ring-slate-100">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex h-6 items-center rounded-lg bg-sky-600 px-2 text-[11px] font-bold text-white">
                    Day {d.day}
                  </span>
                  <span className="text-xs text-slate-400">{d.date}</span>
                  <span className="text-sm font-medium text-slate-700">{d.title}</span>
                </div>
                <p className="mt-1.5 text-xs leading-5 text-slate-500">{d.items.join(" → ")}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {plan.tips.length > 0 && (
        <section className="space-y-1.5">
          <h5 className="text-xs font-semibold text-slate-500">💡 自驾贴士</h5>
          <ul className="space-y-1.5">
            {plan.tips.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-xs leading-5 text-slate-500">
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    TIP_STYLES[t.category] ?? TIP_STYLES["其他"]
                  }`}
                >
                  {t.category}
                </span>
                <span>{t.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-[11px] text-slate-300">
        路线与租车信息仅供参考,出发前请以实际导航和门店信息为准。
      </p>
    </div>
  );
}
