/** 玩家输入区 —— 白色简洁 */

import { useState, useRef, useEffect } from 'react';
import { useGameStore } from '../store/gameStore';

export default function InputArea() {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const { isProcessing, sessionId } = useGameStore();
  useEffect(() => { if (!isProcessing) inputRef.current?.focus(); }, [isProcessing]);

  const send = async () => {
    const text = input.trim();
    if (!text || isProcessing || !sessionId) return;
    const store = useGameStore.getState();
    store.addPlayerMessage(text);
    store.setProcessing(true); store.setChoices([]); store.setDecisionSuggestions([]);
    setInput('');
    try {
      const r = await fetch(`/api/game/${sessionId}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: text }) });
      if (!r.ok) { const e = await r.json(); store.appendNarrativeText(`⚠ ${e.detail || '发送失败'}`); store.setProcessing(false); }
    } catch { store.appendNarrativeText('⚠ 网络错误'); store.setProcessing(false); }
  };

  const abort = async () => { if (!sessionId) return; try { await fetch(`/api/game/${sessionId}/abort`, { method: 'POST' }); } catch {} };

  return (
    <div className="border-t border-gray-200 bg-white p-3">
      <div className="flex items-center gap-2">
        <input ref={inputRef} type="text" value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={isProcessing ? '等待主持回复...' : '输入你的行动...'}
          disabled={isProcessing}
          className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm text-gray-700 placeholder:text-gray-400 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors disabled:bg-gray-50 disabled:text-gray-400" />
        <button onClick={send} disabled={isProcessing || !input.trim()} className="btn-primary px-6 py-2.5 text-sm">发送</button>
        {isProcessing && <button onClick={abort} className="btn-secondary text-xs px-4 py-2.5">跳过</button>}
      </div>
    </div>
  );
}
