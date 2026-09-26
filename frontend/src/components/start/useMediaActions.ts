import { useEffect, useState } from 'react';

/** 媒体：地图 / 生物图鉴 / 角色头像的上传与删除。
 *
 * 状态从 StartScreen 搬进本 hook（15 个 state）：这组 state 只服务知识库步骤的
 * 媒体区、角色步骤的头像上传，以及开局时的 `character_image`；
 * 搬进来后 deps 只剩 `username` 一个跨切面输入。
 */
export interface UseMediaActionsDeps {
  username: string;
}

export function useMediaActions(deps: UseMediaActionsDeps) {
  const { username } = deps;

  // ── 地图 ──
  const [maps,setMaps]=useState<Array<{id:string;name:string;description:string;image_path:string;locations:Array<{name:string;x:number;y:number}>;system:string}>>([]);
  const [mapName,setMapName]=useState('');
  const [mapDesc,setMapDesc]=useState('');
  const [mapSystem,setMapSystem]=useState<'dnd5e'|'dnd4e'|'coc'|'custom'>('custom');
  const [mapFile,setMapFile]=useState<File|null>(null);

  // ── 生物图鉴 ──
  const [bestiary,setBestiary]=useState<Array<{id:string;name:string;system:string;description:string;stats:Record<string,string>;image_path:string;tags:string[]}>>([]);
  const [beastName,setBeastName]=useState('');
  const [beastSystem,setBeastSystem]=useState<'dnd5e'|'dnd4e'|'coc'|'custom'>('custom');
  const [beastDesc,setBeastDesc]=useState('');
  const [beastStats,setBeastStats]=useState('');
  const [beastTags,setBeastTags]=useState('');
  const [beastFile,setBeastFile]=useState<File|null>(null);

  // ── 角色头像与通用忙碌/错误 ──
  const [characterImage,setCharacterImage]=useState('');
  const [mediaBusy,setMediaBusy]=useState(false);
  const [mediaErr,setMediaErr]=useState('');

  const uploadMap=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default'); fd.append('name',mapName||file.name); fd.append('description',mapDesc); fd.append('system',mapSystem);
      const r=await fetch('/api/maps/upload',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setMapName('');setMapDesc('');setMapFile(null);
      const d=await (await fetch(`/api/maps?username=${encodeURIComponent(username||'default')}`)).json(); setMaps(d.maps||[]);
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };

  const deleteMap=async(id:string)=>{
    try{await fetch(`/api/maps/${id}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'}); setMaps(maps.filter((m: any) =>m.id!==id));}catch{}
  };

  const uploadBeast=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default'); fd.append('name',beastName||file.name); fd.append('system',beastSystem); fd.append('description',beastDesc); fd.append('stats',beastStats||'{}'); fd.append('tags',beastTags);
      const r=await fetch('/api/bestiary/upload',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setBeastName('');setBeastDesc('');setBeastStats('');setBeastTags('');setBeastFile(null);
      const d=await (await fetch(`/api/bestiary?username=${encodeURIComponent(username||'default')}`)).json(); setBestiary(d.bestiary||[]);
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };

  const deleteBeast=async(id:string)=>{
    try{await fetch(`/api/bestiary/${id}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'}); setBestiary(bestiary.filter((b: any) =>b.id!==id));}catch{}
  };

  const uploadCharacterImage=async(file:File)=>{
    setMediaBusy(true);setMediaErr('');
    try{
      const fd=new FormData(); fd.append('file',file); fd.append('username',username||'default');
      const r=await fetch('/api/media/character',{method:'POST',body:fd});
      if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||'上传失败');}
      setCharacterImage((await r.json()).image_path||'');
    }catch(e:unknown){setMediaErr(e instanceof Error?e.message:'上传失败');}
    finally{setMediaBusy(false);}
  };



  // 挂载时各拉一次（行为与拆分前 StartScreen 的挂载 effect 一致）
  useEffect(() => {
    fetch(`/api/maps?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setMaps(d.maps||[])).catch(()=>{});
    fetch(`/api/bestiary?username=${encodeURIComponent(username||'default')}`).then(r=>r.json()).then(d=>setBestiary(d.bestiary||[])).catch(()=>{});
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  return {
    maps, setMaps, mapName, setMapName, mapDesc, setMapDesc, mapSystem, setMapSystem, mapFile, setMapFile,
    bestiary, setBestiary, beastName, setBeastName, beastSystem, setBeastSystem, beastDesc, setBeastDesc,
    beastStats, setBeastStats, beastTags, setBeastTags, beastFile, setBeastFile,
    characterImage, setCharacterImage, mediaBusy, setMediaBusy, mediaErr, setMediaErr,
    uploadMap, deleteMap, uploadBeast, deleteBeast, uploadCharacterImage,
  };
}
