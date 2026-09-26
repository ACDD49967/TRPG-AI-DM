import { useStartWizard } from './StartWizardContext';
/** 存档步骤：读取/删除存档。
 *
 * 从 StartScreen 拆出：依赖项通过 props 显式传入，行为与拆分前一致。
 */
import { GAME_SYSTEM_LABELS, type GameSystem } from '../../gameSystems';
import { formatTime } from '../../data/dndData';
import InlineEdit from '../ui/InlineEdit';

export default function SaveStep() {
  const props = useStartWizard();
  const {
    deleteSave,
    loadSaveGame,
    loadSaves,
    saves,
    username,
  } = props;

  const renameSave = async (saveId: string, label: string) => {
    const response = await fetch(
      `/api/saves/${encodeURIComponent(saveId)}?username=${encodeURIComponent(username || 'default')}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label }),
      });
    if (!response.ok) return;
    await loadSaves?.();
  };

  return (
    <>
                <div className="space-y-5">
                  <h2 className="text-lg font-bold text-ink-900">存档</h2>
                  <p className="text-[10px] text-ink-400 bg-gray-50 rounded-lg p-2 border border-gray-200">每轮自动存档，也可手动存档；这里只管理存档，不与其他内容混杂。</p>
                  <div className="space-y-1.5">
                    {saves.length===0&&<p className="text-xs text-ink-400">暂无存档。开始游戏后每轮会自动存档。</p>}
                    {saves.map((s: any) =>(
                      <div key={s.id} className="flex items-center justify-between bg-white rounded-lg p-2.5 border border-gray-200">
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-ink-800">{s.label} {s.auto?'(自动)':'(手动)'}</p>
                          <p className="text-[10px] text-ink-500">{s.character_name} · {(GAME_SYSTEM_LABELS as Record<string, string>)[(s.game_system as GameSystem)||'dnd5e']} · {formatTime(s.created_at)}</p>
                        </div>
                        <div className="flex gap-1">
                          <InlineEdit
                            fields={[{ key: 'label', label: '存档名', value: s.label || '' }]}
                            label="重命名存档"
                            onSave={async (values) => {
                              const label = (values.label || '').trim();
                              if (label) await renameSave(s.id, label);
                            }}
                          />
                          <button onClick={()=>loadSaveGame(s.id)} className="text-[10px] px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100">载入</button>
                          <button onClick={()=>deleteSave(s.id)} className="text-[10px] px-2 py-1 bg-red-50 text-red-600 rounded-lg border border-red-200 hover:bg-red-100">删除</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
    </>
  );
}
