/**
 * 编辑面板：把后端的世界状态/角色状态/会话设置的增删改查接口接成玩家可用入口。
 *
 * 之前这些内容只能靠主 DM 的工具调用改动，玩家想改一个 NPC 的态度或补一条抗性
 * 只能"跟 AI 说"。这里直连 `GET/POST /api/game/{sid}/world` 与 `/state`、
 * `GET/PATCH /api/game/{sid}/settings`，后端仍然走同一批工具处理器
 * （事件推送、落盘、派生逻辑与 DM 完全同源）。
 *
 * 六个标签页的 JSX 已按页拆到 `game/edit/`，本文件只留数据加载、写回与页签切换。
 */

import Modal from '../ui/Modal';
import FlagTab from './edit/FlagTab';
import InventoryTab from './edit/InventoryTab';
import LocationTab from './edit/LocationTab';
import NoteTab from './edit/NoteTab';
import NpcTab from './edit/NpcTab';
import SceneTab from './edit/SceneTab';
import SessionSettingsTab from './edit/SessionSettingsTab';
import StateTab from './edit/StateTab';
import {
  TABS,
} from './edit/types';
import { useEditPanelState } from './edit/useEditPanelState';

export default function EditPanel({ sessionId, username, onClose, onChanged }: {
  sessionId: string;
  username: string;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const {
    tab, setTab, world, character, settings, apiKeyDraft, setApiKeyDraft,
    busy, message, error, load, sendWorld, sendState, saveSettings,
    editScene, mergeSettings, deleteSession,
  } = useEditPanelState({ sessionId, username, onClose, onChanged });

  return (
    <Modal open onClose={onClose} size="2xl" title="编辑与调整" icon="✏️"
           subtitle="直接改世界状态与角色状态（与 DM 走同一套后端规则）">
      <div className="flex items-center gap-1 mb-3 flex-wrap">
        {TABS.map((item) => (
          <button key={item.key} onClick={() => setTab(item.key)}
                  className={`text-2xs px-3 py-1.5 rounded-lg border transition-colors ${
                    tab === item.key
                      ? 'border-brand-300 bg-brand-50 text-brand-700'
                      : 'border-ink-200 text-ink-600 hover:border-ink-300'}`}>
            <span aria-hidden>{item.icon}</span> {item.label}
          </button>
        ))}
        <span className="flex-1" />
        <button onClick={() => { void load(); }} className="text-2xs px-3 py-1.5 rounded-lg border border-ink-200">
          重新读取
        </button>
      </div>

      {(message || error) && (
        <p className={`text-2xs mb-2 ${error ? 'text-red-700' : 'text-emerald-700'}`}>
          {error || message}
        </p>
      )}
      {busy && <p className="text-2xs text-ink-400 mb-2">正在保存…</p>}

      {tab === 'scene' && world && (
        <SceneTab world={world} busy={busy} onEditScene={editScene} onSend={sendWorld}
                  onSave={() => sendWorld('update_scene', '', {
                    current_location: world.scene.location,
                    current_time: world.scene.time,
                    weather: world.scene.weather,
                    atmosphere: world.scene.atmosphere,
                    light: world.scene.light || '',
                    light_source: world.scene.light_source || '',
                    // 清空的文本字段要显式声明，否则后端按"传空即忽略"处理
                    clear: ['weather', 'atmosphere']
                      .filter((k) => !String(world.scene?.[k as 'weather' | 'atmosphere'] ?? '')),
                  })} />
      )}
      {tab === 'npc' && world && <NpcTab world={world} busy={busy} onSend={sendWorld} />}
      {tab === 'location' && world && <LocationTab world={world} busy={busy} onSend={sendWorld} />}
      {tab === 'flag' && world && <FlagTab world={world} busy={busy} onSend={sendWorld} />}
      {tab === 'note' && world && <NoteTab world={world} busy={busy} onSend={sendWorld} />}
      {tab === 'items' && <InventoryTab character={character} busy={busy} onSend={sendState} />}
      {tab === 'state' && <StateTab character={character} busy={busy} onSend={sendState} />}
      {tab === 'settings' && (
        <SessionSettingsTab settings={settings} apiKeyDraft={apiKeyDraft} busy={busy}
                            onSettingsChange={mergeSettings}
                            onApiKeyChange={setApiKeyDraft}
                            onSave={saveSettings}
                            onDeleteSession={deleteSession} />
      )}
    </Modal>
  );
}
