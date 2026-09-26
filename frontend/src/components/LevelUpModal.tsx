/**
 * 升级选择弹窗 —— 属性提升（单项+2 / 两项各+1）或选择专长。
 *
 * 数据加载与写回在 levelup/useLevelUp；本文件只负责 Modal 与交互渲染。
 */
import Modal from './ui/Modal';
import { useLevelUp } from './levelup/useLevelUp';

const ABILITY_LABEL: Record<string, string> = {
  str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力',
};

export default function LevelUpModal() {
  const {
    pendingLevel, mode, setMode, picked, setPicked, pickAbility, canConfirm,
    feats, abilities, busy, confirmAsi, confirmFeat, close,
  } = useLevelUp();

  if (!pendingLevel) return null;

  return (
    <Modal
      open
      onClose={close}
      size="lg"
      icon="🎯"
      title={`升至 ${pendingLevel} 级：属性提升或专长`}
      footer={
        mode === 'feat' ? (
          <button onClick={close} className="btn-secondary text-xs px-3 py-1.5">稍后再说</button>
        ) : (
          <>
            <button onClick={close} className="btn-secondary text-xs px-3 py-1.5">稍后再说</button>
            <button
              onClick={confirmAsi}
              disabled={!canConfirm || busy}
              className="btn-primary text-xs px-3 py-1.5 disabled:opacity-50"
            >
              {busy ? '写入中…' : mode === 'asi2' ? '确认 +2' : '确认两项各 +1'}
            </button>
          </>
        )
      }
    >
      <div className="space-y-3">
        <div className="seg inline-flex">
          {([['asi2', '单项 +2'], ['asi1', '两项各 +1'], ['feat', '选择专长']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => { setMode(key); setPicked([]); }}
              className={`seg-item ${mode === key ? 'seg-active' : ''}`}
            >
              {label}
            </button>
          ))}
        </div>

        {mode !== 'feat' && (
          <div>
            <p className="section-label mb-1.5">
              {mode === 'asi2' ? '选择一项属性 +2（上限 20）' : '选择两项属性各 +1（上限 20）'}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {abilities.map((a) => (
                <button
                  key={a.key}
                  onClick={() => pickAbility(a.key)}
                  className={`rounded-lg border px-2 py-2 text-xs transition-colors ${
                    picked.includes(a.key)
                      ? 'border-brand-400 bg-brand-50 text-brand-700'
                      : 'border-ink-200 bg-white hover:bg-ink-50'
                  }`}
                >
                  {a.name || ABILITY_LABEL[a.key] || a.key}
                </button>
              ))}
            </div>
          </div>
        )}

        {mode === 'feat' && (
          <div className="max-h-72 overflow-y-auto space-y-1.5">
            {feats.map((f) => (
              <button
                key={f.id}
                disabled={busy}
                onClick={() => confirmFeat(f.id)}
                className="w-full text-left rounded-lg border border-ink-200 bg-white hover:bg-brand-50 hover:border-brand-300 px-3 py-2 transition-colors"
              >
                <span className="text-xs font-medium text-ink-800">{f.name}</span>
                <span className="block text-3xs text-ink-500 leading-relaxed mt-0.5">{f.desc}</span>
              </button>
            ))}
            {feats.length === 0 && <p className="text-2xs text-ink-400">专长目录加载中…</p>}
          </div>
        )}
      </div>
    </Modal>
  );
}
