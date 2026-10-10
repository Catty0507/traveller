import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { City } from "../api/types";
import { primaryTagEmoji } from "../constants/colors";

interface Props {
  cities: City[];
  selected: string[];
  onToggle: (id: string) => void;
}

// 城市库太大不铺全量:空搜索时给一组热门精选,其余交给关键词搜索(覆盖全球城市库)
const POPULAR_IDS = [
  "shanghai",
  "beijing",
  "chengdu",
  "hangzhou",
  "hongkong",
  "sanya",
  "tokyo",
  "osaka",
  "seoul",
  "bangkok",
  "singapore",
  "paris",
];

// 远程搜索选中的城市对象缓存:清空搜索框后结果列表会被重置,
// 没有这份缓存,已选中的动态城市(如阿勒泰市)会因查不到而从已选区消失
const dynamicCities = new Map<string, City>();

export default function CityTab({ cities, selected, onToggle }: Props) {
  const [query, setQuery] = useState("");
  const [remote, setRemote] = useState<City[] | null>(null); // null = 未在远程搜索(本地热门模式)
  const [searching, setSearching] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      seq.current += 1;
      setRemote(null);
      setSearching(false);
      return;
    }
    const timer = setTimeout(async () => {
      const my = ++seq.current;
      setSearching(true);
      try {
        const resp = await api.searchCities(q);
        if (my === seq.current) setRemote(resp.cities);
      } catch {
        // 全球搜索接口异常时退回本地过滤,不阻塞选择
        if (my === seq.current) setRemote(localFilter(cities, q));
      } finally {
        if (my === seq.current) setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, cities]);

  const visible = remote ?? cities.filter((c) => POPULAR_IDS.includes(c.id));

  const known = useMemo(() => {
    const m = new Map(cities.map((c) => [c.id, c]));
    (remote ?? []).forEach((c) => m.set(c.id, c));
    dynamicCities.forEach((c) => m.set(c.id, c));
    return m;
  }, [cities, remote]);
  const selectedCities = selected.map((id) => known.get(id)).filter((c): c is City => Boolean(c));
  const selectedIds = new Set(selected);

  // 重名候选(如四个「河南」)自动补地区后缀便于区分:国家不同标国家,否则标省份
  const dupSuffix = useMemo(() => {
    const groups = new Map<string, City[]>();
    [...visible, ...selectedCities].forEach((c) => {
      const g = groups.get(c.name_zh);
      if (g) g.push(c);
      else groups.set(c.name_zh, [c]);
    });
    const labels = new Map<string, string>();
    groups.forEach((g) => {
      if (g.length < 2) return;
      g.forEach((c) => {
        // 国家在本组唯一 → 用国家(朝鲜的河南);否则用省份(黑龙江/浙江/北京的河南)
        const sameCountry = g.filter((x) => x.country === c.country).length;
        let d =
          sameCountry === 1
            ? c.country
            : c.summary.split("·")[0].trim() || c.country;
        if (d === c.name_zh) d = c.country; // 后缀与名字一样时退回国家名
        if (d && d !== c.name_zh) labels.set(c.id, d.slice(0, 10));
      });
    });
    return labels;
  }, [visible, selectedCities]);

  const chip = (city: City, isSelected: boolean) => {
    const suffix = dupSuffix.get(city.id);
    return (
      <button
        key={city.id}
        type="button"
        onClick={() => {
          dynamicCities.set(city.id, city); // 先记住城市对象,再交给父组件切换选中态
          onToggle(city.id);
          if (query) setQuery(""); // 选中后自动清空搜索框,回到热门精选
        }}
        className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
          isSelected
            ? "bg-sky-600 text-white border-sky-600"
            : "bg-white text-slate-700 border-slate-200 hover:border-sky-400"
        }`}
        title={city.summary}
      >
        {primaryTagEmoji(city.tags)} {city.name_zh}
        {suffix ? ` · ${suffix}` : ""}
      </button>
    );
  };

  return (
    <div className="space-y-3">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索全球城市,如「马泰拉」「Matera」「日本」"
          className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
        />
        {searching && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">
            搜索中…
          </span>
        )}
      </div>

      {selectedCities.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {selectedCities.map((c) => chip(c, true))}
        </div>
      )}

      <div className="flex flex-wrap gap-2 max-h-52 overflow-y-auto pt-1">
        {visible.filter((c) => !selectedIds.has(c.id)).map((c) => chip(c, false))}
        {remote !== null && visible.length === 0 && !searching && (
          <p className="text-sm text-slate-400 py-4">没有找到匹配的城市,换个关键词试试</p>
        )}
      </div>

      {remote === null && (
        <p className="text-xs text-slate-400">热门精选 · 输入关键词可搜索全球城市</p>
      )}
    </div>
  );
}

function localFilter(cities: City[], q: string): City[] {
  const kw = q.toLowerCase();
  return cities.filter(
    (c) =>
      c.name_zh.toLowerCase().includes(kw) ||
      c.name_en.toLowerCase().includes(kw) ||
      c.country.toLowerCase().includes(kw)
  );
}
