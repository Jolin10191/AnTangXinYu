"""Supervise two temporary HTTPS tunnels and the local Expo development server."""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import quote

from local_dev import ROOT, check_api, fail


def main() -> None:
    executable = shutil.which("cloudflared") or str(Path.home() / ".local/bin/cloudflared")
    if not Path(executable).is_file():
        fail("请先按 docs/local-development.md 安装官方 cloudflared。")
    check_api("http://127.0.0.1:8000")
    with socket.socket() as connection:
        if connection.connect_ex(("127.0.0.1", 8081)) == 0:
            fail("8081 已有 Metro 运行，请先关闭原 dev-mobile，再启动 dev-tunnel。")
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    state_path = output / "local-tunnel.json"
    processes: list[subprocess.Popen] = []

    def tunnel(name: str, port: int) -> str:
        log_path = output / f"local-tunnel-{name}.log"
        with log_path.open("w") as log:
            process = subprocess.Popen([
                executable, "tunnel", "--url", f"http://127.0.0.1:{port}",
                "--protocol", "http2", "--no-autoupdate", "--loglevel", "info",
            ], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        processes.append(process)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                fail(f"{name} 隧道启动失败，查看 {log_path}")
            contents = log_path.read_text()
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", contents)
            if match and "Registered tunnel connection" in contents:
                return match.group(0)
            time.sleep(0.3)
        fail(f"{name} 隧道连接超时，查看 {log_path}")

    try:
        api_url = tunnel("api", 8000)
        metro_url = tunnel("metro", 8081)
        check_api(api_url)
        client_url = "exp+antang://expo-development-client/?url=" + quote(metro_url, safe="")
        state = {"apiUrl": api_url, "metroUrl": metro_url, "devClientUrl": client_url}
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(f"本机后端隧道：{api_url}\n实时开发隧道：{metro_url}\n开发包连接：{client_url}", flush=True)
        print("无需同一 Wi-Fi。保持本终端和本机后端运行；Ctrl+C 关闭本次公网入口。", flush=True)
        process = subprocess.Popen([
            sys.executable, str(ROOT / "scripts/local_dev.py"), "mobile",
            "--api-url", api_url, "--metro-url", metro_url,
        ], start_new_session=True)
        processes.append(process)
        while True:
            for child in processes:
                if child.poll() is not None:
                    fail("隧道或 Metro 已退出；本次联调停止，请检查终端和 artifacts 中的日志。")
            time.sleep(1)
    except KeyboardInterrupt:
        print("正在关闭本次隧道和实时开发服务。", flush=True)
    finally:
        for child in processes:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in processes:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        state_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
