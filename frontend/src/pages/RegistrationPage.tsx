/**
 * RegistrationPage — Collect participant demographics (name, age, gender).
 *
 * Navigates to the instructions page on successful registration.
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import PageLayout from '../components/PageLayout';

const GENDER_OPTIONS = ['Male', 'Female', 'Other', 'Prefer not to say'] as const;

export default function RegistrationPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  // ─── STATE ──────────────────────────────────────────────────────────────
  const [name, setName] = useState('');
  const [age, setAge] = useState<number | ''>('');
  const [gender, setGender] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ─── VALIDATION ─────────────────────────────────────────────────────────
  const isValid = name.trim().length > 0
    && typeof age === 'number' && age >= 18 && age <= 120
    && gender.length > 0;

  // ─── SUBMIT ─────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid || !sessionId) return;

    setSubmitting(true);
    setError(null);

    try {
      await api.post(`/sessions/${sessionId}/register`, {
        name: name.trim(),
        age: typeof age === 'number' ? age : parseInt(String(age), 10),
        gender,
      });
      navigate(`/subject/${sessionId}/instructions`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Registration failed. Please try again.';
      setError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  // ─── RENDER ─────────────────────────────────────────────────────────────
  return (
    <PageLayout>
      <div className="max-w-lg mx-auto">
        <div className="p-6 bg-surface rounded-xl border border-border">
          <h1 className="text-2xl font-light text-text-primary tracking-wide mb-8">
            Participant Registration
          </h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Name */}
            <div>
              <label className="block text-sm font-semibold text-text-primary mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              />
            </div>

            {/* Age */}
            <div>
              <label className="block text-sm font-semibold text-text-primary mb-1">
                Age
              </label>
              <input
                type="number"
                value={age}
                onChange={(e) => {
                  const val = e.target.value;
                  setAge(val === '' ? '' : parseInt(val, 10));
                }}
                min={18}
                max={120}
                step={1}
                placeholder="Enter your age"
                className="w-full p-3 border border-border rounded-lg bg-white text-text-primary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              />
            </div>

            {/* Gender */}
            <div>
              <label className="block text-sm font-semibold text-text-primary mb-1">
                Gender
              </label>
              <div className="flex flex-wrap gap-3 mt-1">
                {GENDER_OPTIONS.map((option) => (
                  <label
                    key={option}
                    className={`
                      cursor-pointer px-4 py-2 rounded-lg text-sm font-medium
                      transition-all duration-150 select-none
                      ${gender === option
                        ? 'border-2 border-primary bg-primary/10 text-text-primary'
                        : 'border border-border bg-white text-text-primary hover:border-gray-400'
                      }
                    `}
                  >
                    <input
                      type="radio"
                      name="gender"
                      value={option}
                      checked={gender === option}
                      onChange={() => setGender(option)}
                      className="sr-only"
                    />
                    {option}
                  </label>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={!isValid || submitting}
              className={`
                w-full py-4 px-8 rounded-xl text-lg font-semibold
                shadow-md transition-all duration-200
                ${isValid && !submitting
                  ? 'bg-primary text-white hover:bg-primary-light active:bg-primary-dark cursor-pointer'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }
              `}
            >
              {submitting ? 'Registering...' : 'Continue →'}
            </button>
          </form>
        </div>
      </div>
    </PageLayout>
  );
}
