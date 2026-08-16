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

function d(n: number): number {
  return Math.floor(Math.random() * n) + 1;
}

/** COC 7e 标准随机属性生成：STR/CON/DEX/INT/POW/CHA = 3d6×5；SIZ/EDU = (2d6+6)×5 */
export function rollCocAttributes(): Record<string, number> {
  return {
    str: (d(6) + d(6) + d(6)) * 5,
    con: (d(6) + d(6) + d(6)) * 5,
    dex: (d(6) + d(6) + d(6)) * 5,
    int: (d(6) + d(6) + d(6)) * 5,
    pow: (d(6) + d(6) + d(6)) * 5,
    cha: (d(6) + d(6) + d(6)) * 5,
    siz: (d(6) + d(6) + 6) * 5,
    edu: (d(6) + d(6) + 6) * 5,
  };
}

/** COC 7e 幸运：3d6×5 */
export function rollCocLuck(): number {
  return (d(6) + d(6) + d(6)) * 5;
}

/** D&D 5e/4e 标准属性组随机分配：15,14,13,12,10,8 */
export function rollDndAttributes(): Record<string, number> {
  const values = [15, 14, 13, 12, 10, 8];
  for (let i = values.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [values[i], values[j]] = [values[j], values[i]];
  }
  const keys = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
  const out: Record<string, number> = {};
  keys.forEach((k, i) => { out[k] = values[i]; });
  return out;
}

const DND5_CLASS_HD: Record<string, number> = {
  战士: 10, 圣武士: 10, 野蛮人: 12, 游侠: 10, 武僧: 8,
  游荡者: 8, 吟游诗人: 8, 牧师: 8, 德鲁伊: 8, 邪术师: 8,
  法师: 6, 术士: 6,
};

export function getDnd5Derived(charClass: string, attrs: Record<string, number>, level = 1) {
  const con = attrs.con || 10;
  const conMod = Math.floor((con - 10) / 2);
  const hd = DND5_CLASS_HD[charClass] || 8;
  const avgHd = Math.floor(hd / 2) + 1;
  const maxHp = hd + conMod + Math.max(0, level - 1) * (avgHd + conMod);
  return { maxHp, hp: maxHp, hitDie: `1d${hd}` };
}

const DND4_CLASS_HP: Record<string, number> = {
  战士: 15, 圣武士: 15, 野蛮人: 15, 游侠: 12, 游荡者: 12, 牧师: 12,
  邪术师: 12, 吟游诗人: 12, 德鲁伊: 12, 武僧: 12, 术士: 12, 法师: 10,
};
const DND4_CLASS_SURGES: Record<string, number> = {
  战士: 9, 圣武士: 9, 野蛮人: 9, 游侠: 6, 游荡者: 6, 牧师: 7,
  邪术师: 6, 吟游诗人: 7, 德鲁伊: 7, 武僧: 7, 术士: 6, 法师: 6,
};

export function getDnd4Derived(charClass: string, attrs: Record<string, number>) {
  const con = attrs.con || 10;
  const conMod = Math.floor((con - 10) / 2);
  const maxHp = (DND4_CLASS_HP[charClass] || 12) + con;
  const healingSurges = Math.max(1, (DND4_CLASS_SURGES[charClass] || 6) + conMod);
  return { maxHp, hp: maxHp, healingSurges, max_healing_surges: healingSurges, surgeValue: Math.max(1, Math.floor(maxHp / 4)) };
}
