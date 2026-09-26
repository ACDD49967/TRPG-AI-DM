import { useStartWizard } from './StartWizardContext';
import BaseInfoSection from './character/BaseInfoSection';
import SpeciesClassSection from './character/SpeciesClassSection';
import SpellPickerSection from './character/SpellPickerSection';
import SkillPickerSection from './character/SkillPickerSection';
import AttributeSection from './character/AttributeSection';
/** 角色创建步骤：职业/种族/属性/技能/法术/背景与角色卡库。
 *
 * 从 StartScreen 拆出：依赖项通过 props 显式传入，行为与拆分前一致。
 */
import { GAME_SYSTEM_LABELS } from '../../gameSystems';

export default function CharacterStep() {
  const props = useStartWizard();
  const {
    aiBusy,
    aiErr,
    aiGen,
    attrMode,
    attrs,
    authUsername,
    availableCantrips,
    availableLevel1,
    backstoryText,
    callAI,
    cantripQuota,
    cc,
    charCardName,
    charCards,
    charClass,
    charName,
    characterImage,
    cocAttrs,
    cocLuck,
    cocOccInc,
    cocOccPool,
    cocOccRemain,
    cocPerInc,
    cocPerPool,
    cocPerRemain,
    cocSkillPicks,
    customAttrs,
    customClasses,
    customSkills,
    dec,
    decCocOcc,
    decCocPer,
    deleteCharCard,
    gameSystem,
    gender,
    inc,
    incCocOcc,
    incCocPer,
    loadCharCard,
    mediaErr,
    occupation,
    pb,
    race,
    rc,
    rm,
    saveCharCard,
    scenarioSystem,
    selectedCantrips,
    selectedLevel1,
    setAttrMode,
    setAttrs,
    setBackstoryText,
    setCharCardName,
    setCharClass,
    setCharName,
    setCocAttrs,
    setCocLuck,
    setCocSkillPicks,
    setCustomAttrs,
    setGender,
    setOccupation,
    setRace,
    setStep,
    setUsername,
    skillPicks,
    spellPicks,
    spellPoolBusy,
    spellQuota,
    toggleSkill,
    toggleSpell,
    uploadCharacterImage,
    username,
  } = props;

  return (
    <>
                <div className="space-y-5">
                  <p className="text-[10px] text-ink-400 bg-gray-50 rounded-lg p-2 border border-gray-200">
                    剧本系统：{(GAME_SYSTEM_LABELS as Record<string, string>)[scenarioSystem]} ｜ 角色系统：自动跟随剧本系统
                  </p>

                  <BaseInfoSection />
                  <SpeciesClassSection />
                  <SpellPickerSection />
                  <SkillPickerSection />
                  <AttributeSection />
                  {/* 自行填写背景（所有规则系统通用） */}
                  <div>
                    <label className="block text-xs font-medium text-ink-600 mb-1">角色背景</label>
                    <textarea value={backstoryText} onChange={(e: any) =>setBackstoryText(e.target.value)} placeholder="在这里直接写下你的角色过往；也可以留空并使用上方 AI 生成" rows={4} className="input-field resize-none" />
                  </div>

                  <div className="flex gap-2">
                    <button onClick={()=>setStep(1)} className="flex-1 btn-secondary">← 返回剧本</button>
                    <button onClick={()=>setStep(3)} className="flex-[2] btn-primary">继续 → 冒险准备</button>
                  </div>
                </div>
    </>
  );
}
