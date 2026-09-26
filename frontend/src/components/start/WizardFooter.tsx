import { useStartWizard } from './StartWizardContext';
/** 向导底部导航：上一步 / 下一步 / 开始冒险。
 *
 * 从 StartScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */

export default function WizardFooter() {
  const props = useStartWizard();
  const {
    loading,
    setStep,
    start,
    step,
    worldGenBusy,
  } = props;

  return (
    <>
              {/* 向导底部导航：吸底常驻，拇指始终可及（负边距让它在卡片内通栏） */}
              <div className="sticky bottom-0 z-20 -mx-4 sm:-mx-6 -mb-4 sm:-mb-6 mt-2 px-4 sm:px-6 py-3 bg-white/95 backdrop-blur border-t border-ink-100 rounded-b-2xl flex items-center gap-2">
                <button
                  onClick={()=>setStep((s: any) =>Math.max(1, s-1))}
                  disabled={step===1}
                  className="btn-secondary text-xs px-4 py-2.5"
                >
                  ← 上一步
                </button>
                <span className="text-2xs text-ink-500 mx-auto font-mono">
                  {step <= 3 ? `第 ${step} / 3 步` : step === 4 ? '知识库' : '存档'}
                </span>
                {step===3 ? (
                  // 世界大纲生成要一两分钟；这期间开局会不带世界（payload 里 world_outline/scenario_id 都是空），
                  // 所以按钮在这段时间里禁用，而不是让玩家静默开出一局没有世界的游戏。
                  <button onClick={start} disabled={loading || worldGenBusy}
                          title={worldGenBusy ? '世界大纲还在生成，请稍候' : undefined}
                          className="btn-primary text-sm px-6 py-2.5 disabled:opacity-60">
                    {loading?'准备冒险中…':worldGenBusy?'世界生成中…':'开始冒险'}
                  </button>
                ) : step < 5 ? (
                  <button onClick={()=>setStep((s: any) =>Math.min(5, s+1))} className="btn-primary text-sm px-5 py-2.5">
                    下一步 →
                  </button>
                ) : null}
              </div>
    </>
  );
}
