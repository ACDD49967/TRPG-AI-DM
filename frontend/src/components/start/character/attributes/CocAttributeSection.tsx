/** CoC 调查员属性：掷骰生成与派生值预览。 */
import { useStartWizard } from '../../StartWizardContext';
import { COC_ATTRIBUTES, rollCocAttributes, rollCocLuck } from '../../../../gameSystems';

export default function CocAttributeSection() {
  const { aiBusy, aiErr, aiGen, callAI, cocAttrs, cocLuck, setCocAttrs, setCocLuck } = useStartWizard();
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-medium text-ink-600">调查员属性（1-99）</label>
        <button onClick={() => { setCocAttrs(rollCocAttributes()); setCocLuck(rollCocLuck()); }} className="text-[10px] px-2.5 py-1 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">随机生成</button>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {COC_ATTRIBUTES.map((a: any) => (
          <div key={a.key} className="flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white">
            <span className="text-sm">{a.icon}</span>
            <span className="text-xs font-semibold text-ink-700 w-12">{a.label}</span>
            <span className="ml-auto text-xs font-bold text-indigo-600">{cocAttrs[a.key] || 50}</span>
          </div>
        ))}
        <p className="text-[10px] text-ink-400">按 COC 7e 规则掷骰生成：STR/CON/DEX/INT/POW/CHA=3d6×5，SIZ/EDU=(2d6+6)×5；不可自由填写。</p>
      </div>
      <div className="mt-3 bg-gray-50 rounded-lg p-3 border border-gray-200 grid grid-cols-2 gap-2 text-xs">
        <div>HP: <b>{Math.max(1, Math.floor(((cocAttrs.con || 50) + (cocAttrs.siz || 50)) / 10))}</b></div>
        <div>MP: <b>{Math.max(1, Math.floor((cocAttrs.pow || 50) / 5))}</b></div>
        <div>SAN: <b>{cocAttrs.pow || 50}</b></div>
        <div>幸运: <b>{cocLuck}</b></div>
      </div>
      <button onClick={() => callAI(true)} disabled={aiBusy} className="w-full py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium transition-all disabled:opacity-50">
        {aiBusy ? '生成中...' : '基于属性+剧本总结生成沉浸式背景'}
      </button>
      {aiErr && <p className="text-red-700 text-xs">{aiErr}</p>}
      {aiGen?.backstory && (
        <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
          <p className="text-[10px] text-ink-500 font-medium mb-1">背景故事</p>
          <p className="text-xs text-ink-700 leading-relaxed">{aiGen.backstory}</p>
        </div>
      )}
    </div>
  );
}
