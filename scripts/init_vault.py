"""
初始化 Obsidian Vault 目录结构
用法: python scripts/init_vault.py --path ~/Documents/MyVault
"""

import argparse
from pathlib import Path


VAULT_STRUCTURE = {
    "00-Inbox": "快速捕获，待整理的笔记",
    "01-Notes": "正式笔记",
    "01-Notes/AI-ML": "AI/机器学习笔记",
    "01-Notes/课程笔记": "大学课程笔记",
    "01-Notes/编程实践": "代码/项目经验",
    "01-Notes/工具技巧": "工具使用技巧",
    "02-Resources": "外部资源",
    "02-Resources/GitHub-Trending": "GitHub 热点日报（自动生成）",
    "02-Resources/论文笔记": "论文阅读笔记",
    "03-Templates": "笔记模板",
    "04-Daily": "每日笔记",
    "05-Learning": "学习计划与记录",
    "05-Learning/plans": "学习计划",
    "05-Learning/quizzes": "测验记录",
    "99-Archive": "归档",
}

TEMPLATES = {
    "03-Templates/课堂笔记模板.md": """---
created: {date}
type: class-note
course: 
tags: [课堂笔记]
---

# {title}

## 课程信息
- 课程名称：
- 日期：{date}
- 讲师：

## 核心内容


## 关键概念


## 代码/公式


## 疑问与后续

## 相关笔记
""",

    "03-Templates/技术笔记模板.md": """---
created: {date}
type: tech-note
tags: [技术笔记]
---

# {title}

## 概述


## 核心原理


## 代码实现
```python

```

## 实践要点


## 参考资料
- 

## 相关笔记
- 
""",

    "03-Templates/项目笔记模板.md": """---
created: {date}
type: project-note
status: active
tags: [项目笔记]
---

# {title}

## 项目信息
- GitHub：
- 技术栈：
- 状态：进行中

## 架构设计


## 开发日志

### {date}
- 

## 踩坑记录


## 相关笔记
- 
""",
}


def init_vault(vault_path: str):
    """初始化 Vault 目录结构和模板"""
    root = Path(vault_path).expanduser().resolve()

    if not root.exists():
        root.mkdir(parents=True)
        print(f"创建 Vault: {root}")
    else:
        print(f"Vault 已存在: {root}")

    # 创建目录结构
    for dirpath, desc in VAULT_STRUCTURE.items():
        full = root / dirpath
        if not full.exists():
            full.mkdir(parents=True, exist_ok=True)
            print(f"  + {dirpath}/ ({desc})")
        else:
            print(f"  = {dirpath}/ (已存在)")

    # 创建模板文件
    from datetime import date
    today = date.today().isoformat()

    for tmpl_path, tmpl_content in TEMPLATES.items():
        full = root / tmpl_path
        if not full.exists():
            content = tmpl_content.format(date=today, title="新笔记")
            full.write_text(content, encoding="utf-8")
            print(f"  + {tmpl_path}")
        else:
            print(f"  = {tmpl_path} (已存在)")

    # 创建 .obsidian 目录占位（实际配置由 Obsidian App 生成）
    obsidian_dir = root / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    # 创建 README
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(f"""# My Knowledge Vault

初始化日期：{today}

## 目录说明
- `00-Inbox/` - 快速捕获
- `01-Notes/` - 正式笔记
- `02-Resources/` - 外部资源（GitHub热点自动生成）
- `03-Templates/` - 笔记模板
- `04-Daily/` - 每日笔记
- `05-Learning/` - 学习计划与测验记录
- `99-Archive/` - 归档

## 推荐插件
- Templater - 模板自动化
- Dataview - 动态查询
- Obsidian Git - 自动备份
- Smart Connections - 语义搜索
""", encoding="utf-8")
        print(f"  + README.md")

    print(f"\nVault 初始化完成: {root}")
    print(f"用 Obsidian 打开此文件夹即可。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化 Obsidian Vault")
    parser.add_argument("--path", required=True, help="Vault 路径")
    args = parser.parse_args()
    init_vault(args.path)
