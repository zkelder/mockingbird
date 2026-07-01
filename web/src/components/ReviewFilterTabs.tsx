export interface ReviewFilterOption<TValue extends string> {
  value: TValue;
  label: string;
  count: number;
}

interface ReviewFilterTabsProps<TValue extends string> {
  activeFilter: TValue;
  filters: ReviewFilterOption<TValue>[];
  label: string;
  onChange: (value: TValue) => void;
}

export function ReviewFilterTabs<TValue extends string>({
  activeFilter,
  filters,
  label,
  onChange,
}: ReviewFilterTabsProps<TValue>) {
  return (
    <div className="review-filter-tabs" aria-label={label}>
      {filters.map((filter) => (
        <button
          className={activeFilter === filter.value ? "selected" : ""}
          key={filter.value}
          onClick={() => onChange(filter.value)}
          type="button"
        >
          {filter.label}
          <span>{filter.count}</span>
        </button>
      ))}
    </div>
  );
}
