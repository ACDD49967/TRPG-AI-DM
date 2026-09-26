/** 规则系统的派生值：5e/4e 的 HP、回复力、升级经验显示。
 *
 * 从 `gameSystems.ts` 拆出。
 */

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

/**
 * 经验显示：返回“当前经验/下一级所需经验”。
 * 使用 D&D 官方升级经验表（dnd5e / dnd4e）。
 */
const DND5_XP = [
  0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
  85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000,
  305000, 355000,
];
const DND4_XP = [
  0, 1000, 2250, 3750, 5500, 7500, 10000, 13000, 16500, 20500,
  26000, 32000, 39000, 47000, 57000, 69000, 83000, 99000, 119000,
  143000, 175000, 210000, 255000, 310000, 375000, 450000, 550000,
  675000, 825000, 1000000,
];

export function getXpDisplay(system: string, xp: number, level: number): string {
  const table = system === 'dnd5e' ? DND5_XP : system === 'dnd4e' ? DND4_XP : null;
  if (!table) return String(xp || 0);
  const current = Math.max(0, Number(xp) || 0);
  const lv = Math.max(1, Math.min(table.length, Number(level) || 1));
  if (lv >= table.length) return String(current);
  const next = table[lv];
  return `${current}/${next}`;
}
