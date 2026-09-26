/** D&D 5e/4e 属性分配：随机、手动购点与 AI 生成。 */
import { useStartWizard } from '../../StartWizardContext';
import { rollDnd4Attributes, rollDndAttributes } from '../../../../gameSystems';
import { ATTRS, mod } from '../../../../data/dndData';

export default function DndAttributeSection() {
  const {
    aiBusy, aiErr, aiGen, attrMode, attrs, backstoryText, callAI, cc,
    dec, gameSystem, inc, pb, rm, setAttrMode, setAttrs, setBackstoryText,
  } = useStartWizard();
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-medium text-ink-600">属性分配</label>
        <div className="flex gap-1">
          <button onClick={() => { setAttrs(gameSystem === 'dnd4e' ? rollDnd4Attributes() : rollDndAttributes()); setAttrMode('manual'); }} className="text-[10px] px-2.5 py-1 rounded-lg border border-gray-200 text-ink-500 hover:border-gray-300">随机</button>
          <button onClick={() => setAttrMode('manual')} className={`text-[10px] px-2.5 py-1 rounded-lg border ${attrMode === 'manual' ? 'border-indigo-400 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-ink-400'}`}>手动</button>
          <button onClick={() => setAttrMode('ai')} className={`text-[10px] px-2.5 py-1 rounded-lg border ${attrMode === 'ai' ? 'border-indigo-400 bg-indigo-50 text-indigo-700' : 'border-gray-200 text-ink-400'}`}>自动</button>
        </div>
      </div>

      {attrMode === 'manual' && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-1.5 border border-gray-200">
            <span className="text-[10px] text-ink-500">购点 {pb.total}pt · {pb.min}-{pb.max} · 按官方点数表</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden"><div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${pb.total > 0 ? ((pb.total - rm) / pb.total) * 100 : 0}%` }} /></div>
              <span className={`text-xs font-bold ${rm < 0 ? 'text-red-700' : 'text-indigo-600'}`}>{rm}</span>
            </div>
          </div>
          {ATTRS.map((a: any) => {
            const v = attrs[a.k] || 8;
            const pri = cc.pri === a.k;
            return (
              <div key={a.k} className={`flex items-center gap-2 p-2 rounded-lg border ${pri ? 'border-amber-300 bg-amber-50/50' : 'border-gray-200 bg-white'}`}>
                <span className="text-sm w-6 text-center">{a.icon}</span>
                <div className="w-12"><span className="text-xs font-semibold text-ink-700">{a.n}</span><span className="text-[9px] text-ink-400 ml-0.5">{a.e}</span></div>
                <span className="text-[9px] text-ink-400 hidden sm:block w-20">{a.s}</span>
                {pri && <span className="text-[9px] bg-amber-100 text-amber-700 px-1 rounded-full">主</span>}
                <div className="flex items-center gap-1 ml-auto">
                  <button onClick={() => dec(a.k)} disabled={v <= pb.min} className="w-6 h-6 rounded bg-gray-100 border border-gray-200 text-ink-500 hover:text-ink-700 disabled:opacity-30 text-xs">−</button>
                  <span className="w-6 text-center text-xs font-bold text-ink-700">{v}</span>
                  <button onClick={() => inc(a.k)} disabled={v >= pb.max || rm < (pb.cost[v + 1] || 99) - (pb.cost[v] || 0)} className="w-6 h-6 rounded bg-gray-100 border border-gray-200 text-ink-500 hover:text-ink-700 disabled:opacity-30 text-xs">+</button>
                </div>
                <span className="w-12 text-right text-xs font-bold text-indigo-600">{v}<span className={`ml-0.5 ${(v - 10) >= 0 ? 'text-emerald-700' : 'text-red-400'}`}>({mod(v)})</span></span>
              </div>
            );
          })}
        </div>
      )}

      {attrMode === 'ai' && (
        <div className="space-y-2">
          <p className="text-[11px] text-ink-500">描述角色背景，系统自动分配属性。留空则全自动生成。</p>
          <textarea value={backstoryText} onChange={(e: any) => setBackstoryText(e.target.value)} placeholder="例如：森林中长大的精灵，跟随猎人父亲学箭..." rows={3} className="input-field resize-none" />
        </div>
      )}

      {aiErr && <p className="text-red-700 text-xs">{aiErr}</p>}
      <button onClick={() => callAI(attrMode === 'manual')} disabled={aiBusy} className="mt-2 w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium transition-all disabled:opacity-50">
        {aiBusy ? '生成中...' : attrMode === 'manual' ? '根据属性生成背景故事' : '自动生成属性与背景'}
      </button>

      {aiGen && (
        <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
          {aiGen.backstory && <div><p className="text-[10px] text-ink-500 font-medium mb-1">背景故事</p><p className="text-xs text-ink-700 leading-relaxed">{aiGen.backstory}</p></div>}
          <div className="grid grid-cols-3 gap-1.5">
            {ATTRS.map((a: any) => {
              const v = aiGen.attributes[a.k] || 12;
              return (
                <div key={a.k} className={`flex items-center gap-1.5 p-1.5 rounded ${cc.pri === a.k ? 'bg-amber-50' : 'bg-white'}`}>
                  <span className="text-xs">{a.icon}</span><span className="text-[10px] text-ink-500">{a.n}</span>
                  <span className="text-xs font-bold text-indigo-600 ml-auto">{v}</span><span className={`text-[9px] ${(v - 10) >= 0 ? 'text-emerald-700' : 'text-red-400'}`}>({mod(v)})</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
