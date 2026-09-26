/** 开始向导外壳：通过 context 取步骤与开关，渲染页头/设置/各步骤。 */
import { useStartWizard } from './StartWizardContext';
import ApiSettingsPanel from './ApiSettingsPanel';
import WizardNav from './WizardNav';
import WizardFooter from './WizardFooter';
import CharacterStep from './CharacterStep';
import ScenarioStep from './ScenarioStep';
import AdventurePrepStep from './AdventurePrepStep';
import KnowledgeStep from './KnowledgeStep';
import SaveStep from './SaveStep';
import RulebookModal from '../RulebookModal';

export default function StartWizardShell() {
  const { step, showRulebook, setShowRulebook } = useStartWizard();
  return (
    <div className="min-h-screen flex justify-center p-3 sm:p-6">
      <div className="w-full max-w-3xl lg:max-w-4xl">
        <header className="text-center mb-5 sm:mb-7 pt-2">
          <span className="inline-flex items-center gap-1.5 text-2xs font-medium text-parch-700 bg-parch-100/80 border border-parch-300 rounded-full px-3 py-1 mb-3">
            <span aria-hidden>🎲</span> 单人跑团 · AI 主持
          </span>
          <h1 className="text-3xl sm:text-4xl font-display font-black tracking-tight text-ink-900">TRPG 跑团</h1>
          <p className="text-ink-500 text-sm mt-2">选剧本 · 建角色 · 让 AI 主持陪你把故事跑完</p>
          <button onClick={() => setShowRulebook(true)} className="mt-3 btn-secondary text-xs px-3.5 py-1.5 min-h-[40px]">
            <span aria-hidden>📕</span> 打开玩家说明书
          </button>
        </header>

        <ApiSettingsPanel />
        <WizardNav />
        <div className="card p-4 sm:p-6 space-y-5">
          {step === 2 && <CharacterStep />}
          {step === 1 && <ScenarioStep />}
          {step === 3 && <AdventurePrepStep />}
          {step === 4 && <KnowledgeStep />}
          {step === 5 && <SaveStep />}
          <WizardFooter />
        </div>
      </div>
      {showRulebook && <RulebookModal onClose={() => setShowRulebook(false)} />}
    </div>
  );
}
