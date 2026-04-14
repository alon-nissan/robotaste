const STORAGE_KEY = 'robotaste_saved_views';

export interface SavedView {
  id: string;
  name: string;
  sql: string;
  createdAt: string;
}

export function getSavedViews(): SavedView[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as SavedView[];
  } catch {
    return [];
  }
}

export function saveView(name: string, sql: string): SavedView {
  const views = getSavedViews();
  const view: SavedView = {
    id: crypto.randomUUID(),
    name,
    sql,
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...views, view]));
  return view;
}

export function deleteView(id: string): void {
  const views = getSavedViews().filter((v) => v.id !== id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

export function loadView(id: string): SavedView | undefined {
  return getSavedViews().find((v) => v.id === id);
}
