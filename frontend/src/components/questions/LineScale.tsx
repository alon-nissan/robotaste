/**
 * LineScale — continuous rating line for VAS, gVAS, gLMS, LMS, LAM, LHS and
 * hedonic gLMS questions (question.type === 'line_scale').
 *
 * Psychophysics best practices built in:
 * - No marker until the subject taps the line (`start_unmarked`, default true),
 *   so responses are not anchored to a default position.
 * - No numeric readout (`show_value`, default false).
 * - Anchors are drawn at their exact numeric position (value → linear position
 *   on [min, max]), not evenly spaced. Vertical scales put `min` at the bottom
 *   and keep crowded labels (e.g. gLMS 0 / 1.4 / 6) legible by nudging them
 *   apart with a leader line back to the true tick.
 * - Tap to place, drag to adjust; arrow keys for keyboard users.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import type { QuestionConfig, ScaleAnchor } from '../../types';
import { nearestAnchorLabel } from '../../utils/questionnaire';

interface LineScaleProps {
  question: QuestionConfig;
  value: number | undefined;
  onChange: (value: number) => void;
}

/** Fraction of the line that extends past the end anchors when `inset_anchors` is set. */
const INSET_FRACTION = 0.05;
/** Minimum vertical gap (px) between neighbouring vertical labels. */
const LABEL_GAP_PX = 4;

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v));
}

function roundTo(value: number, step: number, min: number) {
  const snapped = Math.round((value - min) / step) * step + min;
  // Avoid float noise like 35.00000000004
  const decimals = Math.max(0, Math.min(6, Math.ceil(-Math.log10(step)) + 1));
  return Number(snapped.toFixed(decimals));
}

/**
 * Lay out vertical labels so they don't overlap: start at each tick's true
 * position, push labels up until they clear the one below, then push back
 * down from the top if the last one overflows.
 * Positions/heights are in px measured from the bottom of the line.
 */
function layoutVerticalLabels(
  targets: number[],
  heights: number[],
  total: number,
  gap = LABEL_GAP_PX
): number[] {
  const n = targets.length;
  const pos = [...targets];
  for (let i = 1; i < n; i++) {
    const minPos = pos[i - 1] + (heights[i - 1] + heights[i]) / 2 + gap;
    pos[i] = Math.max(pos[i], minPos);
  }
  if (n > 0 && pos[n - 1] > total) {
    pos[n - 1] = total;
    for (let i = n - 2; i >= 0; i--) {
      const maxPos = pos[i + 1] - (heights[i + 1] + heights[i]) / 2 - gap;
      pos[i] = Math.min(pos[i], maxPos);
    }
  }
  return pos;
}

/** Assign horizontal labels to rows so neighbours closer than `minDist` don't collide. */
function assignRows(fracs: number[], minDist = 0.2): number[] {
  const lastInRow: number[] = [];
  return fracs.map((f) => {
    for (let row = 0; row < lastInRow.length; row++) {
      if (f - lastInRow[row] >= minDist) {
        lastInRow[row] = f;
        return row;
      }
    }
    lastInRow.push(f);
    return lastInRow.length - 1;
  });
}

export default function LineScale({ question, value, onChange }: LineScaleProps) {
  const min = question.min ?? 0;
  const max = question.max ?? 100;
  const range = max - min || 1;
  const vertical = question.orientation === 'vertical';
  const showValue = question.show_value === true;
  const showTicks = question.show_ticks !== false;
  const inset = question.inset_anchors === true ? INSET_FRACTION : 0;
  const step = question.step && question.step > 0 ? question.step : 0.1;
  const keyStep = question.step && question.step > 0 ? question.step : range / 100;

  const anchors: ScaleAnchor[] = useMemo(
    () => [...(question.anchors ?? [])].sort((a, b) => a.value - b.value),
    [question.anchors]
  );

  const trackRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const toFrac = (v: number) => clamp((v - min) / range, 0, 1);
  // Position along the drawn line (0..1) including the inset margins.
  const toPos = (v: number) => inset + toFrac(v) * (1 - 2 * inset);

  function valueFromPointer(clientX: number, clientY: number): number | null {
    const el = trackRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    const pos = vertical
      ? (rect.bottom - clientY) / rect.height
      : (clientX - rect.left) / rect.width;
    const frac = clamp((pos - inset) / (1 - 2 * inset), 0, 1);
    return clamp(roundTo(min + frac * range, step, min), min, max);
  }

  function handlePointerDown(e: PointerEvent<HTMLDivElement>) {
    e.preventDefault();
    draggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    const v = valueFromPointer(e.clientX, e.clientY);
    if (v !== null) onChange(v);
  }

  function handlePointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!draggingRef.current) return;
    const v = valueFromPointer(e.clientX, e.clientY);
    if (v !== null && v !== value) onChange(v);
  }

  function handlePointerUp(e: PointerEvent<HTMLDivElement>) {
    draggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const increase = vertical ? ['ArrowUp', 'ArrowRight'] : ['ArrowRight', 'ArrowUp'];
    const decrease = vertical ? ['ArrowDown', 'ArrowLeft'] : ['ArrowLeft', 'ArrowDown'];
    let next: number | null = null;
    const current = value ?? (min + max) / 2;
    if (increase.includes(e.key)) next = value === undefined ? current : current + keyStep;
    else if (decrease.includes(e.key)) next = value === undefined ? current : current - keyStep;
    else if (e.key === 'Home') next = min;
    else if (e.key === 'End') next = max;
    if (next === null) return;
    e.preventDefault();
    onChange(clamp(roundTo(next, step, min), min, max));
  }

  const hasValue = typeof value === 'number' && Number.isFinite(value);
  const valueText = hasValue ? nearestAnchorLabel(anchors, value) : 'Not rated yet';
  const formatted = hasValue ? String(Number(value.toFixed(1))) : '';

  const isEnd = (a: ScaleAnchor) => a.value === min || a.value === max;
  const ariaProps = {
    role: 'slider' as const,
    tabIndex: 0,
    'aria-label': question.label,
    'aria-orientation': vertical ? ('vertical' as const) : ('horizontal' as const),
    'aria-valuemin': min,
    'aria-valuemax': max,
    'aria-valuenow': hasValue ? value : undefined,
    'aria-valuetext': valueText,
    onPointerDown: handlePointerDown,
    onPointerMove: handlePointerMove,
    onPointerUp: handlePointerUp,
    onPointerCancel: handlePointerUp,
    onKeyDown: handleKeyDown,
  };

  if (vertical) {
    return (
      <VerticalLineScale
        anchors={anchors}
        toPos={toPos}
        showTicks={showTicks}
        isEnd={isEnd}
        hasValue={hasValue}
        value={value}
        showValue={showValue}
        formatted={formatted}
        trackRef={trackRef}
        ariaProps={ariaProps}
      />
    );
  }

  // ── Horizontal ──
  const fracs = anchors.map((a) => toPos(a.value));
  const rows = assignRows(fracs);
  const rowCount = rows.length ? Math.max(...rows) + 1 : 0;

  return (
    <div className="w-full px-2 select-none" data-testid={`line-scale-${question.id}`}>
      <div
        ref={trackRef}
        {...ariaProps}
        className="relative h-14 cursor-pointer rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        style={{ touchAction: 'none' }}
      >
        {/* The line */}
        <div className="absolute left-0 right-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-primary/70" />
        {/* Anchor ticks */}
        {anchors.map((a) =>
          showTicks || isEnd(a) ? (
            <div
              key={`tick-${a.value}`}
              data-anchor-tick={a.value}
              className="absolute top-1/2 h-5 w-0.5 -translate-x-1/2 -translate-y-1/2 bg-text-primary"
              style={{ left: `${toPos(a.value) * 100}%` }}
            />
          ) : null
        )}
        {/* Marker */}
        {hasValue && (
          <div
            data-testid="line-scale-marker"
            className="pointer-events-none absolute top-1/2 h-9 w-9 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${toPos(value) * 100}%` }}
          >
            <div className="absolute left-1/2 top-0 h-full w-1 -translate-x-1/2 rounded-full bg-primary-dark" />
            <div className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary-dark shadow" />
            {showValue && (
              <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-sm font-semibold text-primary">
                {formatted}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Labels below the line, staggered into rows when neighbours are close */}
      <div className="relative" style={{ height: `${Math.max(rowCount, 1) * 2.75}rem` }}>
        {anchors.map((a, i) => {
          const pos = fracs[i];
          const alignClass =
            pos <= 0.08 ? 'text-left' : pos >= 0.92 ? 'text-right' : 'text-center -translate-x-1/2';
          const style: React.CSSProperties = { top: `${rows[i] * 2.75}rem` };
          if (pos <= 0.08) style.left = `${pos * 100}%`;
          else if (pos >= 0.92) style.right = `${(1 - pos) * 100}%`;
          else style.left = `${pos * 100}%`;
          return (
            <div
              key={`label-${a.value}`}
              data-anchor-label={a.value}
              className={`absolute max-w-[40%] text-sm leading-tight text-text-secondary ${alignClass}`}
              style={style}
            >
              {a.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Vertical layout ───────────────────────────────────────────────────────

interface VerticalProps {
  anchors: ScaleAnchor[];
  toPos: (v: number) => number;
  showTicks: boolean;
  isEnd: (a: ScaleAnchor) => boolean;
  hasValue: boolean;
  value: number | undefined;
  showValue: boolean;
  formatted: string;
  trackRef: React.RefObject<HTMLDivElement | null>;
  ariaProps: Record<string, unknown>;
}

function VerticalLineScale({
  anchors,
  toPos,
  showTicks,
  isEnd,
  hasValue,
  value,
  showValue,
  formatted,
  trackRef,
  ariaProps,
}: VerticalProps) {
  const columnRef = useRef<HTMLDivElement>(null);
  const labelRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [layout, setLayout] = useState<{ height: number; positions: number[] } | null>(null);

  useLayoutEffect(() => {
    const column = columnRef.current;
    if (!column) return;

    const measure = () => {
      const height = column.getBoundingClientRect().height;
      const heights = anchors.map((_, i) => labelRefs.current[i]?.getBoundingClientRect().height ?? 20);
      const targets = anchors.map((a) => toPos(a.value) * height);
      const positions = layoutVerticalLabels(targets, heights, height);
      setLayout((prev) => {
        if (
          prev &&
          prev.height === height &&
          prev.positions.length === positions.length &&
          prev.positions.every((p, i) => Math.abs(p - positions[i]) < 0.5)
        ) {
          return prev;
        }
        return { height, positions };
      });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(column);
    return () => observer.disconnect();
    // toPos is derived from stable question props; anchors identity covers changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchors]);

  const LEADER_WIDTH = 20;

  return (
    // Vertical padding leaves room for end labels, which are centred on the end ticks.
    <div className="flex justify-center py-8 select-none" data-testid="line-scale-vertical">
      <div className="flex" style={{ height: 'min(60vh, 28rem)' }}>
        {/* Track column */}
        <div
          ref={trackRef}
          {...ariaProps}
          className="relative h-full w-14 shrink-0 cursor-pointer rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          style={{ touchAction: 'none' }}
        >
          <div className="absolute bottom-0 left-1/2 top-0 w-1 -translate-x-1/2 rounded-full bg-primary/70" />
          {anchors.map((a) =>
            showTicks || isEnd(a) ? (
              <div
                key={`tick-${a.value}`}
                data-anchor-tick={a.value}
                className="absolute left-1/2 h-0.5 w-6 -translate-x-1/2 translate-y-1/2 bg-text-primary"
                style={{ bottom: `${toPos(a.value) * 100}%` }}
              />
            ) : null
          )}
          {hasValue && value !== undefined && (
            <div
              data-testid="line-scale-marker"
              className="pointer-events-none absolute left-1/2 h-9 w-12 -translate-x-1/2 translate-y-1/2"
              style={{ bottom: `${toPos(value) * 100}%` }}
            >
              <div className="absolute left-0 top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-primary-dark" />
              <div className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary-dark shadow" />
              {showValue && (
                <div className="absolute right-full top-1/2 mr-2 -translate-y-1/2 text-sm font-semibold text-primary">
                  {formatted}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Label column (leader lines + labels) */}
        <div ref={columnRef} className="relative h-full w-48 sm:w-64">
          {layout && (
            <svg
              className="pointer-events-none absolute left-0 top-0 h-full text-border"
              width={LEADER_WIDTH}
              height={layout.height}
              aria-hidden="true"
            >
              {anchors.map((a, i) => {
                const tickY = layout.height - toPos(a.value) * layout.height;
                const labelY = layout.height - layout.positions[i];
                return (
                  <line
                    key={`leader-${a.value}`}
                    x1={0}
                    y1={tickY}
                    x2={LEADER_WIDTH - 2}
                    y2={labelY}
                    stroke="currentColor"
                    strokeWidth={1.5}
                  />
                );
              })}
            </svg>
          )}
          {anchors.map((a, i) => (
            <div
              key={`label-${a.value}`}
              ref={(el) => {
                labelRefs.current[i] = el;
              }}
              data-anchor-label={a.value}
              className="absolute right-0 translate-y-1/2 text-sm leading-tight text-text-secondary"
              style={{
                left: LEADER_WIDTH,
                bottom: layout ? layout.positions[i] : `${toPos(a.value) * 100}%`,
                visibility: layout ? 'visible' : 'hidden',
              }}
            >
              {a.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
