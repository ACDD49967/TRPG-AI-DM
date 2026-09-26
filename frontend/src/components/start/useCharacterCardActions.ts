/** 角色卡动作 hook：本地保存目标 id + 三个动作工厂装配。 */
import { useState } from 'react';
import {
  createDeleteCharCard, createLoadCharCard, createSaveCharCard,
} from './characterCardActions';

export interface UseCharacterCardActionsDeps {
  aiGen: any; backstoryText: any; cc: any; charCardName: any; charCards: any; charName: any;
  characterImage: any; cocLuck: any; cocOccInc: any; cocPerInc: any; cocSkillPicks: any; cocSkillValues: any;
  customClasses: any; customRules: any; customSkills: any; extraAttributes: any; finalAttrs: any;
  gameSystem: any; gender: any; occupation: any; race: any; rc: any; skillPicks: any; spellPicks: any; username: any;
  setAiGen: (v: any) => void; setAttrs: (v: any) => void; setBackstoryText: (v: any) => void;
  setCharCardName: (v: any) => void; setCharCards: (v: any) => void; setCharClass: (v: any) => void;
  setCharName: (v: any) => void; setCharacterImage: (v: any) => void; setCocAttrs: (v: any) => void;
  setCocLuck: (v: any) => void; setCocOccInc: (v: any) => void; setCocPerInc: (v: any) => void;
  setCocSkillPicks: (v: any) => void; setCustomAttrs: (v: any) => void; setCustomClassesText: (v: any) => void;
  setCustomRules: (v: any) => void; setCustomSkillsText: (v: any) => void; setError: (v: any) => void;
  setExtraAttributesText: (v: any) => void; setGameSystem: (v: any) => void; setGender: (v: any) => void;
  setRace: (v: any) => void; setSkillPicks: (v: any) => void; setSpellPicks: (v: any) => void;
}

export function useCharacterCardActions(deps: UseCharacterCardActionsDeps) {
  // 正在编辑的角色卡 id：为空表示"保存"是新建；载入/保存后指向卡 id。
  const [editingCardId, setEditingCardId] = useState<string | null>(null);
  const ctx = { ...deps, editingCardId, setEditingCardId };
  return {
    saveCharCard: createSaveCharCard(ctx),
    loadCharCard: createLoadCharCard(ctx),
    deleteCharCard: createDeleteCharCard(ctx),
    editingCardId,
    /** 清掉"正在编辑"标记：下一次保存会新建一张卡。 */
    saveAsNewCard: () => setEditingCardId(null),
  };
}
