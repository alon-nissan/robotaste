const PHASE_URL_MAP: Record<string, string> = {
  consent: 'consent',
  registration: 'register',
  instructions: 'instructions',
  selection: 'select',
  questionnaire: 'questionnaire',
  loading: 'questionnaire',
  cup_ready: 'cup-ready',
  robot_preparing: 'preparing',
  complete: 'complete',
  completion: 'complete',
};

export function phaseToPath(phase: string, sessionId: string): string {
  const segment = PHASE_URL_MAP[phase] ?? phase;
  return `/subject/${sessionId}/${segment}`;
}
