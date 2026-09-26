/** 生物图鉴弹窗：筛选、通用参考、自建生物、翻译。
 *
 * 从 GameScreen 拆出；条目卡片与自建表单再拆到 `beast/`，这里只留弹窗外壳与列表编排。
 */
import Modal from '../ui/Modal';
import ProgressBar from '../ui/ProgressBar';
import EmptyState from '../ui/EmptyState';
import BeastBuilderForm from './beast/BeastBuilderForm';
import BeastCard from './beast/BeastCard';


export interface BeastModalProps {
  [key: string]: any;
}

export default function BeastModal(props: BeastModalProps) {
  const {
    addDmBeast,
    beastQuery,
    bestiary,
    crToXp,
    currentSid,
    dmBeast,
    filteredBestiary,
    mediaTranslate,
    q,
    scenarioBestiary,
    scopedMaps,
    setBeastQuery,
    setBestiary,
    setDmBeast,
    setDmBeastImage,
    setShowBeast,
    setShowBeastBuilder,
    setShowGlobalRefBestiary,
    showBeast,
    showBeastBuilder,
    showGlobalRefBestiary,
    status,
    textValue,
    translateMedia,
    translateMonsterDesc,
  } = props;

  return (
    <>
          <Modal
            open={showBeast}
            onClose={() => setShowBeast(false)}
            paper
            size="lg"
            icon="🐾"
            title="生物图鉴"
            subtitle="默认仅显示当前剧本条目；通用参考需手动切换，且不会被剧本操作覆盖"
            headExtra={
              <>
                <button onClick={()=>setShowBeastBuilder((v: any) =>!v)} className="btn-xs-paper">
                  {showBeastBuilder ? '收起自建' : '自建生物'}
                </button>
                <button onClick={()=>translateMedia('bestiary')} disabled={!!mediaTranslate} className="btn-xs-brand">
                  {mediaTranslate?.kind==='bestiary' ? '机翻中...' : '翻译生物'}
                </button>
                {currentSid && (
                  <button onClick={()=>setShowGlobalRefBestiary((v: any) =>!v)} className={`btn-xs ${showGlobalRefBestiary ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                    {showGlobalRefBestiary ? '仅当前剧本' : '通用参考'}
                  </button>
                )}
              </>
            }
          >
                {mediaTranslate?.kind==='bestiary' && (
                  <ProgressBar className="mb-3" label="机翻生物描述" value={mediaTranslate.done} max={mediaTranslate.total} />
                )}
                <input value={beastQuery} onChange={(e: any) =>setBeastQuery(e.target.value)} placeholder="搜索生物 / 属性 / 栖息地 / 传说 / 弱点…" className="input-field text-xs mb-3 !py-2" aria-label="搜索生物" />
                {showBeastBuilder && (
                  <BeastBuilderForm
                    dmBeast={dmBeast}
                    setDmBeast={setDmBeast}
                    setDmBeastImage={setDmBeastImage}
                    onSave={() => { addDmBeast(); setShowBeastBuilder(false); }}
                  />
                )}
                {filteredBestiary.length===0&&(
                  <EmptyState
                    icon="🐾"
                    title="没有找到生物"
                    hint={currentSid && !showGlobalRefBestiary && scenarioBestiary.length===0 ? '当前剧本暂无生物图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入怪物库 / 上传生物图片'}
                  />
                )}
                {filteredBestiary.map((b: any) => (
                  <BeastCard key={b.id} b={b} scopedMaps={scopedMaps} q={q}
                             status={status} setBestiary={setBestiary} />
                ))}
          </Modal>
    </>
  );
}
