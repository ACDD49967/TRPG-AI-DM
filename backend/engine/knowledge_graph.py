"""类知识图谱：把世界状态中的角色/地点/生物/剧情组织成节点与关系。

- 节点来自 npcs/locations/creatures/plot_flags；
- 边来自结构化 related_* 字段 + 显式关系表（含亲密度/置信度）；
- 支持局部子图查询与向量化检索。

构建、查询、文本检索按职责拆到三个模块；这里只做再导出，既有 import 不用改：

- 构建：`graph_build`（`build_knowledge_graph` / `build_player_graph`）
- 查询：`graph_query`（局部子图 / 两点路径）
- 文本与检索：`graph_context`（`graph_to_context` / `search_graph_nodes`）
"""
from backend.engine.graph_build import (  # noqa: F401
    _add_edge, _norm_list, _relation_index, _resolve_player_node,
    build_knowledge_graph, build_player_graph,
)
from backend.engine.graph_query import (  # noqa: F401
    get_graph_path, get_local_subgraph, get_local_subgraph_from_graph,
)
from backend.engine.graph_context import (  # noqa: F401
    _tokenize, _vectorize_nodes, graph_to_context, search_graph_nodes,
)
