"""持久化世界状态——NPC可见度控制、场景追踪、时间系统。

核心设计：
- 每个NPC有 visibility 字典控制哪些字段对玩家可见
- 场景追踪：当前时间、地点、天气、氛围
- 玩家笔记：仅导出可见信息到前端侧边栏
- AI可通过 reveal_info 工具修改可见度
"""

from dataclasses import dataclass, field

# 数据模型与文本清洗各有归属模块，这里只做再导出：
# 既有 `from backend.engine.world_state import NpcEntry / clean_scene_text` 不变。
from backend.engine.world_models import (
    CharacterNote, LocationEntry, NotableEntry, NpcEntry, NpcVisibility,
    PlotFlag, SceneInfo,
)
# 下划线常量是同包的内部约定（清洗规则与列表上限），world_state 的查询入口直接复用
from backend.engine.world_names import (
    _EMPTY_NPC_TOKENS, _SCENE_MAX_VISIBLE_NPCS, _SCENE_TEXT_LIMITS,
    _cut_annotation, clean_location_name, clean_npc_name, clean_scene_text,
)



from backend.engine.world_note_mixin import WorldNoteMixin
from backend.engine.world_npc_mixin import WorldNpcMixin
from backend.engine.world_scene_mixin import WorldSceneMixin


@dataclass
class WorldState(WorldNpcMixin, WorldSceneMixin, WorldNoteMixin):
    """完整的持久化世界状态。"""
    session_id: str = ""
    world_title: str = ""
    world_outline: str = ""
    world_rules: str = ""

    npcs: list[NpcEntry] = field(default_factory=list)
    plot_flags: list[PlotFlag] = field(default_factory=list)
    locations: list[LocationEntry] = field(default_factory=list)
    creatures: list = field(default_factory=list)
    spells: list = field(default_factory=list)

    scene: SceneInfo = field(default_factory=SceneInfo)

    # 角色视角笔记
    character_notes: list[CharacterNote] = field(default_factory=list)

    # 值得注意的场景/物品/线索（冒险笔记“角色和场景”页）
    notables: list[NotableEntry] = field(default_factory=list)
    turn_count: int = 0  # 当前轮数

    # 幕后剧情事件：玩家不在场时世界仍在推进
    background_events: list[dict] = field(default_factory=list)

    # 显式关系边（类知识图谱）：source/target/relation/strength/confidence/notes
    relations: list[dict] = field(default_factory=list)

    change_log: list[dict] = field(default_factory=list)
    _storage_dir: str = field(default="world_states", repr=False)

    @classmethod


    def load(cls, session_id: str, storage_dir: str = "world_states"):
        """从磁盘加载（实现见 world_io.load_world）。"""
        from backend.engine.world_io import load_world
        return load_world(cls, session_id, storage_dir)

    def save(self):
        """实现见 world_io.save_world。"""
        from backend.engine.world_io import save_world
        return save_world(self)


    def advance_turn(self):
        """推进轮数。"""
        self.turn_count += 1
        # 可选：不每次保存，由调用方决定

    def _log_change(self, desc: str):
        """实现见 world_io.log_change。"""
        from backend.engine.world_io import log_change
        return log_change(self, desc)

    def _maintenance_impl(self, scope: str = "all", older_than_turns: int = 20,
                          max_notes: int = 120, max_relations: int = 400,
                          max_change_log: int = 300, max_background: int = 100):
        """实现见 world_maintenance.maintenance_impl。"""
        from backend.engine.world_maintenance import maintenance_impl
        return maintenance_impl(self, scope, older_than_turns, max_notes,
                                max_relations, max_change_log, max_background)

    def maintenance(self, scope: str = "all", older_than_turns: int = 20,
                    max_notes: int = 120, max_relations: int = 400,
                    max_change_log: int = 300, max_background: int = 100,
                    dry_run: bool = False):
        """实现见 world_maintenance.run_maintenance。"""
        from backend.engine.world_maintenance import run_maintenance
        return run_maintenance(self, scope, older_than_turns, max_notes,
                               max_relations, max_change_log, max_background, dry_run)

    def to_player_journal(self) -> dict:
        """实现见 world_context.to_player_journal。"""
        from backend.engine.world_context import to_player_journal
        return to_player_journal(self)

    def to_context_string(self) -> str:
        """实现见 world_context.to_context_string。"""
        from backend.engine.world_context import to_context_string
        return to_context_string(self)

    def to_context_compact(self) -> str:
        """实现见 world_context.to_context_compact。"""
        from backend.engine.world_context import to_context_compact
        return to_context_compact(self)


# 数据模型与清洗函数的再导出已在文件顶部完成（历史调用方从本模块取这些名字）。


def cleanup_world_states(storage_dir: str = "world_states", active_session_ids: list[str] | None = None,
                         max_age_days: int = 7) -> int:
    """清理不再活跃且超过保留期的 world_state JSON 文件。

    存档本身包含 world_state 快照，因此这里的运行期文件可以安全清理。
    """
    import os
    import time

    if not os.path.isdir(storage_dir):
        return 0
    active = set(active_session_ids or [])
    now = time.time()
    removed = 0
    for fn in os.listdir(storage_dir):
        if not fn.endswith(".json"):
            continue
        sid = fn[:-5]
        if sid in active:
            continue
        path = os.path.join(storage_dir, fn)
        try:
            if now - os.path.getmtime(path) > max_age_days * 86400:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
