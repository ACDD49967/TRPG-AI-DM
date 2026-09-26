/** 会话设置标签页：模型 / API 地址 / 游玩模式 / 思考档位 / 更新 API Key / 删除本局。 */
import type { SessionSettings } from './types';

export default function SessionSettingsTab({ settings, apiKeyDraft, busy, onSettingsChange, onApiKeyChange, onSave, onDeleteSession }: {
  settings: SessionSettings;
  apiKeyDraft: string;
  busy: boolean;
  onSettingsChange: (patch: Partial<SessionSettings>) => void;
  onApiKeyChange: (value: string) => void;
  onSave: () => void;
  onDeleteSession: () => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-2xs text-ink-500">
        改的是当前会话使用的模型与模式；API Key 只用于本会话，不会回显。
      </p>
      <label className="block">
        <span className="text-2xs text-ink-500">模型</span>
        <input value={settings.model_name || ''}
               onChange={(e) => onSettingsChange({ model_name: e.target.value })}
               placeholder="例如 deepseek-chat"
               className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200" />
      </label>
      <label className="block">
        <span className="text-2xs text-ink-500">API 地址</span>
        <input value={settings.base_url || ''}
               onChange={(e) => onSettingsChange({ base_url: e.target.value })}
               placeholder="https://api.deepseek.com/v1"
               className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200" />
      </label>
      <div className="flex items-center gap-3 flex-wrap">
        <label className="text-2xs text-ink-500">
          游玩模式
          <select value={settings.play_mode || 'deep'}
                  onChange={(e) => onSettingsChange({ play_mode: e.target.value })}
                  className="ml-1 text-2xs px-2 py-1 rounded-lg border border-ink-200">
            <option value="lite">精简</option>
            <option value="deep">深度</option>
          </select>
        </label>
        <label className="text-2xs text-ink-500">
          思考档位
          <select value={settings.thinking_strength || 'medium'}
                  onChange={(e) => onSettingsChange({ thinking_strength: e.target.value })}
                  className="ml-1 text-2xs px-2 py-1 rounded-lg border border-ink-200">
            <option value="low">轻量</option>
            <option value="medium">标准</option>
            <option value="high">深度思考</option>
          </select>
        </label>
      </div>
      <label className="block">
        <span className="text-2xs text-ink-500">更新 API Key（留空表示不改）</span>
        <input type="password" value={apiKeyDraft}
               onChange={(e) => onApiKeyChange(e.target.value)}
               placeholder="sk-..."
               className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200" />
      </label>
      <button disabled={busy} onClick={onSave}
              className="btn-secondary text-2xs px-3 py-1.5">
        保存会话设置
      </button>

      <div className="border border-red-200 rounded-xl p-2 space-y-1.5">
        <p className="text-2xs text-red-700 font-medium">删除本局会话</p>
        <p className="text-2xs text-ink-500">
          清掉当前会话与其世界状态；已保存的存档与角色卡属于独立资源，不受影响。
        </p>
        <button disabled={busy} onClick={onDeleteSession}
                className="text-2xs px-3 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 disabled:opacity-50">
          删除本局会话
        </button>
      </div>
    </div>
  );
}
