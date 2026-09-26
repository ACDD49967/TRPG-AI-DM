import { useStartWizard } from './StartWizardContext';
/** 步骤向导导航条：五步进度与跳转。
 *
 * 从 StartScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */

export default function WizardNav() {
  const props = useStartWizard();
  const {
    setStep,
    step,
  } = props;

  return (
    <>
            {/* 步骤向导 */}
            <nav className="card p-1.5 mb-4 flex items-center gap-1 sticky top-0 z-20 bg-white/95 backdrop-blur" aria-label="创建流程">
              {['剧本','角色创建','冒险准备','知识库','存档'].map((s,i)=>{
                const idx = i+1;
                const done = step > idx;
                const active = step === idx;
                const noNumber = s === '知识库' || s === '存档';
                return (
                  <button
                    key={i}
                    onClick={()=>setStep(idx)}
                    aria-current={active ? 'step' : undefined}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium transition-all duration-150 ${
                      active ? 'bg-brand-600 text-white shadow-sm'
                      : done ? 'text-brand-600 bg-brand-50 hover:bg-brand-100'
                      : 'text-ink-400 hover:bg-ink-50'
                    }`}
                  >
                    {!noNumber && (
                      <span
                        className={`w-4 h-4 shrink-0 rounded-full text-3xs font-bold flex items-center justify-center ${
                          active ? 'bg-white/25' : done ? 'bg-brand-100' : 'bg-ink-100'
                        }`}
                        aria-hidden
                      >
                        {done ? '✓' : idx}
                      </span>
                    )}
                    <span className="hidden sm:inline">{s}</span>
                    <span className="sm:hidden">{s.slice(0,2)}</span>
                  </button>
                );
              })}
            </nav>
    </>
  );
}
