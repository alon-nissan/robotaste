/**
 * Question templates for the protocol wizard that are not scale presets:
 * basic question types and the classic 1–9 attribute sliders.
 * (Scale presets — VAS, gLMS, 9-pt hedonic, … — come from the backend.)
 */
import type { QuestionConfig } from '../../../types';

export const CLASSIC_SLIDER_TEMPLATES: { id: string; label: string; question: QuestionConfig }[] = [
  {
    id: 'blank_slider',
    label: 'Blank Slider (1–9)',
    question: {
      id: 'new_question',
      type: 'slider',
      label: '',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
    },
  },
  {
    id: 'liking',
    label: 'Overall Liking',
    question: {
      id: 'overall_liking',
      type: 'slider',
      label: 'How much do you like this sample?',
      help_text: 'Rate from 1 (Dislike Extremely) to 9 (Like Extremely)',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Dislike Extremely',
        '3': 'Dislike Moderately',
        '5': 'Neither Like nor Dislike',
        '7': 'Like Moderately',
        '9': 'Like Extremely',
      },
    },
  },
  {
    id: 'intensity',
    label: 'General Intensity',
    question: {
      id: 'intensity',
      type: 'slider',
      label: 'How intense is the taste?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Intense',
      },
    },
  },
  {
    id: 'sweetness',
    label: 'Sweetness',
    question: {
      id: 'sweetness',
      type: 'slider',
      label: 'How sweet is the sample?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Strong',
      },
    },
  },
  {
    id: 'bitterness',
    label: 'Bitterness',
    question: {
      id: 'bitterness',
      type: 'slider',
      label: 'How bitter is the sample?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Strong',
      },
    },
  },
  {
    id: 'saltiness',
    label: 'Saltiness',
    question: {
      id: 'saltiness',
      type: 'slider',
      label: 'How salty is the sample?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Strong',
      },
    },
  },
  {
    id: 'sourness',
    label: 'Sourness',
    question: {
      id: 'sourness',
      type: 'slider',
      label: 'How sour is the sample?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Strong',
      },
    },
  },
  {
    id: 'umami',
    label: 'Umami / Savouriness',
    question: {
      id: 'umami',
      type: 'slider',
      label: 'How savoury (umami) is the sample?',
      min: 1,
      max: 9,
      default: 5,
      step: 0.01,
      required: true,
      scale_labels: {
        '1': 'Not at All',
        '3': 'Light',
        '5': 'Moderate',
        '7': 'Strong',
        '9': 'Extremely Strong',
      },
    },
  },
  {
    id: 'dropdown',
    label: 'Multiple Choice (Dropdown)',
    question: {
      id: 'choice_question',
      type: 'dropdown',
      label: '',
      options: ['Option A', 'Option B', 'Option C'],
      required: true,
    },
  },
  {
    id: 'text',
    label: 'Free Text',
    question: {
      id: 'comments',
      type: 'text_input',
      label: 'Any additional comments?',
      required: false,
    },
  },
];

export const BASIC_TEMPLATES: { id: string; label: string; description: string; question: QuestionConfig }[] = [
  {
    id: 'text_input',
    label: 'Short text',
    description: 'One-line free text answer.',
    question: { id: 'answer', type: 'text_input', label: '', required: false },
  },
  {
    id: 'text_area',
    label: 'Comment box',
    description: 'Multi-line free text, usually optional.',
    question: { id: 'comments', type: 'text_area', label: 'Any additional comments?', required: false },
  },
  {
    id: 'dropdown',
    label: 'Dropdown (single choice)',
    description: 'Pick one option from a list.',
    question: {
      id: 'choice_question',
      type: 'dropdown',
      label: '',
      options: ['Option A', 'Option B', 'Option C'],
      required: true,
    },
  },
  {
    id: 'ranking',
    label: 'Ranking',
    description: 'Subject taps items in order of preference.',
    question: {
      id: 'ranking',
      type: 'ranking',
      label: 'Rank these from most to least preferred',
      randomize_order: true,
      options: [
        { value: 'option_a', label: 'Option A' },
        { value: 'option_b', label: 'Option B' },
        { value: 'option_c', label: 'Option C' },
      ],
      required: true,
    },
  },
  {
    id: 'multi_select',
    label: 'Check-all-that-apply (blank)',
    description: 'Select any number of attributes from your own list.',
    question: {
      id: 'attributes',
      type: 'multi_select',
      label: 'Which of these do you notice?',
      randomize_order: true,
      min_selected: 0,
      options: [
        { value: 'option_a', label: 'Option A' },
        { value: 'option_b', label: 'Option B' },
      ],
      required: true,
    },
  },
];

/** Default question id/label for a newly added scale, by preset category. */
export const CATEGORY_DEFAULTS: Record<string, { id: string; label: string }> = {
  intensity: { id: 'intensity', label: 'How intense is the taste?' },
  hedonic: { id: 'liking', label: 'How much do you like this sample?' },
  ideal_point: { id: 'jar', label: 'How is the sweetness?' },
  attitude: { id: 'agreement', label: 'I would buy this product.' },
  descriptive: { id: 'attributes', label: 'Which of these do you notice?' },
};

/** Make `base` unique among `existing` ids by appending _2, _3, … */
export function uniqueId(base: string, existing: Iterable<string>): string {
  const taken = new Set(existing);
  let id = base || 'question';
  let n = 2;
  while (taken.has(id)) id = `${base}_${n++}`;
  return id;
}
