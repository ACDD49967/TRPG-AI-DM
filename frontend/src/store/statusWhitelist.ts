/** SSE `state_update` 的字段白名单与清洗规则。
 *
 * 从 `gameStateShape` 拆出：白名单是"后端能推什么"的契约，
 * 和 GameState 的形状/默认值不是同一种东西，分开更好核对。
 */
import type { CharacterStatus } from './gameTypes';

/** P2-14: SSE state_update 允许写入的字段白名单，避免任意字段污染并持久化。 */
const ALLOWED_STATUS_KEYS = new Set<string>([
  'hp', 'maxHp', 'mp', 'maxMp', 'xp', 'gold', 'level', 'ac', 'inventory', 'attributes',
  'character_name', 'race', 'char_class', 'gender', 'game_system', 'username',
  'character_image', 'scenario_id', 'backstory', 'skill_proficiencies', 'skills', 'saves',
  'passive_perception', 'feats', 'custom_classes', 'custom_skills', 'extra_attributes',
  'race_traits', 'class_proficiencies', 'hit_die', 'san', 'maxSan', 'luck',
  'healing_surges', 'max_healing_surges', 'surge_value', 'speed', 'proficiency_bonus',
  'spell_slots', 'class_resources', 'known_spells', 'action_points', 'fortitude',
  'reflex', 'will', 'damage_bonus', 'build',
  // 这些字段后端会通过 state_update 推送，之前漏在白名单外被静默丢弃：
  // 专注（cast_spell/受伤中断）、状态效果、力竭、4e 血竭、结构化抗性
  'concentration', 'conditions', 'exhaustion', 'bloodied',
  'damage_resistances', 'damage_immunities', 'damage_vulnerabilities',
]);

/** 只接受白名单字段；历史格式的 inventory={items:[...]} 归一为数组。 */
export function sanitizeStatusUpdate(update: Partial<CharacterStatus>): Partial<CharacterStatus> {
  const u: Partial<CharacterStatus> = {};
  for (const [k, v] of Object.entries(update)) {
    if (ALLOWED_STATUS_KEYS.has(k)) {
      (u as Record<string, unknown>)[k] = v;
    }
  }
  const inv = u.inventory as unknown;
  if (inv && typeof inv === 'object' && !Array.isArray(inv)) {
    const rec = inv as Record<string, unknown>;
    if (Array.isArray(rec.items)) {
      u.inventory = rec.items as CharacterStatus['inventory'];
    }
  }
  return u;
}
