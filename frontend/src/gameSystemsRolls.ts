/** 规则系统的属性/幸运掷骰（前端的便利函数，正式结算仍在后端）。
 *
 * 从 `gameSystems.ts` 拆出。
 */

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

/** D&D 5e 标准属性组随机分配：15,14,13,12,10,8 */
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

/** D&D 4e 标准属性组随机分配：16,14,13,12,11,10 */
export function rollDnd4Attributes(): Record<string, number> {
  const values = [16, 14, 13, 12, 11, 10];
  for (let i = values.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [values[i], values[j]] = [values[j], values[i]];
  }
  const keys = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
  const out: Record<string, number> = {};
  keys.forEach((k, i) => { out[k] = values[i]; });
  return out;
}
