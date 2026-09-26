/** API 连接与端点预设：地址/Key/模型名、服务商、思维强度、常用端点。
 *
 * 从 `useModelSettings` 拆出——那一边现在只做组合，把"连接"与"向量/下载"
 * 两件互不相干的事分开，改动时不用在一个文件里来回找。
 */
import { useCallback, useEffect, useState } from 'react';
import { loadConfig } from '../../data/dndData';

export type Provider = 'openai' | 'deepseek' | 'custom';
export interface EndpointPreset {
  name: string;
  baseUrl: string;
  apiKey?: string;
  modelName?: string;
}

const THINKING_KEY = 'dnd_thinking';
const ENDPOINTS_KEY = 'dnd_endpoints';

function initialThinking(): 'low' | 'medium' | 'high' {
  try {
    const v = JSON.parse(localStorage.getItem(THINKING_KEY) || '"high"');
    return v === 'low' || v === 'medium' || v === 'high' ? v : 'high';
  } catch {
    return 'high';
  }
}

function initialEndpoints(): EndpointPreset[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(ENDPOINTS_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useConnectionSettings() {
  const cfg = loadConfig();
  const [apiKey, setApiKey] = useState(cfg.apiKey);
  const [modelName, setModelName] = useState(cfg.modelName);
  const [baseUrl, setBaseUrl] = useState(cfg.baseUrl);
  const [showKey, setShowKey] = useState(false);
  const [provider, setProvider] = useState<Provider>(
    baseUrl.includes('deepseek') ? 'deepseek' : baseUrl.includes('openai') ? 'openai' : 'custom');
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelFetchBusy, setModelFetchBusy] = useState(false);
  const [modelFetchErr, setModelFetchErr] = useState('');
  const [modelInputMode, setModelInputMode] = useState<'select' | 'manual'>('manual');
  const [thinkingStrength, setThinkingStrength] = useState<'low' | 'medium' | 'high'>(initialThinking);
  const [endpointPresets, setEndpointPresets] = useState<EndpointPreset[]>(initialEndpoints);
  const [endpointName, setEndpointName] = useState('');

  useEffect(() => {
    localStorage.setItem(THINKING_KEY, JSON.stringify(thinkingStrength));
  }, [thinkingStrength]);
  useEffect(() => {
    localStorage.setItem(ENDPOINTS_KEY, JSON.stringify(endpointPresets));
  }, [endpointPresets]);

  const applyProvider = useCallback((p: Provider) => {
    setProvider(p);
    if (p === 'openai') setBaseUrl('https://api.openai.com/v1');
  }, []);

  const saveEndpointPreset = useCallback(() => {
    const name = endpointName.trim();
    if (!name || !baseUrl.trim()) return;
    setEndpointPresets(prev => [...prev.filter(e => e.name !== name), {
      name,
      baseUrl: baseUrl.trim(),
      apiKey: apiKey.trim() || undefined,
      modelName: modelName.trim() || undefined,
    }]);
    setEndpointName('');
  }, [apiKey, baseUrl, endpointName, modelName]);

  const deleteEndpointPreset = useCallback((name: string) => {
    setEndpointPresets(prev => prev.filter(e => e.name !== name));
  }, []);

  const fetchModels = useCallback(async () => {
    setModelFetchBusy(true); setModelFetchErr('');
    try {
      const r = await fetch('/api/models', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || '获取模型失败');
      }
      const d = await r.json();
      setModelOptions(d.models || []);
      if (d.models?.length === 1) setModelName(d.models[0]);
      if (d.models?.length > 0) setModelInputMode('select');
    } catch (e: unknown) {
      setModelFetchErr(e instanceof Error ? e.message : '获取模型失败');
    } finally {
      setModelFetchBusy(false);
    }
  }, [apiKey, baseUrl]);

  return {
    apiKey, setApiKey, modelName, setModelName, baseUrl, setBaseUrl, showKey, setShowKey,
    provider, setProvider, modelOptions, modelFetchBusy, modelFetchErr, modelInputMode,
    setModelInputMode, thinkingStrength, setThinkingStrength,
    endpointPresets, endpointName, setEndpointName,
    applyProvider, saveEndpointPreset, deleteEndpointPreset, fetchModels,
  };
}
