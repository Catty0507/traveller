import heroImg from "../assets/hero.jpg";

const HIGHLIGHTS = ["☀️ 真实天气预报", "🌍 全球城市任选", "🗺️ 行程攻略定制"];

export default function Hero() {
  return (
    <section className="relative overflow-hidden rounded-3xl shadow-lg shadow-sky-900/10 ring-1 ring-black/5">
      <img src={heroImg} alt="" className="h-72 w-full object-cover md:h-96" />
      <div className="absolute inset-0 bg-gradient-to-t from-slate-900/70 via-slate-900/20 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2.5 p-6 md:p-10">
        <span className="w-fit rounded-full bg-white/15 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm md:text-sm">
          城市困不住想浪的心 🏃
        </span>
        <h1 className="text-4xl font-bold tracking-wide text-white drop-shadow-lg md:text-5xl">
          出逃计划
        </h1>
        <p className="mt-1 max-w-xl text-sm leading-6 text-white/90 md:text-base">
          说说你什么时候有空、想去哪儿走走,我们结合天气为你推荐最合适的目的地
        </p>
        <div className="mt-1 flex flex-wrap gap-2">
          {HIGHLIGHTS.map((h) => (
            <span
              key={h}
              className="rounded-full bg-white/15 px-3 py-1 text-xs text-white backdrop-blur-sm"
            >
              {h}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
