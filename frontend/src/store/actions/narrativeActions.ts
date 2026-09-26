/** 叙事相关 store 动作：token 缓冲、玩家消息、骰子、事件与决策提取。 */
import type { GameState } from '../gameStateShape';

type StoreSet = (
  partial: Partial<GameState> | ((state: GameState) => Partial<GameState>)
) => void;
type StoreGet = () => GameState;

export function createNarrativeActions(
  set: StoreSet,
  get: StoreGet,
): Pick<
  GameState,
  | 'extractDecisions'
  | 'appendToken'
  | 'flushBuffer'
  | 'appendNarrativeText'
  | 'addPlayerMessage'
  | 'appendDiceRoll'
  | 'appendGameEvent'
> {
  return {
    /** 从AI回复文本中提取决策建议 */
    extractDecisions: (text: string) => {
      const lines = text.split('\n');
      const decisionIdx = lines.findIndex(l =>
        l.includes('决策建议') || l.includes('**决策建议**')
      );
      if (decisionIdx >= 0) {
        const suggestions = lines.slice(decisionIdx + 1)
          .filter(l => l.trim().startsWith('-') || l.trim().startsWith('*'))
          .map(l => l.replace(/^[-*]\s*/, '').replace(/\[|\]/g, '').trim())
          .filter(l => l.length > 0)
          .slice(0, 4);
        if (suggestions.length > 0) {
          get().setDecisionSuggestions(suggestions);
        }
      }
    },

    appendToken: (token) =>
      set((s) => ({ currentTokenBuffer: s.currentTokenBuffer + token })),

    flushBuffer: () => {
      const buf = get().currentTokenBuffer;
      if (!buf.trim()) return;
      const id = get().narrativeId;
      set((s) => ({
        narrative: [...s.narrative, { id, text: buf, role: 'dm' }],
        currentTokenBuffer: '',
        narrativeId: id + 1,
      }));
    },

    appendNarrativeText: (text) => {
      // 先刷新当前缓冲区
      const buf = get().currentTokenBuffer;
      if (buf.trim()) {
        get().flushBuffer();
      }
      // 追加新文本
      const id = get().narrativeId;
      set((s) => ({
        narrative: [...s.narrative, { id, text, role: 'dm' }],
        narrativeId: id + 1,
      }));
    },

    addPlayerMessage: (text) => {
      const id = get().narrativeId;
      set((s) => ({
        narrative: [...s.narrative, { id, text, role: 'player' }],
        narrativeId: id + 1,
      }));
    },

    appendDiceRoll: (data) => {
      // 先刷新当前缓冲区
      const buf = get().currentTokenBuffer;
      if (buf.trim()) {
        get().flushBuffer();
      }
      const id = get().narrativeId;
      set((s) => ({
        narrative: [
          ...s.narrative,
          {
            id,
            // 骰名以规则为准：后端给了 display 就照它显示（COC 的 d100、自定义的 2d10），否则按 d20 拼
            text: (data as { display?: string }).display
              ? `检定：${(data as { display?: string }).display}`
              : `检定：${data.skill} d20=${data.roll}${data.modifier ? `+${data.modifier}` : ''} vs DC${data.dc} → ${data.result}`,
            role: 'dm',
            isDiceRoll: true,
            diceData: data,
          },
        ],
        latestDiceRoll: data,
        narrativeId: id + 1,
        // 自动清理骰子弹窗（5秒后）
      }));
    },

    appendGameEvent: (data) => {
      const buf = get().currentTokenBuffer;
      if (buf.trim()) {
        get().flushBuffer();
      }
      const id = get().narrativeId;
      set((s) => ({
        narrative: [
          ...s.narrative,
          {
            id,
            text: `事件：${data.description}`,
            role: 'dm',
            isGameEvent: true,
            gameEventData: data,
          },
        ],
        narrativeId: id + 1,
      }));
    },
  };
}
