/** 角色卡三个长动作：保存（新建/更新）、读取回填、删除。 */
import { COC_SKILLS, COC_SKILL_BASE, type GameSystem } from '../../gameSystems';
import { SpellOption } from '../../data/dndData';

export interface CharacterCardActionContext {
  [key: string]: any;
  setEditingCardId: (id: string | null) => void;
}

export function createSaveCharCard(ctx: CharacterCardActionContext) {
  return async () => {
    if (!ctx.charName.trim()) { ctx.setError('请先填写角色名再保存角色卡'); return; }
    const card: Record<string, unknown> = {
      name: ctx.charCardName.trim() || ctx.charName.trim(),
      character_name: ctx.charName.trim(),
      gender: ctx.gender,
      race: ctx.gameSystem === 'coc' ? '调查员' : ctx.rc.name,
      char_class: ctx.gameSystem === 'coc' ? ctx.occupation : ctx.cc.name,
      game_system: ctx.gameSystem,
      attributes: ctx.finalAttrs,
      skill_proficiencies: ctx.gameSystem === 'coc' ? ctx.cocSkillPicks : ctx.skillPicks,
      skills: ctx.gameSystem === 'coc' ? ctx.cocSkillValues : undefined,
      coc_occ_inc: ctx.gameSystem === 'coc' ? ctx.cocOccInc : undefined,
      coc_per_inc: ctx.gameSystem === 'coc' ? ctx.cocPerInc : undefined,
      backstory: ctx.aiGen?.backstory || ctx.backstoryText || '',
      character_image: ctx.characterImage,
      custom_rules: ctx.gameSystem === 'custom' ? ctx.customRules : undefined,
      custom_classes: ctx.customClasses,
      custom_skills: ctx.customSkills,
      extra_attributes: ctx.extraAttributes,
      cocLuck: ctx.gameSystem === 'coc' ? ctx.cocLuck : undefined,
      known_spells: ctx.gameSystem === 'dnd5e' ? ctx.spellPicks : [],
    };
    const targetId = ctx.editingCardId;
    try {
      const url = targetId ? `/api/characters/${targetId}` : '/api/characters';
      const r = await fetch(url, {
        method: targetId ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: ctx.username || 'default', card }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '保存失败');
      }
      const d = await r.json();
      ctx.setCharCards((prev: any[]) => [d.card, ...prev.filter((c: any) => c.id !== d.card.id)]);
      ctx.setEditingCardId(d.card.id);
      ctx.setCharCardName('');
    } catch (e: unknown) {
      ctx.setError(e instanceof Error ? e.message : '保存角色卡失败');
    }
  };
}

export function createLoadCharCard(ctx: CharacterCardActionContext) {
  return async (cardId: string) => {
    try {
      const r = await fetch(`/api/characters/${cardId}?username=${encodeURIComponent(ctx.username || 'default')}`);
      if (!r.ok) return;
      const d = await r.json();
      const c = d.card?.data || {};
      if (c.character_name) ctx.setCharName(c.character_name);
      if (c.gender) ctx.setGender(c.gender);
      if (c.game_system) ctx.setGameSystem(c.game_system as GameSystem);
      if (c.race) ctx.setRace(c.race);
      if (c.char_class) ctx.setCharClass(c.char_class);
      if (c.attributes) {
        if (c.game_system === 'coc') ctx.setCocAttrs(c.attributes);
        else if (c.game_system === 'custom') ctx.setCustomAttrs(c.attributes);
        else ctx.setAttrs(c.attributes);
      }
      if (Array.isArray(c.skill_proficiencies)) {
        if (c.game_system === 'coc') ctx.setCocSkillPicks(c.skill_proficiencies);
        else ctx.setSkillPicks(c.skill_proficiencies);
      }
      if (c.coc_occ_inc && typeof c.coc_occ_inc === 'object') {
        ctx.setCocOccInc(c.coc_occ_inc as Record<string, number>);
      }
      if (c.coc_per_inc && typeof c.coc_per_inc === 'object') {
        ctx.setCocPerInc(c.coc_per_inc as Record<string, number>);
      } else if (c.skills && typeof c.skills === 'object') {
        const finalSkills = c.skills as Record<string, number>;
        const occ: Record<string, number> = {};
        COC_SKILLS.forEach((s: any) => {
          occ[s] = Math.max(0, (finalSkills[s] || 0) - (COC_SKILL_BASE[s] || 0));
        });
        ctx.setCocOccInc(occ);
        ctx.setCocPerInc(Object.fromEntries(COC_SKILLS.map((s: any) => [s, 0])));
      }
      if (c.backstory) {
        ctx.setBackstoryText(c.backstory);
        ctx.setAiGen({ attributes: c.attributes || {}, backstory: c.backstory });
      }
      if (c.character_image) ctx.setCharacterImage(c.character_image);
      if (c.custom_rules) ctx.setCustomRules(c.custom_rules);
      if (Array.isArray(c.custom_classes)) ctx.setCustomClassesText(c.custom_classes.join(', '));
      if (Array.isArray(c.custom_skills)) ctx.setCustomSkillsText(c.custom_skills.join(', '));
      if (c.extra_attributes) {
        ctx.setExtraAttributesText(Object.entries(c.extra_attributes).map(([k, v]) => `${k}:${v}`).join('\n'));
      }
      if (c.cocLuck) ctx.setCocLuck(c.cocLuck);
      if (Array.isArray(c.known_spells)) ctx.setSpellPicks(c.known_spells as SpellOption[]);
      ctx.setEditingCardId(cardId);
    } catch { /* 读取失败保持当前草稿 */ }
  };
}

export function createDeleteCharCard(ctx: CharacterCardActionContext) {
  return async (cardId: string) => {
    if (!window.confirm('确定删除该角色卡？此操作不可恢复。')) return;
    try {
      await fetch(`/api/characters/${cardId}?username=${encodeURIComponent(ctx.username || 'default')}`,
        { method: 'DELETE' });
      ctx.setCharCards(ctx.charCards.filter((c: any) => c.id !== cardId));
      if (ctx.editingCardId === cardId) ctx.setEditingCardId(null);
    } catch { /* 删除失败保持列表 */ }
  };
}
