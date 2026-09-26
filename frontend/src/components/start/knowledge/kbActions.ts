/** 知识库动作门面：查询与摄入各自一个模块，这里组合后统一对外。
 *
 * 查询/删除/播种/LLM 注入 → `kbQuery`，备注/上传/取消 → `kbIngest`。
 */
import type { KbActionsContext } from './kbContext';
import { createKbIngest } from './kbIngest';
import { createKbQuery } from './kbQuery';

export type { KbActionsContext } from './kbContext';

export function createKbActions(ctx: KbActionsContext) {
  const query = createKbQuery(ctx);
  const ingest = createKbIngest(ctx, query.loadKb);
  return { ...query, ...ingest };
}
