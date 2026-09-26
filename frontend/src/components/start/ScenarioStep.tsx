import { useStartWizard } from './StartWizardContext';
import ScenarioModeTabs from './scenario/ScenarioModeTabs';
import ExistingScenarioPicker from './scenario/ExistingScenarioPicker';
import ScenarioGenerateForm from './scenario/ScenarioGenerateForm';
import ScenarioRuleSystem from './scenario/ScenarioRuleSystem';
import ScenarioSplitImport from './scenario/ScenarioSplitImport';
import ScenarioWorldProgress from './scenario/ScenarioWorldProgress';
import ScenarioOutlinePanel from './scenario/ScenarioOutlinePanel';
/** 剧本步骤：按三种模式编排区块。
 *
 * 从 StartScreen 拆出；5.81 起模式切换、已有剧本、生成表单、规则系统、切分导入、
 * 世界进度与大纲各成区块（components/start/scenario/），本组件只留编排与两个内联片段。
 */

export default function ScenarioStep() {
  const {
    customClassesText, customSkillsText, extraAttributesText,
    setCustomClassesText, setCustomSkillsText, setExtraAttributesText,
    genWorld, scenarioMode, selectedScenario, worldGenBusy,
  } = useStartWizard();

  return (
    <>
      <div className="space-y-5">
        <h2 className="text-lg font-bold text-ink-900">剧本选择与生成</h2>
        <ScenarioModeTabs />
        <ExistingScenarioPicker />
        <ScenarioGenerateForm />
        <ScenarioRuleSystem />
        {scenarioMode!=='existing'&&(
          <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
            <p className="text-xs font-medium text-ink-700">剧本专属扩展</p>
            <input value={customClassesText} onChange={(e: any) =>setCustomClassesText(e.target.value)} placeholder="专属职业/身份，逗号分隔，如：守夜人、符文工匠" className="input-field text-xs" />
            <input value={customSkillsText} onChange={(e: any) =>setCustomSkillsText(e.target.value)} placeholder="专属技能，逗号分隔，如：符文解读、夜间追踪" className="input-field text-xs" />
            <textarea value={extraAttributesText} onChange={(e: any) =>setExtraAttributesText(e.target.value)} placeholder="额外属性/规则特色，每行一个：名称:值" rows={2} className="input-field resize-none text-xs" />
          </div>
        )}
        <ScenarioSplitImport />
        {scenarioMode==='generate'&&!selectedScenario&&(
          <button onClick={genWorld} disabled={worldGenBusy} className="w-full btn-primary">{worldGenBusy?'正在生成世界...':'生成世界大纲'}</button>
        )}
        {scenarioMode==='existing'&&selectedScenario&&(
          <p className="text-xs text-ink-500 text-center">已加载已有剧本，无需生成。直接进入下一步。</p>
        )}
        <ScenarioWorldProgress />
        <ScenarioOutlinePanel />
      </div>
    </>
  );
}
