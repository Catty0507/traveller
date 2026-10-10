import { useState } from "react";
import type { City, Origin } from "../api/types";

interface Props {
  cities: City[];
  origin: Origin | null;
  onChange: (o: Origin | null) => void;
}

// 浏览器定位 → 尽量反查出地名;反查失败也没关系,只按坐标算距离
export default function LocationPicker({ cities, origin, onChange }: Props) {
  const [locating, setLocating] = useState(false);
  const [locError, setLocError] = useState<string | null>(null);

  const locate = () => {
    if (!navigator.geolocation) {
      setLocError("当前浏览器不支持定位,可手动选择出发城市");
      return;
    }
    setLocating(true);
    setLocError(null);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        let name: string | null = null;
        try {
          const r = await fetch(
            `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=zh`
          );
          if (r.ok) {
            const d = await r.json();
            name = d.city || d.locality || d.principalSubdivision || null;
          }
        } catch {
          // 地名反查失败不影响使用
        }
        setLocating(false);
        onChange({ lat: latitude, lon: longitude, name });
      },
      () => {
        setLocating(false);
        setLocError("定位失败,请检查浏览器定位权限,或手动选择出发城市");
      },
      { timeout: 10000 }
    );
  };

  const label = origin
    ? origin.name || `${origin.lat.toFixed(1)}, ${origin.lon.toFixed(1)}`
    : "";

  return (
    <div className="rounded-xl bg-slate-50 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-slate-500">📍 出发地(可选)</span>
        {origin ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-3 py-1 text-sm text-sky-700">
            {label}
            <button
              type="button"
              onClick={() => onChange(null)}
              className="text-sky-400 hover:text-sky-600"
              aria-label="清除出发地"
            >
              ×
            </button>
          </span>
        ) : (
          <button
            type="button"
            onClick={locate}
            disabled={locating}
            className="rounded-full bg-white px-3 py-1 text-sm text-sky-600 ring-1 ring-sky-200 transition-colors hover:bg-sky-50 disabled:opacity-60"
          >
            {locating ? "定位中…" : "使用我的位置"}
          </button>
        )}
        {!origin && (
          <select
            defaultValue=""
            onChange={(e) => {
              const c = cities.find((x) => x.id === e.target.value);
              if (c) onChange({ lat: c.lat, lon: c.lon, name: c.name_zh });
            }}
            className="ml-auto rounded-full bg-white px-3 py-1 text-sm text-slate-500 ring-1 ring-slate-200"
          >
            <option value="">或手动选择城市…</option>
            {cities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name_zh}
              </option>
            ))}
          </select>
        )}
      </div>
      {locError && <p className="mt-2 text-xs text-amber-600">{locError}</p>}
      {origin && (
        <p className="mt-1.5 text-xs text-slate-400">推荐时会考虑各目的地与你所在地的距离</p>
      )}
    </div>
  );
}
