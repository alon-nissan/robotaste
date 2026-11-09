/**
 * ScaleLibraryPicker — "Add question" panel of the protocol wizard.
 *
 * Left: scale presets from the backend grouped by purpose, plus basic
 * question types and the classic 1–9 sliders. Right: a live, interactive
 * preview of the selected entry with its description and citation, and an
 * "Add to questionnaire" button.
 */
import { useMemo, useState } from 'react';
import type { QuestionConfig, ScalePreset } from '../../../types';
import QuestionRenderer from '../../questions/QuestionRenderer';
import { questionFromPreset } from '../../../utils/scalePresets';
import { BASIC_TEMPLATES, CATEGORY_DEFAULTS, CLASSIC_SLIDER_TEMPLATES, uniqueId } from './questionTemplates';

interface ScaleLibraryPickerProps {
  presets: ScalePreset[];
  loading: boolean;
  error: string | null;
  existingIds: string[];
  onPick: (question: QuestionConfig) => void;
  onCancel: () => void;
}

interface Entry {
  key: string;
  name: string;
  group: string;
  description: string;
  recommendedUse?: string;
  citation?: string;
  unverified?: boolean;
  build: (existingIds: string[]) => QuestionConfig;
}

const GROUPS: { id: string; label: string }[] = [
  { id: 'intensity', label: 'Intensity' },
  { id: 'hedonic', label: 'Liking (hedonic)' },
  { id: 'ideal_point', label: 'Ideal point & attitude' },
  { id: 'descriptive', label: 'Descriptive' },
  { id: 'basic', label: 'Basic question types' },
  { id: 'classic', label: 'Classic 1–9 sliders' },
];

function presetGroup(category: string) {
  return category === 'attitude' ? 'ideal_point' : category;
}

export default function ScaleLibraryPicker({
  presets,
  loading,
  error,
  existingIds,
  onPick,
  onCancel,
}: ScaleLibraryPickerProps) {
  const entries: Entry[] = useMemo(() => {
    const fromPresets: Entry[] = presets.map((p) => ({
      key: `preset:${p.id}`,
      name: p.name,
      group: presetGroup(p.category),
      description: p.description,
      recommendedUse: p.recommended_use,
      citation: p.citation,
      unverified: !p.anchors_verified,
      build: (ids) => {
        const defaults = CATEGORY_DEFAULTS[p.category] ?? { id: p.id, label: '' };
        const isMagnitude = p.question.type === 'magnitude_estimation';
        return questionFromPreset(
          p,
          uniqueId(isMagnitude ? 'magnitude' : defaults.id, ids),
          isMagnitude ? 'How intense is the taste? Enter a number.' : defaults.label
        );
      },
    }));
    const basic: Entry[] = BASIC_TEMPLATES.map((t) => ({
      key: `basic:${t.id}`,
      name: t.label,
      group: 'basic',
      description: t.description,
      build: (ids) => ({ ...JSON.parse(JSON.stringify(t.question)), id: uniqueId(t.question.id, ids) }),
    }));
    const classic: Entry[] = CLASSIC_SLIDER_TEMPLATES.filter((t) => t.question.type === 'slider').map((t) => ({
      key: `classic:${t.id}`,
      name: t.label,
      group: 'classic',
      description: 'Legacy 1–9 slider with a visible value and pre-set thumb.',
      build: (ids) => ({ ...JSON.parse(JSON.stringify(t.question)), id: uniqueId(t.question.id, ids) }),
    }));
    return [...fromPresets, ...basic, ...classic];
  }, [presets]);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const selected = entries.find((e) => e.key === selectedKey) ?? null;
  const previewQuestion = useMemo(
    () => (selected ? selected.build(existingIds) : null),
    // existingIds only affects the generated id, irrelevant for the preview
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected]
  );
  const [previewValue, setPreviewValue] = useState<unknown>(undefined);

  function select(key: string) {
    setSelectedKey(key);
    setPreviewValue(undefined);
  }

  return (
    <div className="border-2 border-dashed border-blue-300 rounded-lg p-4" data-testid="scale-library">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-700">Add a question — choose a scale</span>
        <button type="button" onClick={onCancel} className="text-gray-400 hover:text-gray-600 text-sm">
          ✕ Cancel
        </button>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-yellow-50 text-yellow-800 rounded text-xs">
          ⚠️ {error} Basic question types are still available.
        </div>
      )}
      {loading && <div className="mb-3 text-xs text-gray-500">Loading scale library…</div>}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Catalogue */}
        <div className="lg:col-span-2 space-y-4 max-h-[36rem] overflow-y-auto pr-1">
          {GROUPS.map((g) => {
            const items = entries.filter((e) => e.group === g.id);
            if (!items.length) return null;
            return (
              <div key={g.id}>
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-1.5">{g.label}</div>
                <div className="space-y-1.5">
                  {items.map((e) => (
                    <button
                      key={e.key}
                      type="button"
                      onClick={() => select(e.key)}
                      className={`w-full text-left px-3 py-2 border rounded-lg transition-colors ${
                        selectedKey === e.key
                          ? 'border-blue-400 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300 bg-white'
                      }`}
                    >
                      <div className="text-sm font-medium text-gray-800">
                        {e.name}
                        {e.unverified && (
                          <span className="ml-2 align-middle text-[10px] font-medium px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-800">
                            anchors unverified
                          </span>
                        )}
                      </div>
                      {e.recommendedUse && <div className="text-xs text-gray-500 mt-0.5">{e.recommendedUse}</div>}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Preview */}
        <div className="lg:col-span-3 border border-gray-200 rounded-lg p-4 bg-gray-50">
          {selected && previewQuestion ? (
            <div className="space-y-3">
              <div>
                <div className="text-base font-semibold text-gray-900">{selected.name}</div>
                <p className="text-sm text-gray-600 mt-1">{selected.description}</p>
                {selected.citation && <p className="text-xs text-gray-400 mt-1 italic">{selected.citation}</p>}
                {selected.unverified && (
                  <p className="text-xs text-yellow-800 bg-yellow-50 rounded p-2 mt-2">
                    ⚠️ Some anchor positions of this scale could not be verified against the original
                    publication. Check them before running a study.
                  </p>
                )}
              </div>
              <div className="text-xs font-medium text-gray-500">Preview (try it)</div>
              <div className="bg-white border border-gray-200 rounded-lg p-4" data-testid="library-preview">
                <div className="text-sm font-medium text-gray-800 mb-3">{previewQuestion.label || '(question text)'}</div>
                <QuestionRenderer
                  question={previewQuestion}
                  value={previewValue}
                  onChange={setPreviewValue}
                  seed="preview"
                />
              </div>
              <button
                type="button"
                onClick={() => onPick(selected.build(existingIds))}
                className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Add to questionnaire
              </button>
            </div>
          ) : (
            <div className="h-full min-h-[12rem] flex items-center justify-center text-sm text-gray-500 text-center">
              Select a scale on the left to see a live preview, its intended use and citation.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
