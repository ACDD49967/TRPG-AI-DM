/** 5e/4e 角色卡：数据准备 + 区块编排。
 *
 * 各展示区块在 `sheet/` 下（顶部信息 / 职业资源 / 属性与技能 / 特性 /
 * 攻击 / 施法 / 防具物品 / 背景），常量与小工具在 `sheet/helpers.ts`。
 */
import { useGameStore } from '../store/gameStore';
import AbilitiesBlock from './sheet/AbilitiesBlock';
import AttacksBlock from './sheet/AttacksBlock';
import BackstoryBlock from './sheet/BackstoryBlock';
import InventoryBlock from './sheet/InventoryBlock';
import ResourcesBlock from './sheet/ResourcesBlock';
import SheetHeader from './sheet/SheetHeader';
import SpellcastingBlock from './sheet/SpellcastingBlock';
import TraitsBlock from './sheet/TraitsBlock';
import { SPELLCAST_MOD, splitInventory } from './sheet/helpers';

export default function DndCharacterSheet({ onClose, embedded = false }: { onClose?: () => void; embedded?: boolean }) {
  const { status } = useGameStore();
  const attrs = status.attributes || {};
  const keys = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
  const prof = status.proficiency_bonus ?? 2;
  const speed = status.speed ?? '30尺';
  const { weapons, armor, misc } = splitInventory(status.inventory || []);
  const skillProf = status.skill_proficiencies || [];
  const castAttr = SPELLCAST_MOD[status.char_class || ''] || 'int';
  const castMod = Math.floor((Number(attrs[castAttr] ?? 10) - 10) / 2);
  const spellSlots = status.spell_slots;

  return (
    <div className={embedded ? 'text-ink-900' : 'paper-card rounded-xl max-w-3xl w-full max-h-[88vh] overflow-y-auto p-5 text-ink-900'}>
      <SheetHeader status={status} attrs={attrs} prof={prof} speed={speed}
                   onClose={onClose} embedded={embedded} />
      <ResourcesBlock status={status} />
      <AbilitiesBlock status={status} attrs={attrs} keys={keys} prof={prof} skillProf={skillProf} />
      <TraitsBlock status={status} />
      <AttacksBlock weapons={weapons} attrs={attrs} prof={prof} />
      <SpellcastingBlock status={status} spellSlots={spellSlots} castAttr={castAttr}
                        castMod={castMod} prof={prof} />
      <InventoryBlock armor={armor} misc={misc} />
      {status.backstory ? <BackstoryBlock text={status.backstory} /> : null}
    </div>
  );
}
