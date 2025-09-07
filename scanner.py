import asyncio
import socket
import json
from datetime import datetime
from mcstatus import JavaServer
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

async def scan_port(ip, port, timeout=1.0, retries=2):
    for attempt in range(retries):
        try:
            server = JavaServer(ip, port)
            status = await asyncio.wait_for(server.async_status(), timeout=timeout)

            motd = getattr(status.description, "to_minecraft", lambda: str(status.description))()
            version = status.version.name
            protocol = status.version.protocol
            players_online = status.players.online
            players_max = status.players.max
            players_sample = [p.name for p in (status.players.sample or [])]

            # Forge detection
            forge = status.forge_data is not None
            mods = []
            if forge and hasattr(status.forge_data, "mods"):
                mods = [f"{m.name} {m.marker}" for m in status.forge_data.mods]

            plugins = status.software.plugins if getattr(status, "software", None) else []

            core = "Vanilla"
            if "Paper" in version:
                core = "Paper"
            elif "Spigot" in version:
                core = "Spigot"
            elif "Forge" in version:
                core = "Forge"
            elif "Fabric" in version:
                core = "Fabric"

            favicon = bool(getattr(status, "icon", None))
            ping = status.latency

            # Красивый вывод в консоль
            table = Table(title=f"Сервер найден: {ip}:{port}", box=box.ROUNDED, style="bold white")
            table.add_column("Параметр", style="cyan", no_wrap=True)
            table.add_column("Значение", style="magenta")

            table.add_row("MOTD", f"[blue]{motd}[/blue]")
            table.add_row("Версия", f"{version} (протокол {protocol})")
            table.add_row("Игроки", f"{players_online}/{players_max} {players_sample}")
            table.add_row("Forge", "[green]✔[/green]" if forge else "[red]✘[/red]")
            table.add_row("Core", f"[yellow]{core}[/yellow]")
            table.add_row("Favicon", "[green]Есть[/green]" if favicon else "[red]Нет[/red]")
            table.add_row("Ping", f"[cyan]{ping} ms[/cyan]")

            console.print(table)

            return {
                "ip": ip,
                "port": port,
                "motd": motd,
                "version": version,
                "protocol": protocol,
                "players_online": players_online,
                "players_max": players_max,
                "players_sample": players_sample,
                "forge": forge,
                "mods": mods,
                "plugins": plugins,
                "core": core,
                "favicon": favicon,
                "ping": ping
            }

        except (asyncio.TimeoutError, socket.timeout, ConnectionRefusedError, OSError):
            continue
        except Exception as e:
            console.print(f"[red][!][/red] Ошибка на {ip}:{port} → {e}")
            continue

    return None

async def scan_ports(ip, start_port=25565, end_port=25600, timeout=1.0, concurrency=100):
    tasks = []
    sem = asyncio.Semaphore(concurrency)

    async def sem_task(port):
        async with sem:
            return await scan_port(ip, port, timeout)

    for port in range(start_port, end_port + 1):
        tasks.append(asyncio.create_task(sem_task(port)))

    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]

def save_results(results, filename="results.json"):
    data = {
        "scanned_at": datetime.utcnow().isoformat(),
        "servers_found": len(results),
        "results": results
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    console.print(f"[bold green]✔ Результаты сохранены в {filename}[/bold green]")

def get_user_input():
    console.print("[bold cyan]Введите параметры сканирования (нажмите Enter для значений по умолчанию):[/bold cyan]")
    
    ip = input("IP-адрес (по умолчанию 147.185.221.31): ").strip() or "147.185.221.31"
    
    while True:
        try:
            start_port_input = input("Начальный порт (по умолчанию 36000): ").strip() or "36000"
            start_port = int(start_port_input)
            if start_port < 1 or start_port > 65535:
                raise ValueError("Порт должен быть от 1 до 65535")
            break
        except ValueError as e:
            console.print(f"[red]Ошибка: {e}. Попробуйте снова.[/red]")

    while True:
        try:
            end_port_input = input("Конечный порт (по умолчанию 50000): ").strip() or "50000"
            end_port = int(end_port_input)
            if end_port < start_port or end_port > 65535:
                raise ValueError("Конечный порт должен быть больше начального и до 65535")
            break
        except ValueError as e:
            console.print(f"[red]Ошибка: {e}. Попробуйте снова.[/red]")

    return ip, start_port, end_port

if __name__ == "__main__":
    ip, start_port, end_port = get_user_input()
    console.print(f"[bold green]Сканирование {ip} с портов {start_port} до {end_port}...[/bold green]")
    results = asyncio.run(scan_ports(ip, start_port, end_port, timeout=0.7, concurrency=50))

    if results:
        table = Table(title="Итоговый список серверов", box=box.MINIMAL_DOUBLE_HEAD)
        table.add_column("IP:Port", style="cyan")
        table.add_column("MOTD", style="blue")
        table.add_column("Версия", style="magenta")
        table.add_column("Игроки", style="green")
        table.add_column("Ping", style="yellow")

        for r in results:
            table.add_row(
                f"{r['ip']}:{r['port']}",
                r["motd"][:30] + ("..." if len(r["motd"]) > 30 else ""),
                r["version"],
                f"{r['players_online']}/{r['players_max']}",
                f"{r['ping']} ms"
            )

        console.print(table)

    save_results(results)