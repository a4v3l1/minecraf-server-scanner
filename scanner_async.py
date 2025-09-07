import asyncio
import socket
import json
from datetime import datetime
import logging
from mcstatus import JavaServer

# Настройка логирования
logging.basicConfig(
    filename="scanner.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

async def scan_port_async(ip, port, timeout=2.0, retries=2):
    for attempt in range(retries):
        try:
            server = JavaServer(ip, port)
            async with asyncio.timeout(timeout):
                status = await server.async_status()

            # Получаем favicon, если async_status не вернул
            favicon = status.icon
            if not favicon:
                try:
                    sync_status = server.status(timeout=timeout)
                    favicon = sync_status.icon
                    logging.info(f"Fallback to sync status for favicon on {ip}:{port}")
                except Exception as e:
                    logging.warning(f"Sync favicon fetch failed for {ip}:{port}: {e}")

            motd = status.description.to_minecraft() if hasattr(status.description, 'to_minecraft') else str(status.description)
            version = status.version.name
            protocol = status.version.protocol
            players_online = status.players.online
            players_max = status.players.max
            players_sample = [p.name for p in (status.players.sample or [])]
            forge = status.forge_data is not None
            mods = [f"{m.name} {m.marker}" for m in status.forge_data.mods] if forge and hasattr(status.forge_data, "mods") else []
            plugins = status.software.plugins if hasattr(status, "software") and status.software.plugins else []
            core = "Vanilla"
            if "Paper" in version:
                core = "Paper"
            elif "Spigot" in version:
                core = "Spigot"
            elif "Forge" in version:
                core = "Forge"
            elif "Fabric" in version:
                core = "Fabric"
            ping = status.latency

            logging.info(f"Scanned {ip}:{port} - Favicon: {'Present' if favicon else 'None'}")
            print(f"Raw favicon for {ip}:{port}: {favicon[:50] if favicon else 'None'}...")

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

        except asyncio.TimeoutError:
            logging.warning(f"Attempt {attempt + 1} timeout for {ip}:{port}")
            continue
        except (socket.gaierror, ConnectionRefusedError, OSError) as e:
            logging.warning(f"Attempt {attempt + 1} failed for {ip}:{port}: {e}")
            continue
        except Exception as e:
            logging.error(f"Error scanning {ip}:{port}: {e}")
            return None

    logging.warning(f"All {retries} attempts failed for {ip}:{port}")
    return None

async def scan_ports(ip, start_port=25565, end_port=25600, timeout=2.0, concurrency=50, progress_callback=None):
    results = []
    total_ports = end_port - start_port + 1
    semaphore = asyncio.Semaphore(concurrency)  # Ограничение параллельных задач

    async def scan_with_semaphore(port):
        async with semaphore:
            result = await scan_port_async(ip, port, timeout)
            if progress_callback:
                current_progress = (port - start_port + 1) / total_ports * 100
                await progress_callback(current_progress)
            return result

    tasks = [scan_with_semaphore(port) for port in range(start_port, end_port + 1)]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    results = [r for r in results if r is not None]

    logging.info(f"Scan completed: {len(results)} servers found")
    return results

def save_results(results, filename="results.json"):
    data = {
        "scanned_at": datetime.utcnow().isoformat(),
        "servers_found": len(results),
        "results": results
    }
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Results saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving results to {filename}: {e}")