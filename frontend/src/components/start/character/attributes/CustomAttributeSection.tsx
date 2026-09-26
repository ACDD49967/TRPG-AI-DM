/** 自定义规则属性：1-30 手动输入与背景生成。 */
import { useStartWizard } from '../../StartWizardContext';
import { CUSTOM_ATTRIBUTES } from '../../../../gameSystems';

export default function CustomAttributeSection() {
  const { aiBusy, aiErr, aiGen, callAI, customAttrs, setCustomAttrs } = useStartWizard();
  return (
    <div>
      <label className="text-xs font-medium text-ink-600 mb-2">自定义属性（可在自定义规则中改名）</label>
      <div className="grid grid-cols-2 gap-2">
        {CUSTOM_ATTRIBUTES.map((a: any) => (
          <div key={a.key} className="flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white">
            <span className="text-sm">{a.icon}</span>
            <span className="text-xs font-semibold text-ink-700 w-12">{a.label}</span>
            <input type="number" min={1} max={30} value={customAttrs[a.key] || 10}
              onChange={(e: any) => setCustomAttrs((p: any) => ({ ...p, [a.key]: Math.max(1, Math.min(30, Number(e.target.value) || 10)) }))}
              className="input-field text-xs py-1 px-2" />
          </div>
        ))}
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
