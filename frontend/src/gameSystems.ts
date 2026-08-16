/** 规则系统前端配置 —— 与后端 backend/engine/game_systems.py 对齐 */

export type GameSystem = 'dnd5e' | 'dnd4e' | 'coc' | 'custom';

export const GAME_SYSTEM_LABELS: Record<GameSystem, string> = {
  dnd5e: 'D&D 5e',
  dnd4e: 'D&D 4e',
  coc: '克苏鲁的呼唤 7e',
  custom: '自定义 / 其他',
};

export const GAME_SYSTEM_SHORT: Record<GameSystem, string> = {
  dnd5e: 'DND5e',
  dnd4e: 'DND4e',
  coc: 'COC7e',
  custom: 'CUSTOM',
};

export const GAME_SYSTEM_DESCRIPTIONS: Record<GameSystem, string> = {
  dnd5e: 'd20 检定、优势/劣势、法术位、死亡豁免',
  dnd4e: 'd20 对防御、HP/回复力、威能系统、四类防御',
  coc: 'd100 百分比检定、理智、魔法、幸运、调查员',
  custom: '由玩家提供剧本与规则，AI 按自定义规则主持',
};

/** D&D 4e 常用职业（精简集合） */
export const DND4_CLASSES = [
  '战士', '游荡者', '游侠', '牧师', '圣武士', '法师',
  '邪术师', '吟游诗人', '德鲁伊', '武僧', '野蛮人', '术士',
];

/** COC 7e 八项属性 */
export const COC_ATTRIBUTES = [
  { key: 'str', label: '力量', icon: '💪' },
  { key: 'con', label: '体质', icon: '🩸' },
  { key: 'dex', label: '敏捷', icon: '🏃' },
  { key: 'int', label: '智力', icon: '🧠' },
  { key: 'pow', label: '意志', icon: '🔥' },
  { key: 'cha', label: '魅力', icon: '👑' },
  { key: 'siz', label: '体型', icon: '📏' },
  { key: 'edu', label: '教育', icon: '🎓' },
];

/** COC 7e 常见职业 */
export const COC_OCCUPATIONS = [
  '学者', '记者', '医生', '私家侦探', '教授', '考古学家', '作家',
  '艺术家', '律师', '士兵', '警察', '药剂师', '工程师', '古董商',
  '图书馆员', '神职人员',
];

/** COC 7e 常见技能（精简集合） */
export const COC_SKILLS = [
  '会计', '人类学', '考古学', '天文学', '估价', '魅惑', '攀爬',
  '计算机', '信用评级', '克苏鲁神话', '乔装', '闪避', '驾驶',
  '电气维修', '电子学', '话术', '格斗', '急救', '历史', '恐吓',
  '跳跃', '语言', '法律', '图书馆使用', '聆听', '机械维修', '医药',
  '自然', '导航', '神秘学', '操作重型机械', '说服', '精神分析',
  '心理', '骑术', '科学', '侦查', '潜行', '生存', '游泳', '投掷', '追踪',
];

/** 自定义/其他 的通用属性（可配合自定义规则文本） */
export const CUSTOM_ATTRIBUTES = [
  { key: 'str', label: '力量', icon: '💪' },
  { key: 'dex', label: '敏捷', icon: '🏃' },
  { key: 'con', label: '体质', icon: '🛡️' },
  { key: 'int', label: '智力', icon: '📚' },
  { key: 'wis', label: '感知', icon: '👁️' },
  { key: 'cha', label: '魅力', icon: '👑' },
];

export const GAME_SYSTEM_OPTIONS: Array<{ id: GameSystem; label: string; short: string; description: string }> = (
  ['dnd5e', 'dnd4e', 'coc', 'custom'] as GameSystem[]
).map(id => ({
  id,
  label: GAME_SYSTEM_LABELS[id],
  short: GAME_SYSTEM_SHORT[id],
  description: GAME_SYSTEM_DESCRIPTIONS[id],
}));
