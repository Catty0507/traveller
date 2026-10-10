/**
 * cover_color → 渐变 class 映射。
 * 必须把完整 class 字符串写死在源码里,Tailwind v4 的静态扫描才能收录
 * (无法解析运行时拼出来的类名)。
 */
export const COVER_GRADIENTS: Record<string, string> = {
  emerald: "from-emerald-100 via-teal-50 to-sky-100",
  sky: "from-sky-100 via-cyan-50 to-blue-100",
  amber: "from-amber-100 via-orange-50 to-yellow-100",
  rose: "from-rose-100 via-pink-50 to-fuchsia-100",
  violet: "from-violet-100 via-purple-50 to-indigo-100",
  teal: "from-teal-100 via-emerald-50 to-cyan-100",
  orange: "from-orange-100 via-amber-50 to-rose-100",
  indigo: "from-indigo-100 via-blue-50 to-sky-100",
};

export function coverGradient(color: string): string {
  return COVER_GRADIENTS[color] ?? COVER_GRADIENTS.sky;
}

export const TAG_EMOJIS: Record<string, string> = {
  seaside: "🏖️",
  ancient_town: "🏮",
  food: "🍜",
  nature: "🌲",
  family: "🎢",
  culture: "🏛️",
  shopping: "🛍️",
  ski: "⛷️",
};

const TAG_PRIORITY = [
  "seaside",
  "nature",
  "culture",
  "food",
  "ancient_town",
  "family",
  "shopping",
  "ski",
];

/** 取城市最有辨识度的标签 emoji 作为封面图标。 */
export function primaryTagEmoji(tags: string[]): string {
  for (const t of TAG_PRIORITY) {
    if (tags.includes(t)) return TAG_EMOJIS[t];
  }
  return "🧳";
}
