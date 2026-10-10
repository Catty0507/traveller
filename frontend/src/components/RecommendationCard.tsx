import type { Recommendation } from "../api/types";
import { coverGradient, primaryTagEmoji } from "../constants/colors";
import type { DriveState, GuideState } from "../hooks/useRecommend";
import DriveSection from "./DriveSection";
import GuideSection from "./GuideSection";
import WeatherStrip from "./WeatherStrip";

interface Props {
  rec: Recommendation;
  guide: GuideState | undefined;
  drive: DriveState | undefined;
  hasOrigin: boolean;
  onRetryGuide: () => void;
  onRequestDrive: () => void;
  onRetryDrive: () => void;
  onCancelDrive: () => void;
}

export default function RecommendationCard({
  rec,
  guide,
  drive,
  hasOrigin,
  onRetryGuide,
  onRequestDrive,
  onRetryDrive,
  onCancelDrive,
}: Props) {
  const { city, weather } = rec;

  // 行程区间是窗口内安排的一段(按城市建议天数),与建议天数对比着说
  const tripDays = weather.total_days;
  const fmtDate = (iso: string) => iso.slice(5).replace("-", "/");
  const dayHint =
    tripDays === city.suggested_days
      ? `安排 ${tripDays} 天,节奏刚好`
      : tripDays > city.suggested_days
        ? `安排 ${tripDays} 天,玩得更从容`
        : `建议 ${city.suggested_days} 天,这趟安排 ${tripDays} 天更紧凑`;

  // 自驾方案覆盖整个时间窗口,与原攻略互斥:展示自驾时收起原攻略;租车建议则是补充,两者共存
  const driveActive = drive?.status === "done" && drive.data!.plan.mode === "drive";
  const rentalShown = drive?.status === "done" && drive.data!.plan.mode === "rental";
  const driveBusy = drive?.status === "loading";
  const toggleOff = driveActive || rentalShown;

  return (
    <article className="overflow-hidden rounded-3xl bg-white shadow-md shadow-slate-900/5 ring-1 ring-slate-100 transition-shadow hover:shadow-lg hover:shadow-slate-900/5">
      <div className={`bg-gradient-to-br px-6 py-6 md:px-8 ${coverGradient(city.cover_color)}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/70 text-2xl shadow-sm">
              {primaryTagEmoji(city.tags)}
            </span>
            <div>
              <h3 className="text-xl font-bold text-slate-800 md:text-2xl">{city.name_zh}</h3>
              <p className="mt-0.5 text-sm text-slate-600">
                {city.country} · {fmtDate(rec.trip_start)} ~ {fmtDate(rec.trip_end)} · {dayHint}
              </p>
              <p className="mt-1.5 text-sm leading-5 text-slate-600/90">{city.summary}</p>
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            {rec.distance_km != null && (
              <span className="rounded-full bg-white/70 px-3 py-1 text-xs font-semibold text-slate-500">
                {rec.distance_km === 0 ? "就在本地" : `距你约 ${rec.distance_km.toLocaleString()} km`}
              </span>
            )}
            <span className="rounded-full bg-slate-900/70 px-3 py-1 text-xs font-semibold tracking-wide text-white">
              TOP {rec.rank}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-4 px-6 py-6 md:px-8">
        <WeatherStrip days={weather.days} />
        <p className="text-xs text-slate-400">{weather.summary_text}</p>

        <div className="rounded-2xl bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-800 ring-1 ring-sky-100">
          💡 {rec.reason}
        </div>

        {rec.warning && (
          <div className="rounded-2xl bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-700 ring-1 ring-amber-100">
            ⚠️ {rec.warning}
          </div>
        )}

        {rec.matched_tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {rec.matched_tags.map((t) => (
              <span
                key={t}
                className="rounded-full bg-emerald-50 px-3 py-1 text-xs text-emerald-600"
              >
                契合偏好 · {t}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={toggleOff ? onCancelDrive : onRequestDrive}
            disabled={!hasOrigin || driveBusy}
            title={
              !hasOrigin
                ? "先在上方设置「出发地」,重新推荐后即可规划自驾"
                : driveActive
                  ? "取消自驾模式,恢复原来的行程攻略"
                  : "规划从出发地出发的自驾方案"
            }
            className={
              toggleOff
                ? "inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:border-slate-400 hover:bg-slate-50"
                : "inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-sky-600 to-cyan-500 px-4 py-1.5 text-sm font-semibold text-white shadow-sm shadow-sky-600/20 transition-transform hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
            }
          >
            {driveBusy ? "规划中…" : driveActive ? "↩️ 取消自驾,恢复原方案" : rentalShown ? "收起租车建议" : "🚗 我要自驾"}
          </button>
          <span className="text-xs text-slate-400">
            {!hasOrigin
              ? "先在上方设置「出发地」,重新推荐后即可规划自驾"
              : driveActive
                ? "已切换为自驾方案,原攻略暂时收起"
                : rentalShown
                  ? "自驾时间不够,原方案保留,租车建议附在下方"
                  : "从出发地一路玩过去;时间不够就改当地租车"}
          </span>
        </div>

        <DriveSection state={drive} cityName={city.name_zh} onRetry={onRetryDrive} />

        {!driveActive && (
          <div className="border-t border-slate-100 pt-5">
            <h4 className="mb-3 text-sm font-semibold text-slate-700">
              ✈️ {city.name_zh} 攻略
            </h4>
            <GuideSection state={guide} cityName={city.name_zh} onRetry={onRetryGuide} />
          </div>
        )}
      </div>
    </article>
  );
}
