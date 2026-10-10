import type { GuideState } from "../hooks/useRecommend";

interface Props {
  state: GuideState | undefined;
  cityName: string;
  onRetry: () => void;
}

const TIP_STYLES: Record<string, string> = {
  穿衣: "bg-rose-50 text-rose-600",
  雨具: "bg-sky-50 text-sky-600",
  交通: "bg-emerald-50 text-emerald-600",
  门票: "bg-amber-50 text-amber-600",
  其他: "bg-slate-100 text-slate-500",
};

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-4 w-3/4 rounded bg-slate-100" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 rounded-xl bg-slate-100" />
        ))}
      </div>
      <div className="h-4 w-1/2 rounded bg-slate-100" />
      <div className="h-20 rounded-xl bg-slate-100" />
      <p className="text-center text-xs text-slate-400">正在为你写攻略…</p>
    </div>
  );
}

export default function GuideSection({ state, cityName, onRetry }: Props) {
  if (!state || state.status === "loading") return <Skeleton />;

  if (state.status === "error") {
    return (
      <div className="rounded-xl bg-slate-50 px-4 py-3 flex items-center justify-between gap-3">
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

  const guide = state.data!.guide;

  return (
    <div className="space-y-5">
      <p className="text-sm leading-6 text-slate-600">{guide.overview}</p>

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">📍 景点推荐</h4>
        <div className="grid gap-3 sm:grid-cols-2">
          {guide.attractions.map((a) => (
            <div key={a.name} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium text-slate-800">{a.name}</span>
                <span className="shrink-0 text-xs text-slate-400">{a.duration}</span>
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-500">{a.highlight}</p>
              <p className="mt-1 text-xs leading-5 text-sky-600">💡 {a.tip}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">🗓️ 每日行程</h4>
        <div className="space-y-2">
          {guide.daily_plan.map((d) => (
            <div key={d.day} className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-100">
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

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">🍜 必吃美食</h4>
        <div className="flex flex-wrap gap-2">
          {guide.food.map((f) => (
            <span
              key={f.name}
              className="rounded-full bg-orange-50 px-3 py-1.5 text-xs text-orange-700"
              title={f.desc}
            >
              {f.name} · {f.desc}
            </span>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">💡 出行贴士</h4>
        <ul className="space-y-1.5">
          {guide.tips.map((t, i) => (
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

      <p className="text-[11px] text-slate-300">
        攻略内容仅供参考,价格与开放信息请以实际为准。祝你在{cityName}玩得开心!
      </p>
    </div>
  );
}
