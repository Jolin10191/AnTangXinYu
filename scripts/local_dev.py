"""本机联调入口：固定本机数据库，检查目标后端，不回退到线上。"""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, build_opener

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_HOST = "82.157.48.200"


def fail(message: str) -> None:
    raise SystemExit(message)


def local_api_url() -> str:
    host = os.environ.get("ANTANG_DEV_HOST")
    if not host:
        # UDP connect 仅用于选择本机出站网卡，不发送数据。
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect(("1.1.1.1", 80))
            host = connection.getsockname()[0]
    return validate_api_url(f"http://{host}:{os.environ.get('ANTANG_DEV_API_PORT', '8000')}")


def validate_api_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        fail("请提供完整后端地址，例如 http://192.168.1.100:8000，不包含 /api/v1。")
    if parsed.hostname == PRODUCTION_HOST:
        fail("本地开发和审核预览不能连接线上后端，请填写本机局域网地址或本机隧道地址。")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if parsed.hostname == "localhost" or (address is not None and address.is_loopback):
        fail("手机的 localhost 指向手机自身，请使用电脑的局域网地址。")
    return value


def check_api(api_url: str) -> None:
    try:
        # 本地联调不能经过系统的联网搜索/代理出口。
        with build_opener(ProxyHandler({})).open(f"{api_url}/openapi.json", timeout=8) as response:
            schema = json.load(response)
    except (URLError, OSError, ValueError) as error:
        fail(f"无法访问本地后端 {api_url}。请先运行 bash scripts/dev-api，并检查网络。\n{type(error).__name__}")
    properties = schema.get("components", {}).get("schemas", {}).get("UserResponse", {}).get("properties", {})
    if "role" not in properties or "/api/v1/patients" not in schema.get("paths", {}):
        fail("目标后端尚未运行当前角色授权版本。请检查正在运行的源码目录。")


def api_environment(base_only: bool = False) -> dict[str, str]:
    if not (ROOT / ".env").is_file() or not (ROOT / "api/.env").is_file():
        fail("缺少本机配置，请准备项目根目录 .env 和 api/.env，参考 docs/development.md。")
    database = dotenv_values(ROOT / ".env")
    api = dotenv_values(ROOT / "api/.env")
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    missing = [name for name in required if not database.get(name)]
    if missing:
        fail("本机数据库配置缺失：" + "、".join(missing))
    ai_missing = [name for name in ("HACHIMI_API_KEY", "TAVILY_API_KEY") if not api.get(name)]
    if not api.get("HACHIMI_BASE_URL") or "example.com" in (api.get("HACHIMI_BASE_URL") or ""):
        ai_missing.append("HACHIMI_BASE_URL")
    if ai_missing and not base_only:
        fail("本地完整后端尚缺真实配置：" + "、".join(ai_missing) + "。请填写 api/.env；不会使用假密钥或自动连接线上后端。")
    environment = dict(os.environ)
    environment.update({key: value for key, value in api.items() if value is not None})
    environment["LOCAL_BASIC_MODE"] = "true" if base_only else "false"
    user = quote(database["POSTGRES_USER"] or "", safe="")
    password = quote(database["POSTGRES_PASSWORD"] or "", safe="")
    name = quote(database["POSTGRES_DB"] or "", safe="")
    port = os.environ.get("ANTANG_DEV_DATABASE_PORT", "55432")
    environment["DATABASE_URL"] = f"postgresql+psycopg://{user}:{password}@127.0.0.1:{port}/{name}"
    return environment


def start_database() -> None:
    subprocess.run([
        "docker", "compose", "-p", "antang-local", "-f", "compose.local.yaml",
        "up", "--detach", "--wait", "postgres",
    ], cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="安糖本机开发")
    parser.add_argument("command", choices=("api", "database", "mobile", "prepare-preview", "role"))
    parser.add_argument("--api-url")
    parser.add_argument("--metro-url", help="转发本机 Metro 的 HTTPS 隧道地址")
    parser.add_argument("--tunnel", action="store_true", help="使用 dev-tunnel 记录的当前本机后端隧道")
    parser.add_argument("--base-only", action="store_true", help="显式启用无需模型密钥的基础联调，智能聊天不可用")
    parser.add_argument("--username")
    parser.add_argument("--role", choices=("patient", "clinician", "researcher"))
    parser.add_argument("--actor")
    args = parser.parse_args()
    if args.command == "database":
        start_database()
        return
    if args.command == "api":
        environment = api_environment(args.base_only)
        start_database()
        api_dir = ROOT / "api"
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=api_dir, env=environment, check=True)
        os.chdir(api_dir)
        if args.base_only:
            print("本地基础联调：登录、档案、设备数据和患者授权可用；智能聊天与主动关怀未启用。", flush=True)
        print("本地后端：http://0.0.0.0:8000；保存 api/src 下的 Python 文件后自动重载。", flush=True)
        os.execvpe(sys.executable, [sys.executable, "-m", "uvicorn", "antang_api.main:app",
                                  "--host", "0.0.0.0", "--port", os.environ.get("ANTANG_DEV_API_PORT", "8000"),
                                  "--reload", "--reload-dir", "src", "--no-access-log"], environment)
    if args.command == "role":
        if not args.username or not args.role or not args.actor:
            parser.error("设置本地角色需提供 --username、--role 和 --actor")
        subprocess.run([sys.executable, "-m", "antang_api.manage_roles", args.username, args.role,
                        "--actor", args.actor], cwd=ROOT / "api", env=api_environment(True), check=True)
        return
    if args.tunnel:
        if args.api_url:
            parser.error("--tunnel 与 --api-url 不能同时指定")
        state_path = ROOT / "artifacts/local-tunnel.json"
        if not state_path.is_file():
            fail("请先运行 bash scripts/dev-tunnel，再生成隧道审核包。")
        args.api_url = json.loads(state_path.read_text(encoding="utf-8"))["apiUrl"]
    api_url = validate_api_url(args.api_url) if args.api_url else local_api_url()
    check_api(api_url)
    print(f"连接本机后端：{api_url}", flush=True)
    if args.command == "prepare-preview":
        target = ROOT / "apps/mobile/local-preview.json"
        target.write_text(json.dumps({"apiUrl": api_url}, indent=2) + "\n", encoding="utf-8")
        print("已记录本次预览地址；电脑后端及所选隧道须保持运行。")
        return
    environment = dict(os.environ)
    environment["EXPO_PUBLIC_API_URL"] = api_url
    if args.metro_url:
        metro_url = validate_api_url(args.metro_url)
        if urlsplit(metro_url).scheme != "https":
            parser.error("Metro 公网隧道必须使用 HTTPS")
        environment["EXPO_PACKAGER_PROXY_URL"] = metro_url
        environment["REACT_NATIVE_PACKAGER_HOSTNAME"] = urlsplit(metro_url).hostname or ""
    else:
        environment.pop("EXPO_PACKAGER_PROXY_URL", None)
        environment["REACT_NATIVE_PACKAGER_HOSTNAME"] = urlsplit(local_api_url()).hostname or ""
    os.chdir(ROOT / "apps/mobile")
    print("使用开发 APK 扫描接下来的二维码。保存页面代码后手机将自动刷新。", flush=True)
    os.execvpe("npx", ["npx", "expo", "start", "--dev-client", "--lan", "--max-workers", "2"], environment)


if __name__ == "__main__":
    main()
