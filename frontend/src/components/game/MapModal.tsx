/** 地图/地点图鉴弹窗：筛选、通用参考、自建地点。
 *
 * 从 GameScreen 拆出：依赖经 props 显式传入，行为与拆分前一致。
 */
import Modal from '../ui/Modal';
import ProgressBar from '../ui/ProgressBar';
import EmptyState from '../ui/EmptyState';
import MapEntryCard from './map/MapEntryCard';
import MapBuilderForm from './map/MapBuilderForm';

export interface MapModalProps {
  [key: string]: any;
}

export default function MapModal(props: MapModalProps) {
  const {
    addDmMap,
    bestiary,
    currentSid,
    dmMap,
    filteredMaps,
    mapQuery,
    mediaTranslate,
    q,
    scenarioMaps,
    setDmMap,
    setDmMapImage,
    setMapQuery,
    setMaps,
    setShowGlobalRefMaps,
    setShowMap,
    setShowMapBuilder,
    showGlobalRefMaps,
    showMap,
    showMapBuilder,
    status,
    translateMedia,
  } = props;

  return (
    <>
          <Modal
            open={showMap}
            onClose={() => setShowMap(false)}
            size="lg"
            icon="🗺️"
            title="地点 / 地图图鉴"
            subtitle={currentSid ? '默认仅显示当前剧本条目；可切换显示通用参考' : '通用地点库（所有剧本可用）'}
            headExtra={
              <>
                <button onClick={()=>setShowMapBuilder((v: any) =>!v)} className="btn-xs-paper">
                  {showMapBuilder ? '收起自建' : '自建地点'}
                </button>
                <button onClick={()=>translateMedia('locations')} disabled={!!mediaTranslate} className="btn-xs-brand">
                  {mediaTranslate?.kind==='locations' ? '机翻中...' : '翻译地点'}
                </button>
                {currentSid && (
                  <button onClick={()=>setShowGlobalRefMaps((v: any) =>!v)} className={`btn-xs ${showGlobalRefMaps ? 'border-brand-300 bg-brand-50 text-brand-700' : ''}`}>
                    {showGlobalRefMaps ? '仅当前剧本' : '通用参考'}
                  </button>
                )}
              </>
            }
          >
                {mediaTranslate?.kind==='locations' && (
                  <ProgressBar
                    className="mb-3"
                    label="机翻地点描述"
                    value={mediaTranslate.done}
                    max={mediaTranslate.total}
                  />
                )}
                <input value={mapQuery} onChange={(e: any) =>setMapQuery(e.target.value)} placeholder="搜索地点 / 区域 / 类型 / 人物 / 危险…" className="input-field text-xs mb-3 !py-2" aria-label="搜索地点" />
                {showMapBuilder && (
                  <MapBuilderForm
                    dmMap={dmMap}
                    setDmMap={setDmMap}
                    setDmMapImage={setDmMapImage}
                    onSave={() => { addDmMap(); setShowMapBuilder(false); }}
                  />
                )}
                {filteredMaps.length===0&&(
                  <EmptyState
                    icon="🗺️"
                    title="没有找到地图"
                    hint={currentSid && !showGlobalRefMaps && scenarioMaps.length===0 ? '当前剧本暂无地点图鉴；点击右上角「通用参考」查看通用库。' : '可以调整搜索，或先导入剧本 / 上传地图图片'}
                  />
                )}
                {filteredMaps.map((m: any) => (
                  <MapEntryCard key={m.id} m={m} bestiary={bestiary} q={q}
                                status={status} setMaps={setMaps} />
                ))}
          </Modal>
    </>
  );
}
