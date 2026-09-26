/** API 连接设置：服务商、地址、Key、模型与端点预设。 */
import { useStartWizard } from '../StartWizardContext';

export default function ConnectionSection() {
  const {
    apiKey, applyProvider, authUsername, baseUrl, deleteEndpointPreset, endpointName,
    endpointPresets, fetchModels, modelFetchBusy, modelFetchErr, modelInputMode,
    modelName, modelOptions, onLogout, provider, saveEndpointPreset, setApiKey,
    setBaseUrl, setEndpointName, setModelInputMode, setModelName, setProvider,
    setShowKey, setUsername, showKey, username,
  } = useStartWizard();

  return (
    <div className="card p-4 sm:p-6 mb-4 space-y-3.5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <p className="text-xs font-bold text-ink-800 flex items-center gap-1.5">
          <span aria-hidden>🔌</span> API 连接
          <span className="text-2xs font-normal text-ink-500">（必填，用于驱动 AI 主持）</span>
        </p>
        <div className="flex items-center gap-2">
          <button onClick={() => applyProvider('openai')} className={`text-2xs px-3 py-1.5 min-h-[40px] rounded-lg border transition-colors shrink-0 ${provider === 'openai' ? 'border-brand-300 bg-brand-50 text-brand-700' : 'border-ink-200 text-ink-600 hover:border-ink-300'}`}>OpenAI 默认</button>
          <select
            value=""
            onChange={(e: any) => {
              const name = e.target.value;
              if (!name) return;
              const p = endpointPresets.find((x: any) => x.name === name);
              if (p) {
                setBaseUrl(p.baseUrl);
                if (p.apiKey) setApiKey(p.apiKey);
                if (p.modelName) setModelName(p.modelName);
              }
            }}
            className="field-sm w-full sm:w-40"
          >
            <option value="">已保存链接...</option>
            {endpointPresets.map((p: any) => <option key={p.name} value={p.name}>{p.name}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="block text-[10px] text-ink-500 mb-1">用户 / 玩家名（登录账号，用于隔离存档、角色卡、扩展与媒体）</label>
        <div className="flex gap-2">
          <input value={username} onChange={(e: any) => setUsername(e.target.value)} disabled={!!authUsername} placeholder="输入你的用户名" className="input-field text-xs flex-1 disabled:bg-gray-100 disabled:text-gray-500" />
          {authUsername && onLogout && <button onClick={onLogout} className="btn-secondary text-xs px-3 whitespace-nowrap">退出登录</button>}
        </div>
        {authUsername && <p className="text-[10px] text-emerald-600 mt-1">已登录：{authUsername}</p>}
      </div>
      <div className="grid gap-2">
        <div>
          <label className="block text-[10px] text-ink-500 mb-1">API 地址（OpenAI 兼容格式）</label>
          <input value={baseUrl} onChange={(e: any) => { setBaseUrl(e.target.value); if (!e.target.value.includes('openai')) setProvider('custom'); }} placeholder="https://api.openai.com/v1" className="input-field font-mono text-xs" />
        </div>
        <div className="flex gap-1">
          <input value={endpointName} onChange={(e: any) => setEndpointName(e.target.value)} placeholder="给当前链接命名并保存" className="input-field font-mono text-xs flex-1" />
          <button onClick={saveEndpointPreset} className="btn-secondary text-xs px-2 whitespace-nowrap">保存</button>
          {endpointPresets.length > 0 && (
            <select value="" onChange={(e: any) => { if (e.target.value) deleteEndpointPreset(e.target.value); }} className="input-field text-xs py-1 px-2 min-h-[40px] w-24">
              <option value="">删除...</option>
              {endpointPresets.map((p: any) => <option key={p.name} value={p.name}>{p.name}</option>)}
            </select>
          )}
        </div>
        <div>
          <label className="block text-[10px] text-ink-500 mb-1">API Key</label>
          <div className="flex gap-2">
            <input type={showKey ? 'text' : 'password'} value={apiKey} onChange={(e: any) => setApiKey(e.target.value)} placeholder="sk-..." className="input-field font-mono text-xs flex-1" />
            <button onClick={() => setShowKey(!showKey)} className="btn-secondary text-xs px-3">{showKey ? '隐藏' : '显示'}</button>
          </div>
        </div>
        <div>
          <label className="block text-[10px] text-ink-500 mb-1">模型（可从服务商自动获取，也可手动填写）</label>
          <div className="flex gap-2">
            {modelInputMode === 'select' && modelOptions.length > 0 ? (
              <>
                <select
                  value={modelOptions.includes(modelName) ? modelName : ''}
                  onChange={(e: any) => {
                    if (e.target.value === '__manual__') { setModelInputMode('manual'); return; }
                    setModelName(e.target.value);
                  }}
                  className="input-field font-mono text-xs flex-1"
                >
                  <option value="" disabled>选择模型...</option>
                  {modelOptions.map((m: any) => <option key={m} value={m}>{m}</option>)}
                  <option value="__manual__">手动输入...</option>
                </select>
                <button onClick={() => setModelInputMode('manual')} className="btn-secondary text-xs px-3 whitespace-nowrap">手动</button>
              </>
            ) : (
              <>
                <input value={modelName} onChange={(e: any) => setModelName(e.target.value)} placeholder="输入模型名称" className="input-field font-mono text-xs flex-1" />
                {modelOptions.length > 0 && <button onClick={() => setModelInputMode('select')} className="btn-secondary text-xs px-3 whitespace-nowrap">列表</button>}
              </>
            )}
            <button onClick={fetchModels} disabled={modelFetchBusy || !apiKey} className="btn-secondary text-xs px-3 whitespace-nowrap">{modelFetchBusy ? '获取中...' : '获取模型'}</button>
          </div>
          {modelFetchErr && <p className="text-red-700 text-[10px] mt-1">{modelFetchErr}</p>}
          {modelOptions.length > 0 && <p className="text-[10px] text-ink-400 mt-1">已获取 {modelOptions.length} 个模型，可从下拉中选择。</p>}
        </div>
      </div>
    </div>
  );
}
