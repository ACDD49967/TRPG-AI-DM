/** 剧本工坊的 SSE 读取：把 fetch 响应按空行切事件，逐条交给回调。
 *
 * 世界生成与剧本导入用的是同一套 `data: {...}\n\n` 协议，两处循环原本各写一遍；
 * 抽出来后只需要维护一份解析逻辑（取消仍由调用方 abort 掉 fetch，AbortError 由调用方处理）。
 */
export async function readEventStream(
  response: Response,
  onEvent: (data: Record<string, unknown>) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    for (const evt of events) {
      const line = evt.split('\n').find((l) => l.startsWith('data: '));
      if (!line) continue;
      onEvent(JSON.parse(line.slice(6)) as Record<string, unknown>);
    }
  }
}

/** 剧本列表的统一刷新（生成/导入/改名后都会用到）。 */
export async function refreshScenarioList(username: string): Promise<unknown[]> {
  try {
    const r = await fetch(`/api/scenarios?username=${encodeURIComponent(username || 'default')}`);
    const d = await r.json();
    return d.scenarios || [];
  } catch {
    return [];
  }
}
