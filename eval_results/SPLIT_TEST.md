# 切分功能测试报告

## 测试样本

| 格式 | 样本来源 | 大小 |
|------|---------|------|
| `.md` | The Delian Tomb（GitHub README） | ~4.7 KB |
| `.txt` | 同一份 Delian Tomb 文本 | ~4.7 KB |
| `.docx` | 使用 python-docx 从 Delian Tomb 文本生成 | ~38 KB |
| `.doc` | UTF-8 纯文本 fallback 样本（模拟旧格式 fallback 路径） | ~4.7 KB |
| `.pdf` | Chaosium 官方《Call of Cthulhu 7e Quick-Start Rules》 | ~32 MB |

## 测试结果

| 格式 | 提取字符数 | 切分器块数 | 语义切分块数 | 自动识别系统 | 是否通过 |
|------|-----------|-----------|-------------|-------------|---------|
| md | 4723 | 8 | 6 | dnd5e | ✅ |
| txt | 4723 | 8 | 6 | dnd5e | ✅ |
| docx | 4645 | 6 | 6 | dnd5e | ✅ |
| doc | 4721 | 8 | 6 | dnd5e | ✅ |
| pdf | 113472 | 152 | 199 | coc | ✅ |

## 验证点

- **格式识别**：`.md/.txt/.docx/.doc` 均成功进入对应解析分支，`.pdf` 成功通过 pypdf 提取。
- **格式分化**：
  - DND 系文本（Delian Tomb）自动识别为 `dnd5e`
  - COC 官方 Quick-Start PDF 自动识别为 `coc`
- **切分可用性**：
  - 切分器（naive）：按段落/字数稳定切分
  - 语义切分：按句子相似度分组，能保留英文 Markdown 的可读空格，不再把 `![Version]` 错误拆开
- **`.doc` 说明**：本次使用 UTF-8 纯文本 fallback 样本验证 fallback 路径；真实二进制 `.doc` 仍依赖系统 `antiword`，否则会退回文本提取。

## 修复的问题

1. **语义切分英文拼接丢空格**
   - 修复前：`# The Delian Tomb![Version]`
   - 修复后：`# The Delian Tomb ![Version]`
2. **语义切分把 Markdown 图片语法 `![` 当成句子边界**
   - 修复后：英文 `!`/`?` 仅在后面有空白时才作为句子边界。

## 复现命令

```bash
PYTHONPATH=. .venv/Scripts/python.exe scripts/test_splitting.py
```

原始 JSON 报告位于 `eval_results/split_test_report.json`（已 gitignore）。
