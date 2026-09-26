/** 场景标签页：当前地点 / 时间描述 / 天气 / 氛围 / 光照 + 世界规则（纯文本）。 */
import type { SceneRow, SendWorld, WorldState } from './types';

const FIELDS = [
  ['current_location', '当前地点', 'location'],
  ['current_time', '时间描述', 'time'],
  ['weather', '天气', 'weather'],
  ['atmosphere', '氛围', 'atmosphere'],
] as const;
const LIGHT_OPTIONS = ['', '明亮', '微光', '黑暗'];

export default function SceneTab({ world, busy, onEditScene, onSave, onSend }: {
  world: WorldState;
  busy: boolean;
  onEditScene: (key: keyof SceneRow, value: string) => void;
  onSave: () => void;
  onSend: SendWorld;
}) {
  return (
    <div className="space-y-2">
      {FIELDS.map(([key, label, field]) => (
        <label key={key} className="block">
          <span className="text-2xs text-ink-500">{label}</span>
          <input
            value={String(world.scene?.[field] ?? '')}
            onChange={(e) => onEditScene(field, e.target.value)}
            className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200"
          />
        </label>
      ))}
      <div className="flex gap-2">
        <label className="block flex-1">
          <span className="text-2xs text-ink-500">光照（决定攻击优势与能不能藏）</span>
          <select
            value={String(world.scene?.light ?? '')}
            onChange={(e) => onEditScene('light', e.target.value)}
            className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200 bg-white"
          >
            {LIGHT_OPTIONS.map((v) => (
              <option key={v || 'unset'} value={v}>{v || '未设置（按时间推断）'}</option>
            ))}
          </select>
        </label>
        <label className="block flex-1">
          <span className="text-2xs text-ink-500">光源</span>
          <input
            value={String(world.scene?.light_source ?? '')}
            onChange={(e) => onEditScene('light_source', e.target.value)}
            placeholder="火把 / 月光 / 无光"
            className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200"
          />
        </label>
      </div>
      <button disabled={busy} className="btn-secondary text-2xs px-3 py-1.5" onClick={onSave}>
        保存场景
      </button>

      <label className="block pt-1 border-t border-ink-100">
        <span className="text-2xs text-ink-500">世界规则 / 房规（纯文本，DM 每次都会带上）</span>
        <textarea defaultValue={String(world.world_rules || '')} rows={3}
                  onBlur={(e) => onSend('set_world_rule', e.target.value, {})}
                  placeholder="例如：本世界没有神祇，魔法稀少；死亡后无法复活。"
                  className="w-full mt-0.5 text-xs px-2 py-1.5 rounded-lg border border-ink-200 resize-none" />
      </label>
    </div>
  );
}
