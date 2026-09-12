/**
 * 玩家输入区
 *
 * 优化点：
 *  - 多行自适应输入（Shift+Enter 换行，Enter 发送），长行动不再只能挤在一行。
 *  - 中文输入法组合态保护：IME 选词回车不会误发送（原实现的真实痛点）。
 *  - 等待期间显示「跳过」与提示，避免玩家以为卡死。
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useGameStore } from '../store/gameStore';

const MAX_ROWS_PX = 132;

export default function InputArea() {
  const [input, setInput] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { isProcessing, sessionId } = useGameStore();

  useEffect(() => {
    if (!isProcessing) inputRef.current?.focus();
  }, [isProcessing]);

  // 高度自适应：先归零再按 scrollHeight 撑开，超过上限则内部滚动
  const resize = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_ROWS_PX)}px`;
    el.style.overflowY = el.scrollHeight > MAX_ROWS_PX ? 'auto' : 'hidden';
  }, []);

  useEffect(() => resize(), [input, resize]);

  const send = async () => {
    const text = input.trim();
    if (!text || isProcessing || !sessionId) return;
    const store = useGameStore.getState();
    store.addPlayerMessage(text);
    store.setProcessing(true);
    store.setChoices([]);
    store.setDecisionSuggestions([]);
    store.setJournalStatus('syncing');
    setInput('');
    try {
      const r = await fetch(
        `/api/game/${sessionId}/action?username=${encodeURIComponent(useGameStore.getState().status.username || 'default')}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_input: text }) },
      );
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        store.appendNarrativeText(`⚠ ${e.detail || '发送失败'}`);
        store.setProcessing(false);
      }
    } catch {
      store.appendNarrativeText('⚠ 网络错误');
      store.setProcessing(false);
    }
  };

  const abort = async () => {
    if (!sessionId) return;
    try {
      await fetch(`/api/game/${sessionId}/abort?username=${encodeURIComponent(useGameStore.getState().status.username || 'default')}`, { method: 'POST' });
    } catch {}
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 中文输入法组合中（keyCode 229 / isComposing）不触发发送
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  const canSend = !!input.trim() && !isProcessing && !!sessionId;

  return (
    <div className="border-t border-ink-200 bg-white/80 backdrop-blur-sm px-3 sm:px-4 pt-3 pb-safe">
      <div className="mx-auto w-full max-w-3xl">
        <div
          className={`flex items-end gap-2 rounded-2xl border bg-white px-3 py-2 transition-all duration-150 ${
            focused ? 'border-brand-400 ring-4 ring-brand-500/10' : 'border-ink-200'
          }`}
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={isProcessing ? '主持正在回应，稍候…（可点跳过）' : '描述你的行动…'}
            disabled={isProcessing}
            aria-label="行动输入框"
            className="flex-1 resize-none bg-transparent text-sm leading-relaxed text-ink-800 placeholder:text-ink-500
                       disabled:text-ink-500 py-1.5 max-h-[132px] overflow-y-auto"
          />

          <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
            {isProcessing ? (
              <button
                onClick={abort}
                className="inline-flex items-center gap-1.5 text-2xs font-medium px-3 py-2 rounded-xl
                           border border-ink-200 bg-white text-ink-500 hover:bg-ink-50 hover:text-ink-700 transition-colors"
                title="中止本次生成"
              >
                <svg viewBox="0 0 20 20" fill="none" className="w-3.5 h-3.5" aria-hidden>
                  <rect x="6" y="6" width="8" height="8" rx="1.5" fill="currentColor" />
                </svg>
                跳过
              </button>
            ) : (
              <button
                onClick={send}
                disabled={!canSend}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-4 py-2.5 rounded-xl
                           bg-brand-600 text-white shadow-sm hover:bg-brand-700
                           disabled:bg-ink-100 disabled:text-ink-600 disabled:shadow-none disabled:cursor-not-allowed
                           transition-all duration-150"
              >
                <svg viewBox="0 0 20 20" fill="none" className="w-3.5 h-3.5" aria-hidden>
                  <path d="M3.5 10h12m0 0l-5-5m5 5l-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                发送
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-2 mt-1.5 px-1">
          <p className="text-3xs text-ink-500">
            <kbd className="px-1.5 py-0.5 rounded border border-ink-300 bg-ink-100 font-sans text-3xs text-ink-600">Enter</kbd> 发送 ·{' '}
            <kbd className="px-1.5 py-0.5 rounded border border-ink-300 bg-ink-100 font-sans text-3xs text-ink-600">Shift+Enter</kbd> 换行
          </p>
          {isProcessing && (
            <p className="text-3xs text-brand-600 flex items-center gap-1" aria-live="polite">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse-soft" />
              正在生成
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
