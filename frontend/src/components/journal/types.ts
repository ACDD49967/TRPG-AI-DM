/** 笔记面板的数据形状与展示常量（与后端 /api/game/{sid}/journal 的返回一致）。
 *
 * 从 PlayerJournal 拆出：展示型子组件也要用这些类型与配色表。
 */
export interface CharNote { target: string; comment: string; clue?: string; turn: number }
export interface NpcView {
  name: string; race: string; role: string; attitude: string; alive: boolean | null;
  appearance: string; personality: string; motivation: string; secret: string; relation_to_plot: string;
  location: string; level?: number; ac?: number; hp?: number; max_hp?: number;
  attributes?: Record<string, number>; skills?: string[]; traits?: string[]; equipment?: string[];
  conditions?: Array<string | { name?: string; description?: string; remaining_rounds?: number }>;
  related_locations?: string[]; related_npcs?: string[]; related_creatures?: string[];
  image_path?: string; importance?: 'major' | 'minor' | string; fully_revealed: boolean;
}
export interface JournalData {
  scene: { location: string; time: string; weather: string; atmosphere: string; npcs_here: string[] };
  npcs: { allies: NpcView[]; enemies: NpcView[]; neutrals: NpcView[]; total: number };
  plot_flags: { key: string; status: string; description: string }[];
  world_events?: { turn?: number; text: string }[];
  locations: Array<{
    name: string; description: string; status: string; secret?: string; type?: string; culture?: string;
    notable_figures?: string; dangers?: string; related_locations?: string[]; related_npcs?: string[]; related_creatures?: string[];
  }>;
  character_notes: { npc_notes: CharNote[]; event_notes: CharNote[]; quest_clues: CharNote[]; location_notes: CharNote[] };
  notables?: Array<{ name: string; entry_type: string; description: string; location?: string; status?: string; importance?: string; tags?: string[]; image_path?: string }>;
  turn_count: number;
}

export const CAT_COLORS: Record<string, string> = {
  ally: 'border-emerald-200 bg-emerald-50/50',
  enemy: 'border-red-200 bg-red-50/50',
  neutral: 'border-ink-200 bg-ink-50/60',
};
export const CAT_LABELS: Record<string, string> = { ally: '友善', enemy: '敌对', neutral: '中立' };
export const ATTR_NAMES: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
  pow: '意志', siz: '体型', edu: '教育',
};
