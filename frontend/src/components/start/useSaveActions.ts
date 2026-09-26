
/** 存档：列表、读档、删除。
 *
 * 从 StartScreen 拆出：依赖经 deps 传入，行为与拆分前一致。
 */
export interface UseSaveActionsDeps {
  apiKey: any;
  baseUrl: any;
  modelName: any;
  saves: any;
  setError: (v: any) => void;
  setSaves: (v: any) => void;
  setSession: (v: any) => void;
  updateStatus: any;
  username: any;
}

export function useSaveActions(deps: UseSaveActionsDeps) {
  const apiKey = deps.apiKey;
  const baseUrl = deps.baseUrl;
  const modelName = deps.modelName;
  const saves = deps.saves;
  const setError = deps.setError;
  const setSaves = deps.setSaves;
  const setSession = deps.setSession;
  const updateStatus = deps.updateStatus;
  const username = deps.username;

  const loadSaves=async()=>{
    try{
      const r=await fetch(`/api/saves?username=${encodeURIComponent(username||'default')}`);
      if(r.ok)setSaves((await r.json()).saves||[]);
    }catch{}
  };

  const loadSaveGame=async(saveId:string)=>{
    try{
      const r=await fetch('/api/saves/load',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        username:username||'default', save_id:saveId,
        api_key:apiKey||undefined, model_name:modelName||undefined, base_url:baseUrl||undefined,
      })});
      if(!r.ok){
        const e=await r.json().catch(()=>({}));
        setError(e.detail||'载入存档失败');
        // 存档可能已被删除，刷新列表
        fetch(`/api/saves?username=${encodeURIComponent(username||'default')}`).then((x: any) =>x.json()).then((d: any) =>setSaves(d.saves||[])).catch(()=>{});
        return;
      }
      const d=await r.json();
      if(d.status) updateStatus(d.status);
      setSession(d.session_id);
      // 读档会在后端开一个**新会话 id**（旧会话继续留在磁盘上供其它标签页使用）。
      // 明确告诉玩家一声，避免在旧标签页里继续操作后困惑"存档怎么变了"。
      try {
        const { useToastStore } = await import('../../store/toastStore');
        useToastStore.getState().showToast('已载入存档（已开始新会话）', 'success');
      } catch { /* 提示失败不影响读档 */ }
    }catch(e:unknown){setError(e instanceof Error?e.message:'载入存档失败');}
  };

  const deleteSave=async(saveId:string)=>{
    if(!window.confirm('确定删除该存档？此操作不可恢复。')) return;
    try{
      await fetch(`/api/saves/${saveId}?username=${encodeURIComponent(username||'default')}`,{method:'DELETE'});
      setSaves(saves.filter((s: any) =>s.id!==saveId));
    }catch{}
  };


  return { loadSaves, loadSaveGame, deleteSave };
}
