import type { Tag } from "../api/types";

interface Props {
  tags: Tag[];
  selected: string[];
  onToggle: (id: string) => void;
}

export default function TagsTab({ tags, selected, onToggle }: Props) {
  return (
    <div className="flex flex-wrap gap-2 py-1">
      {tags.map((t) => {
        const isSelected = selected.includes(t.id);
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onToggle(t.id)}
            className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
              isSelected
                ? "bg-sky-600 text-white border-sky-600"
                : "bg-white text-slate-700 border-slate-200 hover:border-sky-400"
            }`}
          >
            {t.emoji} {t.label}
          </button>
        );
      })}
    </div>
  );
}
