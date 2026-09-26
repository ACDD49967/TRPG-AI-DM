/** 向量模式与可选模型下载（知识库步骤用）：BGE-M3 / 重排 / 小模型。
 *
 * 从 `useModelSettings` 拆出：这块只服务知识库检索质量，与 API 连接设置无关。
 */
import { useCallback, useEffect, useState } from 'react';
import { useModelDownloads } from './modelDownloads';

export type VectorMode = 'local' | 'bge';

export function useVectorSettings() {
  const [vectorMode, setVectorMode] = useState<VectorMode>('local');
  const [bgeBusy, setBgeBusy] = useState<'embedding' | 'reranker' | null>(null);
  const [bgeStatus, setBgeStatus] = useState('');
  const [bgeProgress, setBgeProgress] = useState<number | null>(null);
  const [bgeDownloaded, setBgeDownloaded] = useState(false);
  const [bgeRerankerDownloaded, setBgeRerankerDownloaded] = useState(false);
  const [smallBusy, setSmallBusy] = useState(false);
  const [smallStatus, setSmallStatus] = useState('');
  const [smallProgress, setSmallProgress] = useState<number | null>(null);
  const [smallDownloaded, setSmallDownloaded] = useState(false);
  const [smallDeclined, setSmallDeclined] = useState(false);

  const fetchVectorMode = useCallback(async () => {
    try {
      const r = await fetch('/api/knowledge/vector-mode');
      if (!r.ok) return;
      const d = await r.json();
      setVectorMode(d.mode === 'bge' && d.bge_ready ? 'bge' : 'local');
      setBgeDownloaded(!!d.bge_ready);
      setSmallDownloaded(!!d.small_ready);
      setBgeRerankerDownloaded(!!d.reranker_ready);
    } catch { /* 向量模式不可用不影响开局 */ }
  }, []);

  useEffect(() => { fetchVectorMode(); }, [fetchVectorMode]);

  const setVectorModeNow = useCallback(async (mode: VectorMode) => {
    try {
      await fetch('/api/knowledge/vector-mode', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      setVectorMode(mode);
    } catch { /* 同上：设置失败保持原模式 */ }
  }, []);

  const { downloadBge, downloadSmall } = useModelDownloads({
    setBgeBusy, setBgeStatus, setBgeProgress, setBgeDownloaded, setBgeRerankerDownloaded,
    setSmallBusy, setSmallStatus, setSmallProgress, setSmallDownloaded, setSmallDeclined,
    setVectorModeNow,
  });

  return {
    vectorMode, bgeBusy, bgeStatus, bgeProgress, bgeDownloaded, bgeRerankerDownloaded,
    smallBusy, smallStatus, smallProgress, smallDownloaded, smallDeclined, setSmallDeclined,
    fetchVectorMode, setVectorModeNow, downloadBge, downloadSmall,
  };
}
