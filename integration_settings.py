#!/usr/bin/env python3
"""MCP/hooks の安全な部分移行（POSIX / Python >= 3.13、PyYAML が必要）。

公開 API は validate_source(Path) -> None。環境値・導入先・Hermes を参照せず、
JSON と agent-hooks/ の構造だけを検査する。CLI は source/home/env-file と
排他的な dry-run / apply / verify / seed-profile を受け取る。

config の意味変更は隔離した実 Hermes CLI に任せ、RAW 値全体の一致を確認後に
atomic 配置する。mcp_servers/hooks 以外の意味値は追加・削除・上書きしない。
local/harness-integration.json の schema_version=1 は mcp_servers（名前→hash）、
hooks（event→block hash のリスト）、root のみ scripts（home 相対path→hash）。
ハッシュはソート済み UTF-8 JSON（または script のバイト列）の SHA-256。
値そのものを管理情報・stdout/stderr に出さず、未管理の同一定義は所有しない。
失敗時は復元し、外部変更を検知した場合は上書きせず保護バックアップを残す。
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any


class IntegrationError(ValueError):
    """値そのもの（秘密を含み得る）を表示しない検証エラー。"""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IntegrationError("JSON キーが重複しています")
        result[key] = value
    return result


def _plain_path(path: Path) -> Path:
    """resolve() でリンクを隠さず、全既存祖先を lstat で検査する。"""
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise IntegrationError("シンボリックリンクは使用できません")
        if part != path and not stat.S_ISDIR(mode):
            raise IntegrationError("パスの祖先がディレクトリではありません")
    return path


def _regular_file(path: Path) -> Path:
    path = _plain_path(path)
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise IntegrationError("通常ファイルではありません")
    except FileNotFoundError:
        raise IntegrationError("必須ファイルがありません") from None
    return path


def _text(path: Path) -> str:
    try:
        state = _state(path)
        if state is None:
            raise IntegrationError("必須ファイルがありません（config は事前の Hermes 初期設定が必要です）")
        return state[0].decode("utf-8-sig")
    except (OSError, UnicodeError):
        raise IntegrationError("UTF-8 ファイルを読み取れません") from None


def _read_json(path: Path):
    try:
        result = json.loads(_text(path), object_pairs_hook=_object,
                            parse_constant=lambda _: _invalid("JSON 数値が不正です"))
        _json_value(result)
        return result
    except (json.JSONDecodeError, RecursionError):
        raise IntegrationError("JSON が不正です") from None


def _json_value(value, active=None):
    active = set() if active is None else active
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise IntegrationError("JSON に不正な Unicode が含まれています") from None
        return
    if type(value) in (bool, int, type(None)):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise IntegrationError("JSON 数値が有限ではありません")
        return
    if type(value) not in (dict, list) or id(value) in active:
        raise IntegrationError("JSON の型または循環参照が不正です")
    active.add(id(value))
    try:
        if isinstance(value, dict):
            if any(not isinstance(key, str) for key in value):
                raise IntegrationError("JSON キーは文字列が必須です")
            for key in value:
                _json_value(key, active)
            values = value.values()
        else:
            values = value
        for item in values:
            _json_value(item, active)
    finally:
        active.remove(id(value))


def _invalid(message):
    raise IntegrationError(message)


def _name(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 for c in value)


def _mcp(value) -> None:
    if not isinstance(value, dict):
        raise IntegrationError("mcpServers/mcp_servers は辞書が必須です")
    _json_value(value)
    for name, server in value.items():
        if not _name(name) or not isinstance(server, dict):
            raise IntegrationError("MCP 定義の型が不正です")
        if not any(_name(server.get(k)) for k in ("command", "url")):
            raise IntegrationError("MCP command または url が必要です")
        for key in ("command", "url", "transport", "type", "cwd"):
            if key in server and not _name(server[key]):
                raise IntegrationError("MCP 文字列の型が不正です")
        if "args" in server and (not isinstance(server["args"], list)
                                  or any(not isinstance(a, str) for a in server["args"])):
            raise IntegrationError("MCP args は文字列のリストが必須です")
        for key in ("env", "headers"):
            if key in server and (not isinstance(server[key], dict)
                    or any(not _name(k) or not isinstance(v, str) for k, v in server[key].items())):
                raise IntegrationError("MCP env/headers の型が不正です")
        if "enabled" in server and not isinstance(server["enabled"], bool):
            raise IntegrationError("MCP enabled は真偽値が必須です")


def _identity(hook):
    return hook["command"], hook.get("matcher")


def _hooks(value) -> None:
    if not isinstance(value, dict):
        raise IntegrationError("hooks は辞書が必須です")
    _json_value(value)
    for event, blocks in value.items():
        if not _name(event) or not isinstance(blocks, list):
            raise IntegrationError("hook event はリストが必須です")
        seen = set()
        for block in blocks:
            if not isinstance(block, dict) or not _name(block.get("command")):
                raise IntegrationError("hook command は文字列が必須です")
            if "matcher" in block and not isinstance(block["matcher"], str):
                raise IntegrationError("hook matcher は文字列が必須です")
            if "timeout" in block and (type(block["timeout"]) not in (int, float)
                    or not math.isfinite(block["timeout"]) or block["timeout"] <= 0):
                raise IntegrationError("hook timeout は正の数が必須です")
            identity = _identity(block)
            if identity in seen:
                raise IntegrationError("hook の同一 command/matcher が重複しています")
            seen.add(identity)


def _relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or str(path) != value
            or any(p in ("", ".", "..") for p in value.split("/"))
            or "\\" in value or ":" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise IntegrationError("相対パスが不正です")
    return path


def _source_scripts(source: Path) -> dict[str, bytes]:
    root = _plain_path(source / "agent-hooks")
    if not root.is_dir():
        raise IntegrationError("agent-hooks/ がありません")
    result = {}
    def walk_error(_):
        raise IntegrationError("agent-hooks/ を読み取れません")
    for parent, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in sorted(dirs + files):
            child = _plain_path(Path(parent) / name)
            relative = str(child.relative_to(root))
            _relative(relative)
            if child.is_dir():
                continue
            _regular_file(child)
            state = _state(child)
            if state is None:
                raise IntegrationError("script が読取り中に消えました")
            result[relative] = state[0]
    return result


def validate_source(source: Path) -> None:
    """env/導入先を参照せず JSON と scripts ツリーを検証する（書込みゼロ）。"""
    source = _plain_path(source)
    for filename, key, validator in (("mcp.json", "mcpServers", _mcp),
                                      ("hooks.json", "hooks", _hooks)):
        value = _read_json(source / filename)
        if not isinstance(value, dict) or key not in value:
            raise IntegrationError("配布 JSON に必須の辞書がありません")
        validator(value[key])
    _source_scripts(source)


# トークン名だけを格納する。逆方向定義に機器固有値を埋め込まない。
PLACEHOLDER_MAP = {
    "VAULT_ROOT": "HARNESS_VAULT_ROOT", "REPO_ROOT": "HARNESS_PROJECT_ROOT",
    "ORG_ROOT": "HARNESS_ORG_ROOT", "KANBAN_RUNS_ROOT": "HARNESS_KANBAN_RUNS_DIR",
    "HERMES_HOME": "HARNESS_HOME", "USER_HOME": "HARNESS_USER_HOME",
    "USER_HOME_MAC": "HARNESS_USER_HOME_MAC", "USER_NAME": "HARNESS_USER_NAME",
    "USER_NAME_LOWER": "HARNESS_USER_NAME_LOWER", "VAULT_NAME": "HARNESS_VAULT_NAME",
    "LOCAL_IP": "HARNESS_LOCAL_IP", "KANBAN_RUNS_DIR": "HARNESS_KANBAN_RUNS_DIR",
    "GITLAB_URL_ORG": "HARNESS_GITLAB_URL_ORG", "GITLAB_HOST": "HARNESS_GITLAB_HOST",
    "ORG_NAME": "HARNESS_ORG_NAME", "REPO_NAME": "HARNESS_REPO_NAME",
    "PROJECT_G01_NAME": "HARNESS_PROJECT_G01_NAME",
    "PROJECT_H01_NAME": "HARNESS_PROJECT_H01_NAME", "PROJECT_P01_NAME": "HARNESS_PROJECT_P01_NAME",
    "PROJECT_P02_NAME": "HARNESS_PROJECT_P02_NAME", "PROJECT_H02_NAME": "HARNESS_PROJECT_H02_NAME",
    "DASHBOARD_BASIC_AUTH_USERNAME": "HARNESS_DASHBOARD_BASIC_AUTH_USERNAME",
    "DASHBOARD_BASIC_AUTH_PASSWORD_HASH": "HARNESS_DASHBOARD_BASIC_AUTH_PASSWORD_HASH",
    "DASHBOARD_BASIC_AUTH_SECRET": "HARNESS_DASHBOARD_BASIC_AUTH_SECRET",
}
NAME_MAP_KEYS = {
    "g01": "HARNESS_PROJECT_G01_NAME", "org": "HARNESS_ORG_NAME",
    "h01": "HARNESS_PROJECT_H01_NAME", "p01": "HARNESS_PROJECT_P01_NAME",
    "p02": "HARNESS_PROJECT_P02_NAME", "h02": "HARNESS_PROJECT_H02_NAME",
    "repo": "HARNESS_REPO_NAME",
}


def _environment(env_file: Path, home: Path) -> dict[str, str]:
    result = {}
    for line in _text(env_file).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.startswith("HARNESS_"):
            if key in result:
                raise IntegrationError("HARNESS 環境キーが重複しています")
            result[key] = value
    for pair in result.get("HARNESS_PROJECT_NAME_MAP", "").split(","):
        pair = "".join(pair.split())
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        key = NAME_MAP_KEYS.get(name)
        if key and value and value != "REPLACE_ME" and not result.get(key):
            result[key] = value
    # 設定先は CLI 引数が正本。子プロファイルの HOME に置換してはいけない。
    result["HARNESS_HOME"] = str(home)
    return result


def _replace(text: str, env: dict[str, str]) -> str:
    import re
    def token(match):
        key = PLACEHOLDER_MAP.get(match.group(1))
        if key is None:
            return match.group(0)  # ${API_KEY} 等は秘密参照のまま残す。
        value = env.get(key)
        if not value or value == "REPLACE_ME":
            raise IntegrationError("使用する HARNESS 環境値が未設定です: " + key)
        return value
    return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", token, text)


def _read_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError as exc:
        raise IntegrationError("PyYAML が必要です（README: uv pip install -r pyproject.toml）") from exc
    import yaml
    class UniqueLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            self.flatten_mapping(node)
            result = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, (str, int, float, bool, type(None))):
                    raise IntegrationError("YAML キーの型が不正です")
                if key in result:
                    raise IntegrationError("YAML キーが重複しています")
                result[key] = self.construct_object(value_node, deep=deep)
            return result
    try:
        value = yaml.load(_text(path), Loader=UniqueLoader)
    except (yaml.YAMLError, RecursionError, TypeError):
        raise IntegrationError("config.yaml が不正です（Hermes 初期設定を確認してください）") from None
    if not isinstance(value, dict):
        raise IntegrationError("config.yaml は辞書が必須です（Hermes 初期設定が必要です）")
    _acyclic(value)
    _mcp(value.get("mcp_servers", {}))
    _hooks(value.get("hooks", {}))
    return value


def _acyclic(value, active=None):
    active = set() if active is None else active
    if not isinstance(value, (dict, list, set)):
        return
    if id(value) in active:
        raise IntegrationError("YAML の循環参照は移行できません")
    active.add(id(value))
    try:
        for item in (value.values() if isinstance(value, dict) else value):
            _acyclic(item, active)
    finally:
        active.remove(id(value))


def _profile_names(source: Path, env: dict[str, str]) -> list[str]:
    import re
    names = []
    for line in _text(source / "profiles.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = _replace(line, env).lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name) or name == "default":
            raise IntegrationError("profiles.txt の名前が不正です")
        if name in names:
            raise IntegrationError("profiles.txt に置換後の重複があります")
        names.append(name)
    return names


def _same(left, right) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same(v, right[k]) for k, v in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _hash(value) -> str:
    import hashlib
    data = value if isinstance(value, bytes) else _json_bytes(value)
    return hashlib.sha256(data).hexdigest()


def _expanded(value: Any, env: dict[str, str]) -> Any:
    if isinstance(value, str):
        return _replace(value, env)
    if isinstance(value, list):
        return [_expanded(item, env) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = _replace(key, env)
            if key in result:
                raise IntegrationError("置換後の JSON キーが重複しています")
            result[key] = _expanded(item, env)
        return result
    return value


def _command(command: str, env) -> str:
    """元のシェル構文を保持し、許可トークンの挿入だけを文脈別に引用する。"""
    import re
    import shlex
    pattern = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
    output, quote, index = [], None, 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'" and index + 1 < len(command):
            output.append(command[index:index + 2])
            index += 2
            continue
        match = pattern.match(command, index)
        if match and match.group(1) in PLACEHOLDER_MAP:
            value = _replace(match.group(0), env)
            if quote == "'":
                value = value.replace("'", "'\"'\"'")
            elif quote == '"':
                value = "".join(
                    "\\" + c if c in '\\$`"' else c for c in value)
            else:
                value = shlex.quote(value)
            output.append(value)
            index = match.end()
            continue
        if char in ("'", '"'):
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        output.append(char)
        index += 1
    if quote is not None:
        raise IntegrationError("hook command の引用が閉じていません")
    return "".join(output)


def _manifest(path: Path, *, root: bool) -> dict:
    import re
    if not path.exists():
        _plain_path(path)
        result = {"schema_version": 1, "mcp_servers": {}, "hooks": {}}
        if root:
            result["scripts"] = {}
        return result
    result = _read_json(path)
    if (not isinstance(result, dict) or type(result.get("schema_version")) is not int
            or result["schema_version"] != 1 or set(result) - {"schema_version", "mcp_servers", "hooks", "scripts"}
            or not isinstance(result.get("mcp_servers"), dict) or not isinstance(result.get("hooks"), dict)
            or (root and "scripts" not in result)
            or ("scripts" in result and not isinstance(result["scripts"], dict))
            or (not root and result.get("scripts"))):
        raise IntegrationError("管理情報の schema/type が不正です")
    def valid_hash(value):
        return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
    if any(not _name(k) or not valid_hash(v) for k, v in result["mcp_servers"].items()):
        raise IntegrationError("管理 MCP ハッシュが不正です")
    for event, hashes in result["hooks"].items():
        if (not _name(event) or not isinstance(hashes, list) or not all(valid_hash(v) for v in hashes)
                or len(set(hashes)) != len(hashes)):
            raise IntegrationError("管理 hook ハッシュが不正です")
    for relative, digest in result.get("scripts", {}).items():
        parts = _relative(relative).parts
        if len(parts) < 2 or parts[0] != "agent-hooks" or not valid_hash(digest):
            raise IntegrationError("管理 script のパス/ハッシュが不正です")
    return result


def _assert_owned(config, manifest):
    mcp, hooks = config.get("mcp_servers", {}), config.get("hooks", {})
    for name, digest in manifest["mcp_servers"].items():
        if name not in mcp or _hash(mcp[name]) != digest:
            raise IntegrationError("管理 MCP が利用者により変更/消去されています（競合）")
    for event, hashes in manifest["hooks"].items():
        current = [_hash(block) for block in hooks.get(event, [])]
        if any(current.count(digest) != 1 for digest in hashes):
            raise IntegrationError("管理 hook が利用者により変更/消去されています（競合）")


def _merge_config(config, desired_mcp, desired_hooks, old):
    import copy
    _assert_owned(config, old)
    merged = copy.deepcopy(config)
    mcp = merged.get("mcp_servers", {})
    hooks = merged.get("hooks", {})
    managed_mcp = dict(old["mcp_servers"])
    managed_hooks = {event: list(hashes) for event, hashes in old["hooks"].items()}
    next_mcp = {}
    for name in list(managed_mcp):
        if name not in desired_mcp:
            del mcp[name]
    for name, server in desired_mcp.items():
        if name in managed_mcp:
            mcp[name] = server
            next_mcp[name] = _hash(server)
        elif name in mcp:
            if not _same(mcp[name], server):
                raise IntegrationError("同名 MCP の未管理定義が異なります（競合）")
        else:
            mcp[name] = server
            next_mcp[name] = _hash(server)
    next_hooks = {}
    for event in dict.fromkeys([*hooks, *desired_hooks]):
        desired = {_identity(block): block for block in desired_hooks.get(event, [])}
        owned = set(managed_hooks.get(event, []))
        current, hashes = [], []
        for block in hooks.get(event, []):
            digest = _hash(block)
            replacement = desired.pop(_identity(block), None)
            if digest in owned:
                if replacement is not None:
                    current.append(replacement)
                    hashes.append(_hash(replacement))
            else:
                if replacement is not None and not _same(block, replacement):
                    raise IntegrationError("同一 hook の未管理パラメータが異なります（競合）")
                current.append(block)
        for block in desired.values():
            current.append(block)
            hashes.append(_hash(block))
        if not current and owned and event not in desired_hooks:
            hooks.pop(event, None)
        else:
            hooks[event] = current
        if hashes:
            next_hooks[event] = hashes
    if desired_mcp or "mcp_servers" in config:
        merged["mcp_servers"] = mcp
    if desired_hooks or "hooks" in config:
        merged["hooks"] = hooks
    manifest = {"schema_version": 1, "mcp_servers": next_mcp, "hooks": next_hooks}
    return merged, manifest


def _directory_fd(path: Path, *, create=False, created=None):
    """各祖先を openat(O_NOFOLLOW) で固定する。親リンクの競合も辿らない。"""
    path = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(path.anchor, flags)
    current = Path(path.anchor)
    try:
        for part in path.parts[1:]:
            current = current / part
            try:
                next_fd = os.open(part, flags, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=fd)
                if created is not None:
                    created.append(current)
                next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _directory_state(path: Path):
    _plain_path(path)
    try:
        fd = _directory_fd(path)
    except FileNotFoundError:
        return None
    try:
        info = os.fstat(fd)
        return info.st_dev, info.st_ino
    finally:
        os.close(fd)


def _check_directories(directories):
    for path, expected in directories.items():
        if _directory_state(path) != expected:
            raise IntegrationError("対象ディレクトリの事前状態が変化しました（CAS）")


def _state(path: Path):
    path = _plain_path(path)
    try:
        parent_fd = _directory_fd(path.parent)
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
    except FileNotFoundError:
        return None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise IntegrationError("対象はリンクでない通常ファイルが必須です")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
        after = os.fstat(fd)
        fields = lambda st: (st.st_mode & 0o777, st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
        if fields(before) != fields(after):
            raise IntegrationError("読取り中にファイルが変更されました（CAS）")
        return data, fields(after)
    finally:
        os.close(fd)


class Plan:
    """計画の repr/log に設定値を含めない。読み取ったバイト列で CAS する。"""
    def __init__(self, home):
        self.home = home
        self.states = {}
        self.directories = {}
        self.configs = []
        self.files = {}
        self.manifests: set[Path] = set()
        self.target_count = 0
        self.script_source: Path | None = None
        self.script_names: set[str] = set()

    def watch(self, path):
        if path not in self.states:
            for parent in reversed(path.parents):
                if parent not in self.directories:
                    state = _directory_state(parent)
                    if state is not None:
                        self.directories[parent] = state
            self.states[path] = _state(path)
        return self.states[path]

    def watch_directory(self, path):
        self.directories[path] = _directory_state(path)

    def unchanged(self):
        _check_directories(self.directories)
        if self.script_source is not None and set(_source_scripts(self.script_source)) != self.script_names:
            raise IntegrationError("配布 script の一覧が変更されました（CAS）")
        for path, state in self.states.items():
            if _state(path) != state:
                raise IntegrationError("事前状態が外部で変更されました（CAS）")


def _infrastructure(home: Path):
    local = _plain_path(home / "local")
    if local.exists() and not local.is_dir():
        raise IntegrationError("local/ はディレクトリが必須です")
    lock = _plain_path(local / "harness-integration.lock")
    if lock.exists():
        _regular_file(lock)
    if local.exists():
        fd = _directory_fd(local)
        try:
            if any(name.startswith(".harness-integration-") for name in os.listdir(fd)):
                raise IntegrationError("未完了 transaction が local に残っています。"
                                       "保護バックアップを確認するまで再適用しません。")
        finally:
            os.close(fd)


def _plan(source: Path, home: Path, env_file: Path) -> Plan:
    _infrastructure(home)
    validate_source(source)
    plan = Plan(home)
    for path in (source / "mcp.json", source / "hooks.json", source / "profiles.txt", env_file):
        plan.watch(path)
    scripts = {}
    for relative in _source_scripts(source):
        state = plan.watch(source / "agent-hooks" / relative)
        if state is None:
            raise IntegrationError("配布 script が読取り中に消えました（CAS）")
        scripts[relative] = state[0]
    plan.script_source = source
    plan.script_names = set(scripts)
    env = _environment(env_file, home)
    desired_mcp = _expanded(_read_json(source / "mcp.json")["mcpServers"], env)
    hooks_source = _read_json(source / "hooks.json")["hooks"]
    desired_hooks = _expanded(hooks_source, env)
    for event, blocks in hooks_source.items():
        for index, block in enumerate(blocks):
            desired_hooks[_replace(event, env)][index]["command"] = _command(block["command"], env)
    _mcp(desired_mcp)
    _hooks(desired_hooks)
    targets = [home]
    for name in _profile_names(source, env):
        path = _plain_path(home / "profiles" / name)
        plan.watch_directory(path)
        if path.exists():
            if not path.is_dir():
                raise IntegrationError("対象プロファイルがディレクトリではありません")
            targets.append(path)
    for target in targets:
        config_path = target / "config.yaml"
        plan.watch(config_path)
        config = _read_yaml(config_path)
        manifest_path = target / "local" / "harness-integration.json"
        plan.manifests.add(manifest_path)
        manifest_state = plan.watch(manifest_path)
        old = _manifest(manifest_path, root=target == home)
        merged, manifest = _merge_config(config, desired_mcp, desired_hooks, old)
        if target == home:
            managed = dict(old["scripts"])
            for relative, digest in managed.items():
                state = plan.watch(home / relative)
                if state is None or _hash(state[0]) != digest:
                    raise IntegrationError("管理 script が利用者により変更/消去されています（競合）")
            next_scripts = {}
            destinations = set()
            for relative, data in scripts.items():
                source_mode = plan.states[source / "agent-hooks" / relative][1][0]
                relative = "agent-hooks/" + _replace(relative, env)
                _relative(relative)
                if any(relative == other or relative.startswith(other + "/")
                       or other.startswith(relative + "/") for other in destinations):
                    raise IntegrationError("置換後の script パスが重複/親子競合しています")
                destinations.add(relative)
                try:
                    text = data.decode("utf-8")
                except UnicodeError:
                    pass  # バイナリアセットは文字列置換せずバイト列のまま扱う。
                else:
                    data = _replace(text, env).encode("utf-8")
                path = home / relative
                state = plan.watch(path)
                if relative in managed or state is None:
                    next_scripts[relative] = _hash(data)
                    if state is None or state[0] != data:
                        mode = 0o600 | (source_mode & 0o100) if state is None else state[1][0]
                        plan.files[path] = (data, mode)
                elif state[0] != data:
                    raise IntegrationError("既存の未管理 script の内容が異なります（競合）")
            for relative in managed.keys() - destinations:
                plan.files[home / relative] = (None, 0o600)
            manifest["scripts"] = next_scripts
        if not _same(config, merged):
            plan.configs.append((config_path, config, merged))
        if manifest_state is None or not _same(old, manifest):
            plan.files[manifest_path] = (_json_bytes(manifest), 0o600)
    plan.target_count = len(targets)
    plan.unchanged()
    return plan


def _private_dir(path: Path):
    _plain_path(path)
    fd = _directory_fd(path, create=True)
    try:
        os.fchmod(fd, 0o700)
    finally:
        os.close(fd)


def _write_private(path: Path, data: bytes):
    parent_fd = _directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def _cli_set(stage: Path, user_home: Path, key: str, value):
    import shutil
    import subprocess
    executable = shutil.which("hermes")
    if not executable:
        raise IntegrationError("hermes CLI が見つかりません")
    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(user_home),
           "HERMES_HOME": str(stage), "HERMES_PROFILE": "default",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
           "XDG_CONFIG_HOME": str(user_home / ".config"),
           "XDG_CACHE_HOME": str(user_home / ".cache"), "TMPDIR": str(user_home)}
    try:
        # 負荷の高い環境（スワップ逼迫等）でも CLI 起動が完了できるよう予算は広め。
        # 成否の検証は後に RAW 設定の完全一致で行うため、緩めても検証強度は変わらない。
        result = subprocess.run([executable, "config", "set", "--force", key, _json_bytes(value).decode("utf-8")],
                                env=env, cwd=user_home, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    except (OSError, subprocess.SubprocessError):
        raise IntegrationError("隔離 Hermes config set が失敗しました（出力非表示）") from None
    if result.returncode:
        raise IntegrationError("隔離 Hermes config set が失敗しました（出力非表示）")


def _make_parents(path: Path, created: list[Path]):
    _plain_path(path)
    fd = _directory_fd(path, create=True, created=created)
    os.close(fd)


def _publish(artifact: Path | None, path: Path):
    _plain_path(path)
    parent_fd = _directory_fd(path.parent)
    try:
        if artifact is None:
            os.unlink(path.name, dir_fd=parent_fd)
        else:
            source_fd = _directory_fd(artifact.parent)
            try:
                os.replace(artifact.name, path.name, src_dir_fd=source_fd, dst_dir_fd=parent_fd)
            finally:
                os.close(source_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _check_states(states):
    for path, state in states.items():
        if _state(path) != state:
            raise IntegrationError("事前状態が外部で変更されました（CAS）")


def _rollback(committed, originals, backups, created):
    conflicts = []
    for path, installed in reversed(committed):
        try:
            current = _state(path)
            original = originals[path]
            if current == original:
                continue
            if installed is False or current != installed:
                conflicts.append(path)
                continue
            if original is None:
                _publish(None, path)
            else:
                backup = backups[path]
                os.chmod(backup, original[1][0])
                _publish(backup, path)
                os.utime(path, ns=(original[1][3], original[1][3]), follow_symlinks=False)
                restored = _state(path)
                if restored is None or restored[0] != original[0]:
                    conflicts.append(path)
        except (OSError, IntegrationError):
            conflicts.append(path)
    for directory in reversed(created):
        try:
            parent_fd = _directory_fd(directory.parent)
            try:
                os.rmdir(directory.name, dir_fd=parent_fd)
            finally:
                os.close(parent_fd)
        except OSError:
            pass  # 外部の追加物・非空ディレクトリを消さない。
    if conflicts:
        raise IntegrationError("rollback で外部変更または復元障害を検出しました。"
                               "該当ファイルを上書きせず local の保護バックアップを保持しました。")


def _apply(plan: Plan):
    import fcntl
    import shutil
    import tempfile
    plan.unchanged()
    if not plan.configs and not plan.files:
        return
    local = plan.home / "local"
    _private_dir(local)
    if local not in plan.directories:
        plan.directories[local] = _directory_state(local)
    lock_path = _plain_path(local / "harness-integration.lock")
    local_fd = _directory_fd(local)
    try:
        lock = os.open(lock_path.name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600,
                       dir_fd=local_fd)
    finally:
        os.close(local_fd)
    stage, retain = None, False
    committed, created, backups = [], [], {}
    originals = dict(plan.states)
    try:
        if not stat.S_ISREG(os.fstat(lock).st_mode) or os.fstat(lock).st_nlink != 1:
            raise IntegrationError("ロックファイルが不正です")
        os.fchmod(lock, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise IntegrationError("他の install が設定を更新中です（lock）") from None
        _infrastructure(plan.home)
        plan.unchanged()
        stage = Path(tempfile.mkdtemp(prefix=".harness-integration-", dir=local))
        _private_dir(stage / "backups")
        _private_dir(stage / "stage")
        updates = dict(plan.files)
        # 実 CLI の隔離ランタイム準備はデータルート単位で重い。全対象で 1 つの
        # データルートを順に使い回し、target ごとの RAW 検証は変えない。
        cli_home = stage / "stage" / "cli"
        user_home = cli_home / "user-home"
        _private_dir(user_home)

        def _stage_raw(name: str, data: bytes):
            # 共有ルートへの 2 回目以降の書込みのため、一時名→atomic 置換で上書きする。
            temporary = cli_home / f".raw-{os.getpid()}-{name}"
            _write_private(temporary, data)
            parent_fd = _directory_fd(cli_home)
            try:
                os.replace(temporary.name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            finally:
                os.close(parent_fd)

        for index, (path, original, expected) in enumerate(plan.configs):
            _stage_raw("config.yaml", plan.states[path][0])
            _stage_raw(".env", b"")
            for key in ("mcp_servers", "hooks"):
                if not _same(original.get(key, {}), expected.get(key, {})):
                    _cli_set(cli_home, user_home, key, expected.get(key, {}))
            stage_state = _state(cli_home / "config.yaml")
            actual = _read_yaml(cli_home / "config.yaml")
            if not _same(actual, expected):
                raise IntegrationError("CLI 更新後の RAW 設定が計画と一致しません（対象外の値も検査）")
            if stage_state is None or _state(cli_home / "config.yaml") != stage_state:
                raise IntegrationError("CLI ステージが検証中に変更されました（CAS）")
            updates[path] = (stage_state[0], 0o600)
        prepared, journal = [], []
        for index, (path, (data, mode)) in enumerate(updates.items()):
            state = plan.states[path]
            if state is not None:
                backup = stage / "backups" / str(index)
                _write_private(backup, state[0])
                backups[path] = backup
            artifact = None
            if data is not None:
                artifact = stage / "stage" / f"artifact-{index}"
                _write_private(artifact, data)
            prepared.append((path, artifact, mode))
            journal.append({"path": str(path.relative_to(plan.home)),
                            "backup": str(index) if state is not None else None,
                            "before_hash": _hash(state[0]) if state is not None else None,
                            "after_hash": _hash(data) if data is not None else None})
        _write_private(stage / "transaction.json", _json_bytes({"schema_version": 1, "files": journal}))
        plan.unchanged()
        expected_states = dict(plan.states)
        for path, artifact, mode in prepared:
            if _state(path) != plan.states[path]:
                raise IntegrationError("atomic 配置直前に外部変更を検出しました（CAS）")
            _make_parents(path.parent, created)
            for directory in created:
                if directory not in plan.directories:
                    plan.directories[directory] = _directory_state(directory)
            if path in plan.manifests:
                _private_dir(path.parent)
            # False は「まだ配置完了を確認していない」。外部変更と区別して復元する。
            committed.append((path, False))
            if artifact is None:
                _publish(None, path)
            else:
                os.chmod(artifact, mode)
                _publish(artifact, path)
            current = _state(path)
            if (None if current is None else current[0]) != updates[path][0]:
                raise IntegrationError("atomic 配置直後に外部変更を検出しました（CAS）")
            committed[-1] = (path, current)
            expected_states[path] = current
        _check_directories(plan.directories)
        _check_states(expected_states)
    except BaseException:
        try:
            _rollback(committed, originals, backups, created)
        except IntegrationError:
            retain = True
            raise
        raise
    finally:
        try:
            if stage is not None and not retain:
                parent_fd = _directory_fd(stage.parent)
                try:
                    shutil.rmtree(stage.name, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
        finally:
            os.close(lock)


def _seed_profile(source: Path, home: Path, env_file: Path, name: str):
    """直前に clone された設定の所有権だけを渡す。scripts の所有権は root 専有。"""
    import re
    _infrastructure(home)
    validate_source(source)
    plan = Plan(home)
    for path in (source / "profiles.txt", env_file):
        plan.watch(path)
    env = _environment(env_file, home)
    if (not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name)
            or name not in _profile_names(source, env)):
        raise IntegrationError("seed-profile は profiles.txt の正規化済み名称が必須です")
    root_manifest_path = home / "local" / "harness-integration.json"
    _regular_file(root_manifest_path)
    child = _plain_path(home / "profiles" / name)
    child_manifest_path = child / "local" / "harness-integration.json"
    plan.manifests.add(child_manifest_path)
    for path in (root_manifest_path, home / "config.yaml", child / "config.yaml"):
        plan.watch(path)
    if plan.watch(child_manifest_path) is not None:
        raise IntegrationError("seed-profile の管理情報が既に存在します（上書き拒否）")
    manifest = _manifest(root_manifest_path, root=True)
    _assert_owned(_read_yaml(home / "config.yaml"), manifest)
    _assert_owned(_read_yaml(child / "config.yaml"), manifest)
    seeded = {"schema_version": 1, "mcp_servers": manifest["mcp_servers"], "hooks": manifest["hooks"]}
    plan.files[child_manifest_path] = (_json_bytes(seeded), 0o600)
    plan.target_count = 1
    plan.unchanged()
    _apply(plan)


def main(argv=None) -> int:
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--env-file", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--seed-profile")
    args = parser.parse_args(argv)
    try:
        source, home = _plain_path(args.source), _plain_path(args.home)
        if args.seed_profile is not None:
            _seed_profile(source, home, args.env_file, args.seed_profile)
            print("[seed-profile] clone 元と一致する設定所有情報だけを記録しました。")
            return 0
        plan = _plan(source, home, args.env_file)
        if args.dry_run:
            print(f"[dry-run] 設定対象 {plan.target_count} 件（default を含む）。"
                  f"設定変更 {len(plan.configs)} 件、script/管理情報変更 {len(plan.files)} 件。書込みなし。")
        elif args.apply:
            _apply(plan)
            print(f"[apply] 設定対象 {plan.target_count} 件の部分移行を検証しました。")
        else:
            scripts = [path for path in plan.files if path not in plan.manifests]
            if plan.configs or scripts:
                raise IntegrationError("期待する MCP/hooks/scripts が未反映です")
            plan.unchanged()
            print(f"[verify] 設定対象 {plan.target_count} 件と共有 scripts の一致を確認しました。")

        return 0
    except IntegrationError as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 1
    except OSError:
        print("ERROR: 設定部分移行のファイル操作に失敗しました（詳細非表示）。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
