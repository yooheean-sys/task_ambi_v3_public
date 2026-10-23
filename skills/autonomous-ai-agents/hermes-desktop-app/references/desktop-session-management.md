# Desktop session management — verified facts

Session state lives in `~/.hermes/state.db`, table `sessions`. Visibility flags (0/1):

- `archived` — soft-hidden by the user, the Dashboard/API, or a bulk CLI archive. Messages and search stay intact.
- `auto_archived` — hidden by the `sessions.auto_archive` idle sweep (Settings → 「古いチャットを自動アーカイブ」).
- `pinned` — durable keep flag; pinned sessions are exempt from auto-archive and pruning.
- `hidden` — Bot-Mode routing chats (never appears in the sidebar).

## Archive entry points

- Desktop sidebar: Alt/⌥+Shift-click a chat row, or the row's ⋯ menu → 「アーカイブ」.
- CLI bulk: `hermes sessions archive` (same filters as `prune`; at least one filter required; `--dry-run` previews). Sets the same `archived` flag as the UI.

## Restore (unarchive) paths — UI only, no CLI subcommand

1. 設定 → 「アーカイブ済みチャット」 page → row's 「アーカイブを解除」 button.
2. Sidebar filter menu → turn ON the 「アーカイブ済み」 toggle → the sidebar switches to the archived list → row ⋯ menu → 「アーカイブを解除」. In the archived view the same menu verb that archives restores instead.

## Behavior notes

- An auto-archived chat resurfaces on its own; a user-archived chat stays archived until explicitly unarchived.
- Archived sessions are hidden from `hermes sessions list` and `/resume` but remain fully queryable in `state.db` and in FTS search.
- Exports/imports preserve the archived/pinned/hidden flags.

Source references (in `~/.hermes/hermes-agent/apps/desktop/src`): `app/chat/sidebar/session-actions-menu.tsx` (restore verb), `app/chat/sidebar/filter-menu.tsx` (`$sidebarShowArchived` toggle), `app/settings/sessions-settings.tsx` (archived-chats page), `app/session/hooks/use-session-actions/unarchive-session.test.tsx`.
