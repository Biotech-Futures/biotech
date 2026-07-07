import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export const PAGE_SIZE_PRESETS = [25, 50, 100, 200] as const;
export const MIN_PAGE_SIZE = 1;
export const MAX_PAGE_SIZE = 500;

const CUSTOM_VALUE = "custom";

function clampPageSize(value: number): number {
  if (!Number.isFinite(value)) return PAGE_SIZE_PRESETS[0];
  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, Math.floor(value)));
}

interface PageSizeSelectProps {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

/**
 * Rows-per-page control: presets (25/50/100/200) plus a free-form number input
 * for any custom size up to MAX_PAGE_SIZE.
 */
export function PageSizeSelect({
  value,
  onChange,
  disabled,
}: PageSizeSelectProps) {
  const isPreset = (PAGE_SIZE_PRESETS as readonly number[]).includes(value);
  const [customMode, setCustomMode] = useState(!isPreset);
  const [draft, setDraft] = useState(String(value));

  // Keep the input in sync when the value changes (e.g. via the URL) and snap
  // back to the dropdown whenever the active size matches a preset.
  useEffect(() => {
    setDraft(String(value));
    if ((PAGE_SIZE_PRESETS as readonly number[]).includes(value)) {
      setCustomMode(false);
    }
  }, [value]);

  const applyCustom = () => {
    const next = clampPageSize(Number(draft));
    setDraft(String(next));
    if (next !== value) onChange(next);
  };

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">Rows per page</span>
      {customMode ? (
        <div className="flex items-center gap-1">
          <Input
            type="number"
            inputMode="numeric"
            min={MIN_PAGE_SIZE}
            max={MAX_PAGE_SIZE}
            value={draft}
            disabled={disabled}
            aria-label="Rows per page"
            className="h-8 w-20"
            onChange={(event) => setDraft(event.target.value)}
            onBlur={applyCustom}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                applyCustom();
              }
            }}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled}
            onClick={() => {
              setCustomMode(false);
              if (!isPreset) onChange(PAGE_SIZE_PRESETS[0]);
            }}
          >
            Presets
          </Button>
        </div>
      ) : (
        <Select
          value={String(value)}
          disabled={disabled}
          onValueChange={(next) => {
            if (next === CUSTOM_VALUE) {
              setCustomMode(true);
              return;
            }
            onChange(Number(next));
          }}
        >
          <SelectTrigger className="h-8 w-[130px]" aria-label="Rows per page">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PAGE_SIZE_PRESETS.map((preset) => (
              <SelectItem key={preset} value={String(preset)}>
                {preset} / page
              </SelectItem>
            ))}
            <SelectItem value={CUSTOM_VALUE}>Custom…</SelectItem>
          </SelectContent>
        </Select>
      )}
    </div>
  );
}
