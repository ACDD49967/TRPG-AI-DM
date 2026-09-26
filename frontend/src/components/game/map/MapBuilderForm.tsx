/** 自建地点/地图表单：字段只做受控输入，保存动作由父组件编排。 */
export default function MapBuilderForm({
  dmMap, setDmMap, setDmMapImage, onSave,
}: {
  [key: string]: any;
}) {
  return (
    <div className="rounded-xl border border-parch-400/50 bg-parch-100/60 p-3 space-y-2.5 mb-3">
      <p className="text-xs font-bold text-ink-700">自建地点 / 地图</p>
      <div className="grid grid-cols-2 gap-2">
        <input value={dmMap.name} onChange={(e: any) => setDmMap({ ...dmMap, name: e.target.value })} placeholder="地点名称 *" className="input-field text-xs" />
        <input value={dmMap.type} onChange={(e: any) => setDmMap({ ...dmMap, type: e.target.value })} placeholder="类型（城镇/地城/森林...）" className="input-field text-xs" />
        <input value={dmMap.status} onChange={(e: any) => setDmMap({ ...dmMap, status: e.target.value })} placeholder="状态（可访问/危险/封闭）" className="input-field text-xs" />
        <input value={dmMap.culture} onChange={(e: any) => setDmMap({ ...dmMap, culture: e.target.value })} placeholder="文化/势力" className="input-field text-xs" />
        <input value={dmMap.districts} onChange={(e: any) => setDmMap({ ...dmMap, districts: e.target.value })} placeholder="区域（逗号分隔）" className="input-field text-xs" />
        <input value={dmMap.notable_figures} onChange={(e: any) => setDmMap({ ...dmMap, notable_figures: e.target.value })} placeholder="知名人物" className="input-field text-xs" />
        <input value={dmMap.dangers} onChange={(e: any) => setDmMap({ ...dmMap, dangers: e.target.value })} placeholder="危险/威胁" className="input-field text-xs" />
        <input value={dmMap.secret} onChange={(e: any) => setDmMap({ ...dmMap, secret: e.target.value })} placeholder="秘密/隐藏信息" className="input-field text-xs" />
      </div>
      <input value={dmMap.locationsText} onChange={(e: any) => setDmMap({ ...dmMap, locationsText: e.target.value })} placeholder="子地点（逗号分隔）" className="input-field text-xs w-full" />
      <textarea value={dmMap.description} onChange={(e: any) => setDmMap({ ...dmMap, description: e.target.value })} placeholder="地点描述" rows={2} className="input-field text-xs resize-none w-full" />
      <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) => setDmMapImage(e.target.files?.[0] || null)} className="block w-full text-[10px] text-ink-500" />
      <button onClick={onSave} className="btn-xs-paper mt-1">保存到当前剧本地点库</button>
    </div>
  );
}
