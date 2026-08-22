/** COC 7e 官方调查员卡样式 */

import { useGameStore } from '../store/gameStore';

const COC_ATTRS: Array<[string, string]> = [
  ['str', '力量'], ['con', '体质'], ['dex', '敏捷'], ['int', '智力'],
  ['pow', '意志'], ['cha', '魅力'], ['siz', '体型'], ['edu', '教育'],
];

export default function CocInvestigatorSheet({ onClose }: { onClose?: () => void }) {
  const { status } = useGameStore();
  const attrs = status.attributes || {};

  return (
    <div className="paper-card rounded-xl max-w-3xl w-full max-h-[88vh] overflow-y-auto p-5 text-gray-900">
      {/* 身份 */}
      <div className="flex items-start justify-between border-b-2 border-amber-900/30 pb-3">
        <div>
          <h3 className="paper-title text-2xl font-black tracking-wide">{status.character_name || '调查员'}</h3>
          <p className="text-xs text-gray-600 mt-1">{status.race || '调查员'} · {status.char_class || '未知职业'} · COC 7e</p>
        </div>
        {onClose && <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-600">关闭</button>}
      </div>

      {/* 核心数值 */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-3">
        {[
          ['HP', `${status.hp}/${status.maxHp}`],
          ['MP', `${status.mp}/${status.maxMp}`],
          ['SAN', `${status.san}/${status.maxSan}`],
          ['LUCK', `${status.luck ?? 0}`],
          ['伤害加值', status.damage_bonus || '0'],
          ['体型', `${status.build ?? 0}`],
        ].map(([k, v]) => (
          <div key={k} className="bg-amber-50/70 border border-amber-900/20 rounded-lg p-2 text-center">
            <p className="text-[9px] uppercase tracking-widest text-gray-500">{k}</p>
            <p className="paper-title text-lg font-bold">{v}</p>
          </div>
        ))}
      </div>

      {/* 八维属性 */}
      <div className="mt-4">
        <p className="section-label mb-2">特性值</p>
        <div className="grid grid-cols-4 gap-2">
          {COC_ATTRS.map(([k, label]) => {
            const v = Number(attrs[k] ?? 50);
            return (
              <div key={k} className="bg-white border-2 border-amber-900/30 rounded-lg p-2 text-center shadow-sm">
                <p className="text-[9px] uppercase tracking-widest text-gray-400">{label}</p>
                <p className="paper-title text-2xl font-black">{v}</p>
                <p className="text-[9px] text-gray-500 mt-0.5">1/2: {Math.floor(v / 2)} · 1/5: {Math.floor(v / 5)}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 技能 */}
      {status.skills && Object.keys(status.skills).length > 0 && (
        <div className="mt-4">
          <p className="section-label mb-2">技能</p>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
            {Object.entries(status.skills).map(([k, v]) => (
              <div key={k} className="bg-white/70 border border-amber-900/20 rounded px-2 py-1 flex items-center justify-between">
                <span className="text-[10px] text-gray-600">{k}</span>
                <span className="paper-title text-sm font-bold">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 背景 */}
      {status.backstory && (
        <div className="mt-4 bg-white/70 border border-amber-900/20 rounded-lg p-3">
          <p className="section-label mb-1">背景故事</p>
          <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{status.backstory}</p>
        </div>
      )}
    </div>
  );
}
