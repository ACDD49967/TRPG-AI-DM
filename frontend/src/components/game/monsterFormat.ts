/** 怪物/生物字段格式化：属性缩写、体型/类型中文、CR→XP、描述翻译。从 GameScreen 拆出。 */
export const ATTR_CN: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
  pow: '意志', siz: '体型', edu: '教育',
};
export const SIZE_CN: Record<string, string> = { T: '微型', S: '小型', M: '中型', L: '大型', H: '超大型', G: '巨型' };
export const TYPE_CN: Record<string, string> = {
  humanoid: '类人生物', monstrosity: '怪物', dragon: '龙', beast: '野兽', undead: '亡灵',
  fiend: '邪魔', celestial: '天界生物', construct: '构装体', elemental: '元素生物',
  fey: '妖精', giant: '巨人', ooze: '泥怪', plant: '植物', aberration: '异怪',
};
export function crToXp(cr: string): string {
  const table: Record<string, number> = {
    '0': 10, '1/8': 25, '1/4': 50, '1/2': 100, '1': 200, '2': 450, '3': 700,
    '4': 1100, '5': 1800, '6': 2300, '7': 2900, '8': 3900, '9': 5000,
    '10': 5900, '11': 7200, '12': 8400, '13': 10000, '14': 11500, '15': 13000,
    '16': 15000, '17': 18000, '18': 20000, '19': 22000, '20': 25000,
  };
  return String(table[String(cr).trim()] ?? '—');
}

export function translateMonsterDesc(desc: string): string {
  return desc
    .replace(/\b(T|S|M|L|H|G)\b/g, m => SIZE_CN[m] || m)
    .replace(/\b(humanoid|monstrosity|dragon|beast|undead|fiend|celestial|construct|elemental|fey|giant|ooze|plant|aberration)\b/g, m => TYPE_CN[m] || m);
}

