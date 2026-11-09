/**
 * QuestionRenderer — renders any questionnaire question by `type`.
 * Shared by the subject questionnaire, custom survey phases and (later) the
 * protocol wizard preview. Also exports QuestionLabel.
 */
import type { QuestionConfig } from '../../types';
import { defaultInstruction } from '../../utils/questionnaire';
import LineScale from './LineScale';
import CategoryScale from './CategoryScale';
import MagnitudeEstimation from './MagnitudeEstimation';
import MultiSelect from './MultiSelect';
import RankingQuestion from './RankingQuestion';
import {
  DropdownQuestion,
  PillboxQuestion,
  SliderQuestion,
  TextAreaQuestion,
  TextInputQuestion,
} from './LegacyQuestions';

interface QuestionRendererProps {
  question: QuestionConfig;
  value: unknown;
  onChange: (value: unknown) => void;
  /** Seed for randomised option orders (e.g. `${sessionId}:${cycle}`). */
  seed?: string;
  /** Receives the displayed option order of randomised questions. */
  onOptionOrder?: (order: Array<string | number>) => void;
}

const asNumber = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);
const asString = (v: unknown) => (typeof v === 'string' ? v : '');
const asList = (v: unknown) => (Array.isArray(v) ? (v as Array<string | number>) : undefined);

export default function QuestionRenderer({
  question,
  value,
  onChange,
  seed = '',
  onOptionOrder,
}: QuestionRendererProps) {
  switch (question.type) {
    case 'line_scale':
      return <LineScale question={question} value={asNumber(value)} onChange={onChange} />;

    case 'category_scale':
      return <CategoryScale question={question} value={asNumber(value)} onChange={onChange} />;

    case 'magnitude_estimation':
      return <MagnitudeEstimation question={question} value={asNumber(value)} onChange={onChange} />;

    case 'multi_select':
      return (
        <MultiSelect
          question={question}
          value={asList(value)}
          onChange={onChange}
          seed={seed}
          onOrder={onOptionOrder}
        />
      );

    case 'ranking':
      return (
        <RankingQuestion
          question={question}
          value={asList(value)}
          onChange={onChange}
          seed={seed}
          onOrder={onOptionOrder}
        />
      );

    case 'slider':
      // Legacy `display_type: "pillboxes"` renders discrete buttons.
      if (question.display_type === 'pillboxes') {
        return (
          <PillboxQuestion
            question={question}
            value={value as number | string | undefined}
            onChange={onChange}
          />
        );
      }
      return (
        <SliderQuestion
          question={question}
          value={
            asNumber(value) ??
            (typeof question.default === 'number' ? question.default : question.min ?? 5)
          }
          onChange={onChange}
        />
      );

    case 'pillbox':
      return (
        <PillboxQuestion
          question={question}
          value={value as number | string | undefined}
          onChange={onChange}
        />
      );

    case 'dropdown':
      return <DropdownQuestion question={question} value={asString(value)} onChange={onChange} />;

    case 'text_input':
      return <TextInputQuestion question={question} value={asString(value)} onChange={onChange} />;

    case 'text_area':
      return <TextAreaQuestion question={question} value={asString(value)} onChange={onChange} />;

    default:
      return (
        <div className="p-3 bg-yellow-50 text-yellow-800 rounded-lg text-sm">
          ⚠️ Unsupported question type "{String((question as { type?: unknown }).type)}". Please
          tell the experimenter.
        </div>
      );
  }
}

/**
 * For questions like "How sweet is the sample?" extracts "sweet" as the
 * key concept. Returns null if the pattern doesn't match.
 */
function parseModality(label: string): { before: string; modality: string; after: string } | null {
  const match = label.match(/^(how\s+)(\w+)(\s+.+)/i);
  if (!match) return null;
  return { before: match[1], modality: match[2], after: match[3] };
}

export function QuestionLabel({
  question,
  sequential,
  required,
}: {
  question: QuestionConfig;
  sequential: boolean;
  required?: boolean;
}) {
  const { label, help_text: helpText } = question;
  const parsed = parseModality(label);

  if (sequential) {
    const instruction = helpText || defaultInstruction(question);
    return (
      <div className="mb-6 text-center">
        {parsed ? (
          <>
            <div className="text-4xl sm:text-5xl font-extrabold text-primary tracking-wide mb-3">
              {parsed.modality.charAt(0).toUpperCase() + parsed.modality.slice(1)}
            </div>
            <div className="text-xl text-text-primary">{label}</div>
          </>
        ) : (
          <div className="text-2xl sm:text-3xl font-bold text-primary mb-2">{label}</div>
        )}
        {instruction && <div className="mt-2 text-base text-text-secondary">{instruction}</div>}
      </div>
    );
  }

  return (
    <div className="mb-3">
      <div className="block text-base font-medium text-text-primary">
        {parsed ? (
          <>
            {parsed.before}
            <span className="font-bold text-primary">{parsed.modality}</span>
            {parsed.after}
          </>
        ) : (
          label
        )}
        {required === false && (
          <span className="ml-2 text-xs font-normal text-text-secondary">(optional)</span>
        )}
      </div>
      {helpText && <div className="mt-0.5 text-sm text-text-secondary italic">{helpText}</div>}
    </div>
  );
}
