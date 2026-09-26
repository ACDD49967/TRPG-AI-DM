/** 删除媒体条目（法术 / 地图 / 图鉴）：三者 DELETE 路由形状一致，统一在这里拼。
 *
 * 游戏中的媒体弹窗此前只能新建与编辑，删不掉；补上删除并复用同一份 URL 规则。
 */
export type MediaKind = 'spell' | 'map' | 'beast';

const BASE: Record<MediaKind, string> = {
  spell: '/api/spells',
  map: '/api/maps',
  beast: '/api/bestiary',
};

export async function deleteMediaItem(
  kind: MediaKind, id: string, username?: string,
): Promise<boolean> {
  const user = encodeURIComponent(username || 'default');
  try {
    const response = await fetch(
      `${BASE[kind]}/${encodeURIComponent(String(id))}?username=${user}`,
      { method: 'DELETE' });
    return response.ok;
  } catch {
    return false;
  }
}
