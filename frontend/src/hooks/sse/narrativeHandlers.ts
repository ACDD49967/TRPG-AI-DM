/** 叙事流相关 SSE 处理器：正文、骰子、历史、回合收尾与错误。 */
import type { SSEHandler, SSEHandlerDeps } from './handlerTypes';

export function createNarrativeHandlers(deps: SSEHandlerDeps): Record<string, SSEHandler> {
  const { store, refreshMetrics } = deps;
  return {
    intro: (data) => {
      const scene = data.scene as string;
      if (scene) {
        store.getState().appendNarrativeText(scene);
      }
      store.getState().setProcessing(false);
    },

    narrative: (data) => {
      const token = data.token as string;
      if (token) {
        store.getState().appendToken(token);
      }
    },

    narrative_flush: (data) => {
      const fullText = data.full_text as string;
      if (fullText) {
        store.getState().appendNarrativeText(fullText);
      }
    },

    dice_roll: (data) => {
      // 骰名以规则为准：后端给了 display 就用它（COC 是 d100、自定义可能是 2d10），
      // 否则回退到 d20 模板
      const detail = (data.display as string | undefined)
        || `${data.skill}检定 d20=${data.roll}${data.modifier ? `+${data.modifier}` : ''} vs DC${data.dc} → ${data.result}`;
      store.getState().appendDiceRoll({
        skill: data.skill as string,
        dc: data.dc as number,
        roll: data.roll as number,
        modifier: (data.modifier as number) || 0,
        result: data.result as string,
        display: data.display as string | undefined,
        advantage: data.advantage as string | undefined,
        advantage_note: data.advantage_note as string | undefined,
      });
      store.getState().appendCombatLog({ kind: 'dice', text: detail });
    },

    choices: (data) => {
      const options = data.options as string[];
      if (Array.isArray(options)) {
        store.getState().setChoices(options);
      }
    },

    error: (data) => {
      console.error('[SSE] 错误:', data.msg);
      store.getState().appendNarrativeText(`错误：${data.msg}`);
    },

    history: (data) => {
      const turns = data.turns as Array<{ player_input: string; dm_response: string }> | undefined;
      if (!Array.isArray(turns)) return;
      const st = store.getState();
      for (const t of turns) {
        if (t.player_input) st.addPlayerMessage(t.player_input);
        if (t.dm_response) st.appendNarrativeText(t.dm_response);
      }
    },

    end_of_turn: () => {
      // 先获取缓冲区文本用于提取决策
      const buf = store.getState().currentTokenBuffer;
      // 刷新打字机缓冲区
      store.getState().flushBuffer();
      // 从本轮AI回复中提取决策建议
      if (buf) {
        store.getState().extractDecisions(buf);
      }
      store.getState().setProcessing(false);
      // 清除骰子高亮
      setTimeout(() => store.getState().setLatestDiceRoll(null), 5000);
      // 回合结束后拉一次统计（此时本轮还没结算，拿到的总量正确、明细缺当前轮）
      refreshMetrics();
    },

    // 后端在回合真正结算后再推一次：这时 recent_turns 才包含刚结束的这一轮
    metrics_update: () => {
      refreshMetrics();
    },
  };
}
