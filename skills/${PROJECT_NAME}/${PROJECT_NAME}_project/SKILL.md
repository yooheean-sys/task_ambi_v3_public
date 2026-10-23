---
name: ${PROJECT_NAME}_project
description: task_ambi作業時。ソース管理は ~/project/task_ambi/${REPO_NAME} が基本。
version: 1.0
author: ${USER_NAME_LOWER}
license: private
metadata:
  hermes:
    tags: [task_ambi, git, gitlab]
    related_skills: [${PROJECT_NAME}_kanban-agent-org, ${PROJECT_NAME}_boot]
---

# task_ambi プロジェクト

## When to Use
- task_ambi のコードを読む・直す・コミットする作業をするとき
- 「このプロジェクト」が task_ambi を指しているときのソース管理先の確認

- ソースコード管理（ユーザー指定の基本）:
  - ローカル: `${REPO_ROOT}`
  - リモート: `origin = https://${GITLAB_URL_ORG}/${REPO_NAME}.0.git`
  - `main` ブランチが `origin/main` を追跡（2026-10-17 時点で同期済み・`ls-remote` 到達確認済み）
- 同じ親ディレクトリに `task_ambi_2609` / `task_ambi_public` / `publish_tools` がある（用途は未確認）
- Obsidian vault `${VAULT_NAME}`（`${VAULT_ROOT}`）は Git 管理外。同期は Dropbox + Remotely Save プラグインのみ。
