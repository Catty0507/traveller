import { useState } from "react";
import type { City, Mode, Origin, RecommendRequestBody, Tag } from "../api/types";
import CityTab from "./CityTab";
import DateRangePicker from "./DateRangePicker";
import LocationPicker from "./LocationPicker";
import TagsTab from "./TagsTab";

interface Props {
  cities: City[];
  tags: Tag[];
  submitting: boolean;
  onSubmit: (body: RecommendRequestBody) => void;
}

export default function InputCard({ cities, tags, submitting, onSubmit }: Props) {
  const [mode, setMode] = useState<Mode>("cities");
  const [selectedCityIds, setSelectedCityIds] = useState<string[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [origin, setOrigin] = useState<Origin | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const toggle = (list: string[], id: string) =>
    list.includes(id) ? list.filter((x) => x !== id) : [...list, id];

  const selectionCount = mode === "cities" ? selectedCityIds.length : selectedTagIds.length;
  const datesReady = start !== "" && end !== "" && end >= start;
  const canSubmit = selectionCount > 0 && datesReady && !submitting;

  const handleSubmit = () => {
    if (!canSubmit) return;
    const body: RecommendRequestBody = {
      mode,
      start_date: start,
      end_date: end,
    };
    if (mode === "cities") body.city_ids = selectedCityIds;
    else body.tags = selectedTagIds;
    if (origin) body.origin = origin;
    onSubmit(body);
  };

  return (
    <section className="space-y-6 rounded-3xl bg-white p-6 shadow-xl shadow-sky-900/5 ring-1 ring-slate-100 md:p-8">
      <div className="inline-flex rounded-full bg-slate-100 p-1">
        {(
          [
            ["cities", "选择想去的地方"],
            ["tags", "按偏好推荐"],
          ] as [Mode, string][]
        ).map(([m, label]) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-all ${
              mode === m
                ? "bg-white text-sky-700 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "cities" ? (
        <CityTab
          cities={cities}
          selected={selectedCityIds}
          onToggle={(id) => setSelectedCityIds((prev) => toggle(prev, id))}
        />
      ) : (
        <TagsTab
          tags={tags}
          selected={selectedTagIds}
          onToggle={(id) => setSelectedTagIds((prev) => toggle(prev, id))}
        />
      )}

      <LocationPicker cities={cities} origin={origin} onChange={setOrigin} />

      <DateRangePicker start={start} end={end} onStart={setStart} onEnd={setEnd} />

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">
          {!datesReady
            ? "先选好日期"
            : selectionCount === 0
              ? mode === "cities"
                ? "至少选择 1 个城市(最多 10 个)"
                : "至少选择 1 个偏好标签(最多 4 个)"
              : mode === "cities"
                ? `已选 ${selectionCount} 个城市`
                : `已选 ${selectionCount} 个偏好`}
        </p>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-full bg-sky-600 px-7 py-2.5 text-sm font-medium text-white shadow-lg shadow-sky-600/25 transition-all hover:-translate-y-px hover:bg-sky-700 active:translate-y-0 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none disabled:hover:translate-y-0"
        >
          {submitting ? "正在看天气…" : "帮我推荐"}
        </button>
      </div>
    </section>
  );
}
