/** 角色卡库 / 基础信息 / 角色图片 / 性别（从 CharacterStep 拆出；值经 useStartWizard 取用）。 */
import { useStartWizard } from '../StartWizardContext';
import { GAME_SYSTEM_LABELS, type GameSystem } from '../../../gameSystems';
import { formatTime } from '../../../data/dndData';

export default function BaseInfoSection() {
  const {
    authUsername,
    charCardName,
    charCards,
    charName,
    characterImage,
    deleteCharCard,
    editingCardId,
    gameSystem,
    gender,
    loadCharCard,
    mediaErr,
    saveAsNewCard,
    saveCharCard,
    setCharCardName,
    setCharName,
    setGender,
    setUsername,
    uploadCharacterImage,
    username,
  } = useStartWizard();
  const editingCard = charCards.find((card: { id: string }) => card.id === editingCardId);

  return (
    <>
                  {/* 角色卡库 */}
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-bold text-ink-700">我的角色卡</p>
                      <div className="flex items-center gap-1">
                        <input value={charCardName} onChange={(e: any) =>setCharCardName(e.target.value)} placeholder="角色卡名称" className="input-field text-xs py-1 px-2 w-28" />
                        <button onClick={saveCharCard} className="btn-secondary text-xs px-2 py-1 whitespace-nowrap">
                          {editingCard ? '更新当前卡' : '保存当前'}
                        </button>
                        {editingCard && (
                          <button onClick={saveAsNewCard} title="保留该卡并让下一次保存新建一张"
                                  className="text-xs px-2 py-1 rounded-lg border border-ink-200 whitespace-nowrap">
                            另存为新卡
                          </button>
                        )}
                      </div>
                    </div>
                    {editingCard && (
                      <p className="text-[10px] text-indigo-600">
                        正在编辑：{editingCard.name}（保存会更新这张卡，不会新建）
                      </p>
                    )}
                    {(() => {
                      const visibleCards = charCards.filter((card: any) => !card.game_system || card.game_system === gameSystem);
                      if (visibleCards.length === 0) {
                        return <p className="text-[10px] text-ink-400">{charCards.length === 0 ? '暂无角色卡。填写完角色后可保存，方便下次新游戏直接复用。' : `当前规则系统（${(GAME_SYSTEM_LABELS as Record<string, string>)[gameSystem]}）下没有角色卡，请先保存一张或切换规则。`}</p>;
                      }
                      return visibleCards.map((card: any) =>(
                      <div key={card.id} className="flex items-center justify-between bg-white rounded-lg p-2 border border-gray-200">
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-ink-800 truncate">{card.name}</p>
                          <p className="text-[9px] text-ink-400 truncate">{card.character_name} · {(GAME_SYSTEM_LABELS as Record<string, string>)[card.game_system as GameSystem]||card.game_system} · {formatTime(card.updated_at)}</p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <button onClick={()=>loadCharCard(card.id)} className="text-[10px] px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100">使用</button>
                          <button onClick={()=>deleteCharCard(card.id)} className="text-[10px] px-2 py-1 bg-red-50 text-red-600 rounded-lg border border-red-200 hover:bg-red-100">删除</button>
                        </div>
                      </div>
                      ));
                    })()}
                  </div>

                  {/* 基础信息 */}
                  <div className="grid grid-cols-2 gap-3">
                    <div><label className="block text-xs font-medium text-ink-600 mb-1">玩家</label><input value={username} onChange={(e: any) =>setUsername(e.target.value)} disabled={!!authUsername} placeholder="你的名字" className="input-field disabled:bg-gray-100 disabled:text-gray-500" /></div>
                    <div><label className="block text-xs font-medium text-ink-600 mb-1">角色名 <span className="text-red-400">*</span></label><input value={charName} onChange={(e: any) =>setCharName(e.target.value)} placeholder="取名..." className="input-field" /></div>
                  </div>

                  {/* 角色图片 */}
                  <div className="flex items-center gap-3 bg-gray-50 rounded-lg p-3 border border-gray-200">
                    {characterImage?<img src={characterImage} alt="角色" className="w-16 h-16 object-cover rounded-lg border border-gray-300" />:<div className="w-16 h-16 bg-gray-200 rounded-lg flex items-center justify-center text-[9px] text-ink-400">暂无头像</div>}
                    <div className="flex-1">
                      <label className="block text-[10px] text-ink-500 mb-1">角色图片</label>
                      <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e: any) =>{const f=e.target.files?.[0]; if(f)uploadCharacterImage(f);}} className="block w-full text-xs" />
                      {mediaErr&&<p className="text-red-700 text-[10px] mt-1">{mediaErr}</p>}
                    </div>
                  </div>

                  {/* 性别 */}
                  <div>
                    <label className="block text-xs font-medium text-ink-600 mb-2">性别</label>
                    <div className="flex gap-2">
                      {['未指定','男','女'].map((g: any) =>(
                        <button key={g} onClick={()=>setGender(g)} className={`px-4 py-1.5 rounded-lg border text-xs transition-all ${gender===g?'border-indigo-400 bg-indigo-50 text-indigo-700':'border-gray-200 bg-white text-ink-500 hover:border-gray-300'}`}>{g}</button>
                      ))}
                    </div>
                  </div>

    </>
  );
}
