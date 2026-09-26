/** 游玩模式与思维强度：决定 token 消耗和扮演深度。 */
import { useStartWizard } from '../StartWizardContext';

export default function PlayModeSection() {
  const { playMode, setPlayMode, thinkingStrength, setThinkingStrength } = useStartWizard();
  return (
    <section className="card p-4 sm:p-6 mb-4 space-y-4">
      <div>
        <p className="section-label mb-2">游玩模式</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button onClick={() => setPlayMode('lite')} aria-pressed={playMode === 'lite'} className={`p-3 rounded-xl border text-left transition-all ${playMode === 'lite' ? 'border-emerald-400 bg-emerald-50 ring-1 ring-emerald-200' : 'border-ink-200 bg-white hover:border-ink-300'}`}>
            <div className="flex items-center gap-2">
              <span className="text-2xs font-bold text-emerald-700 bg-emerald-100 rounded px-1.5 py-0.5 shrink-0">精简</span>
              <div className="min-w-0">
                <div className="text-sm font-bold text-ink-800">精简模式</div>
                <div className="text-2xs text-ink-500 leading-relaxed">低 token 消耗 · 快节奏 · 性价比玩法</div>
              </div>
            </div>
          </button>
          <button onClick={() => setPlayMode('deep')} aria-pressed={playMode === 'deep'} className={`p-3 rounded-xl border text-left transition-all ${playMode === 'deep' ? 'border-brand-400 bg-brand-50 ring-1 ring-brand-200' : 'border-ink-200 bg-white hover:border-ink-300'}`}>
            <div className="flex items-center gap-2">
              <span className="text-2xs font-bold text-brand-700 bg-brand-100 rounded px-1.5 py-0.5 shrink-0">深度</span>
              <div className="min-w-0">
                <div className="text-sm font-bold text-ink-800">深度模式</div>
                <div className="text-2xs text-ink-500 leading-relaxed">高 token 消耗 · 高深度扮演 · 沉浸体验</div>
              </div>
            </div>
          </button>
        </div>
      </div>

      <div>
        <p className="section-label mb-2">
          思维强度 <span className="normal-case font-normal text-ink-400">（影响推理深度与 token 消耗）</span>
        </p>
        <div className="grid grid-cols-3 gap-1.5">
          {(['low', 'medium', 'high'] as const).map((v: any) => (
            <button key={v} onClick={() => setThinkingStrength(v)} aria-pressed={thinkingStrength === v} className={`seg ${thinkingStrength === v ? 'seg-active' : ''}`}>
              {v === 'low' ? '轻量' : v === 'medium' ? '标准' : '深度思考'}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
