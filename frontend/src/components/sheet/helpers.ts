/** 角色卡用的常量与小工具（从 DndCharacterSheet 拆出）。 */
import type { CharacterStatus } from '../../store/gameTypes';

export type InventoryItem = CharacterStatus['inventory'][number];

export const ATTR_CN: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
};

export const SKILL_ATTR: Record<string, string> = {
  '运动': 'str', '体操': 'dex', '巧手': 'dex', '隐匿': 'dex',
  '奥秘': 'int', '历史': 'int', '调查': 'int', '自然': 'int', '宗教': 'int',
  '驯兽': 'wis', '洞悉': 'wis', '医药': 'wis', '察觉': 'wis', '生存': 'wis',
  '欺瞒': 'cha', '威吓': 'cha', '表演': 'cha', '说服': 'cha',
};

export const WEAPON_DICE: Record<string, string> = {
  '巨斧': '1d12', '长戟': '1d10', '长剑': '1d8', '战斧': '1d8', '细剑': '1d8',
  '短弓': '1d6', '短剑': '1d6', '短棍': '1d6', '硬头锤': '1d6', '手斧': '1d6',
  '轻弩': '1d8', '长弓': '1d8', '匕首': '1d4', '法杖': '1d6', '飞镖': '1d4',
};

export const SPELLCAST_MOD: Record<string, string> = {
  '法师': 'int', '术士': 'cha', '吟游诗人': 'cha', '邪术师': 'cha',
  '牧师': 'wis', '德鲁伊': 'wis', '游侠': 'wis', '圣武士': 'cha', '武僧': 'wis',
};

export function mod(v: number): string {
  const m = Math.floor((v - 10) / 2);
  return `${m >= 0 ? '+' : ''}${m}`;
}

export function invName(it: InventoryItem): string {
  const name = typeof it === 'string' ? it : it.name || '未知物品';
  const q = typeof it === 'object' && it.quantity && it.quantity > 1 ? ` ×${it.quantity}` : '';
  return `${name}${q}`;
}

export function weaponDice(name: string): string {
  for (const [k, v] of Object.entries(WEAPON_DICE)) {
    if (name.includes(k)) return v;
  }
  return '1d8';
}

/** 背包按 武器 / 防具 / 其它 分类（与 status/inventory.tsx 的 isWeapon 同一套判断）。 */
export function splitInventory(inventory: InventoryItem[]) {
  const weapons = inventory.filter((i) => /剑|斧|弓|弩|匕首|矛|锤|杖|棍|鞭|刀|枪|戟|链枷|战|刃/.test(invName(i)));
  const armor = inventory.filter((i) => /甲|盾|袍|披风|头盔|护|铠|锁子|皮|板/.test(invName(i)));
  const misc = inventory.filter((i) => !weapons.includes(i) && !armor.includes(i));
  return { weapons, armor, misc };
}
