import tkinter as tk
from tkinter import ttk, messagebox, Text
from PIL import Image, ImageTk
import base64
import threading
from io import BytesIO
from datetime import datetime
import json
import os
import logging
import asyncio

from scanner_async import scan_ports  # Асинхронный сканер

# Настройка логирования
logging.basicConfig(
    filename="scanner.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

class ServerScannerGUI:
    def __init__(self, root):
        self.total_ports = 0
        self.root = root
        self.root.title("Minecraft Server Scanner (v1 GUI)")
        # Установка размера окна
        self.root.minsize(800, 600)
        self.root.geometry("1000x700")

        # Цвета для MOTD (hex-коды, совместимые с tkinter)
        self.colors = {
            '0': '#000000', '1': '#0000AA', '2': '#00AA00', '3': '#00AAAA',
            '4': '#AA0000', '5': '#AA00AA', '6': '#FFAA00', '7': '#AAAAAA',
            '8': '#555555', '9': '#5555FF', 'a': '#55FF55', 'b': '#55FFFF',
            'c': '#FF5555', 'd': '#FF55FF', 'e': '#FFFF55', 'f': '#FFFFFF'
        }

        # Тема (светлая/темная)
        self.theme = "light"
        self.bg_color = "#f0f0f0"
        self.details_bg_color = "#ffffff"
        self.card_bg_color = "#e0e0e0"
        self.text_color = "#000000"
        self.progress_value = 0

        # Загрузка избранных серверов (с тегами)
        self.favorites = list({(f['ip'], f['port']): f for f in self.load_favorites()}.values())

        # Основной фрейм с вкладками
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True)

        # Вкладка для основного сканирования
        self.main_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.main_frame, text="Основной поиск")

        # Вкладка для избранных серверов
        self.fav_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.fav_frame, text="Избранное")

        # Вкладка для истории серверов
        self.history_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.history_frame, text="История")

        # Фоновая текстура (если есть)
        self.bg_image = None
        self.bg_label_main = None
        self.bg_label_fav = None
        if os.path.exists("background.png"):
            self.bg_image = tk.PhotoImage(file="background.png")
            self.bg_label_main = tk.Label(self.main_frame, image=self.bg_image)
            self.bg_label_main.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label_main.lower()  # Помещаем фон ниже всех элементов
            self.bg_label_fav = tk.Label(self.fav_frame, image=self.bg_image)
            self.bg_label_fav.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label_fav.lower()  # Помещаем фон ниже всех элементов

        # Верхняя панель (основной поиск)
        frame_top = tk.Frame(self.main_frame, bg=self.bg_color)
        frame_top.pack(pady=10, fill="x")

        tk.Label(frame_top, text="IP:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.entry_ip = tk.Entry(frame_top, width=20, font=("Arial", 12))
        self.entry_ip.pack(side=tk.LEFT, padx=5)
        self.entry_ip.insert(0, "147.185.221.31")

        tk.Label(frame_top, text="Порты:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.entry_ports = tk.Entry(frame_top, width=15, font=("Arial", 12))
        self.entry_ports.pack(side=tk.LEFT, padx=5)
        self.entry_ports.insert(0, "25565-25600")

        self.btn_scan = tk.Button(frame_top, text="Сканировать", command=self.start_scan, image=self.get_icon("scan.png"), compound=tk.LEFT, font=("Arial", 10))
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        # Прогресс-бар с процентами
        self.progress = ttk.Progressbar(frame_top, mode='determinate', maximum=100)
        self.progress.pack(side=tk.LEFT, padx=5)
        self.scan_label = tk.Label(frame_top, text="", font=("Arial", 12), bg=self.bg_color, fg=self.text_color)
        self.scan_label.pack(side=tk.LEFT, padx=5)

        # Кнопка для сохранения результатов
        self.btn_save = tk.Button(frame_top, text="Сохранить результаты", command=self.save_results, state=tk.DISABLED, image=self.get_icon("save.png"), compound=tk.LEFT, font=("Arial", 10))
        self.btn_save.pack(side=tk.LEFT, padx=5)

        # Кнопка для импорта серверов
        self.btn_import = tk.Button(frame_top, text="Импорт серверов", command=self.import_servers, image=self.get_icon("import.png"), compound=tk.LEFT, font=("Arial", 10))
        self.btn_import.pack(side=tk.LEFT, padx=5)

        # Кнопка для массовой проверки избранного
        self.btn_check_favs = tk.Button(frame_top, text="Проверить избранное", command=self.check_favorites, image=self.get_icon("check_favs.png"), compound=tk.LEFT, font=("Arial", 10))
        self.btn_check_favs.pack(side=tk.LEFT, padx=5)

        # Кнопка для переключения темы
        self.btn_theme = tk.Button(frame_top, text="Темная тема", command=self.toggle_theme, image=self.get_icon("theme.png"), compound=tk.LEFT, font=("Arial", 10))
        self.btn_theme.pack(side=tk.LEFT, padx=5)

        # Автопроверка серверов
        self.rescan_active = tk.BooleanVar(value=False)
        self.rescan_check = tk.Checkbutton(frame_top, text="Автопроверка", variable=self.rescan_active, command=self.toggle_rescan, bg=self.bg_color, fg=self.text_color, font=("Arial", 10))
        self.rescan_check.pack(side=tk.LEFT, padx=5)
        tk.Label(frame_top, text="Интервал (мин):", bg=self.bg_color, fg=self.text_color, font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.rescan_interval_var = tk.StringVar(value="5")
        self.rescan_interval_entry = tk.Entry(frame_top, textvariable=self.rescan_interval_var, width=5, font=("Arial", 10))
        self.rescan_interval_entry.pack(side=tk.LEFT, padx=5)
        self.rescan_interval_entry.bind("<KeyRelease>", self.update_rescan_interval)

        # Панель фильтрации и сортировки
        frame_filter = tk.Frame(self.main_frame, bg=self.bg_color)
        frame_filter.pack(pady=5, fill="x")

        tk.Label(frame_filter, text="Фильтр:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.filter_var = tk.StringVar(value="all")
        tk.Radiobutton(frame_filter, text="Все", variable=self.filter_var, value="all", command=self.apply_filter, bg=self.bg_color, fg=self.text_color, font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(frame_filter, text="С игроками", variable=self.filter_var, value="players", command=self.apply_filter, bg=self.bg_color, fg=self.text_color, font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        tk.Label(frame_filter, text="Ядро:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.core_var = tk.StringVar(value="all")
        tk.OptionMenu(frame_filter, self.core_var, "all", "Vanilla", "Paper", "Spigot", "Forge", "Fabric", command=self.apply_filter).pack(side=tk.LEFT, padx=5)

        tk.Label(frame_filter, text="Версия:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.version_var = tk.StringVar()
        self.version_entry = tk.Entry(frame_filter, textvariable=self.version_var, width=10, font=("Arial", 12))
        self.version_entry.pack(side=tk.LEFT, padx=5)
        self.version_entry.insert(0, "")
        self.version_entry.bind("<KeyRelease>", self.apply_filter)

        tk.Label(frame_filter, text="MOTD:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.motd_var = tk.StringVar()
        self.motd_entry = tk.Entry(frame_filter, textvariable=self.motd_var, width=20, font=("Arial", 12))
        self.motd_entry.pack(side=tk.LEFT, padx=5)
        self.motd_entry.bind("<KeyRelease>", self.apply_filter)

        tk.Label(frame_filter, text="Сортировка:", bg=self.bg_color, fg=self.text_color, font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        self.sort_var = tk.StringVar(value="none")
        tk.OptionMenu(frame_filter, self.sort_var, "Без сортировки", "По пингу", "По игрокам", command=self.apply_sort).pack(side=tk.LEFT, padx=5)

        # Статистика сканирования
        self.stats_label = tk.Label(self.main_frame, text="Статистика: 0 серверов, 0 портов, 0 сек", font=("Arial", 12), bg=self.bg_color, fg=self.text_color)
        self.stats_label.pack(pady=5)

        self.status_label = tk.Label(
            self.main_frame,
            text="",
            font=("Arial", 12),
            bg=self.bg_color,
            fg="blue"
        )
        self.status_label.pack(pady=5)

        # Основная рабочая область
        self.main_content = tk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL, bg="#d0d0d0", sashwidth=5, sashrelief="raised")
        self.main_content.pack(fill="both", expand=True)

        # Левая часть: список серверов
        self.server_list_frame = tk.Frame(self.main_content, bg=self.bg_color, bd=2, relief="groove")
        self.main_content.add(self.server_list_frame, width=400)

        self.server_canvas = tk.Canvas(self.server_list_frame, bg=self.bg_color)
        self.server_scrollbar = ttk.Scrollbar(self.server_list_frame, orient="vertical", command=self.server_canvas.yview)
        self.server_list = tk.Frame(self.server_canvas, bg=self.bg_color)

        self.server_list.bind(
            "<Configure>",
            lambda e: self.server_canvas.configure(scrollregion=self.server_canvas.bbox("all"))
        )
        self.server_canvas.create_window((0, 0), window=self.server_list, anchor="nw")
        self.server_canvas.configure(yscrollcommand=self.server_scrollbar.set)
        self.server_canvas.pack(side="left", fill="both", expand=True)
        self.server_scrollbar.pack(side="right", fill="y")

        # Правая часть: подробная информация
        self.details_frame = tk.Frame(self.main_content, bg=self.details_bg_color, bd=2, relief="groove")
        self.main_content.add(self.details_frame, width=400)
        self.details_label = tk.Label(self.details_frame, text="Выберите сервер для просмотра деталей", font=("Arial", 14), bg=self.details_bg_color, fg=self.text_color)
        self.details_label.pack(pady=20)

        # Вкладка избранного
        self.fav_list_frame = tk.Frame(self.fav_frame, bg=self.bg_color, bd=2, relief="groove")
        self.fav_list_frame.pack(fill="both", expand=True)
        self.fav_canvas = tk.Canvas(self.fav_list_frame, bg=self.bg_color)
        self.fav_scrollbar = ttk.Scrollbar(self.fav_list_frame, orient="vertical", command=self.fav_canvas.yview)
        self.fav_list = tk.Frame(self.fav_canvas, bg=self.bg_color)

        self.fav_list.bind(
            "<Configure>",
            lambda e: self.fav_canvas.configure(scrollregion=self.fav_canvas.bbox("all"))
        )
        self.fav_canvas.create_window((0, 0), window=self.fav_list, anchor="nw")
        self.fav_canvas.configure(yscrollcommand=self.fav_scrollbar.set)
        self.fav_canvas.pack(side="left", fill="both", expand=True)
        self.fav_scrollbar.pack(side="right", fill="y")

        # История сканов (список)
        self.history_listbox = tk.Listbox(self.history_frame, font=("Arial", 12))
        self.history_listbox.pack(fill="both", expand=True, padx=10, pady=10)

        # Кнопка для загрузки выбранного скана
        self.btn_load_history = tk.Button(
            self.history_frame, text="Загрузить",
            command=self.load_selected_history,
            font=("Arial", 12)
        )
        self.btn_load_history.pack(pady=5)

        self.btn_rescan_history = tk.Button(
            self.history_frame, text="Пересканировать",
            command=self.rescan_selected_history,
            font=("Arial", 12)
        )
        self.btn_rescan_history.pack(pady=5)

        # Загружаем историю
        self.history = self.load_history()
        self.show_history()

        self.cards = []
        self.results = []
        self.filtered_results = []
        self.fav_cards = []
        self.default_icon = None
        self.load_default_icon()

        # Таймер для повторного сканирования (по умолчанию выключен)
        self.rescan_interval = 300000  # 5 минут в миллисекундах

    def load_default_icon(self):
        try:
            if os.path.exists("default_icon.png"):
                image = Image.open("default_icon.png").resize((64, 64))
                self.default_icon = ImageTk.PhotoImage(image)
            else:
                self.default_icon = None
        except Exception as e:
            logging.error(f"Ошибка загрузки default_icon.png: {e}")
            self.default_icon = None

    def get_icon(self, filename):
        try:
            if os.path.exists(filename):
                image = Image.open(filename).resize((16, 16))
                return ImageTk.PhotoImage(image)
            return None
        except Exception:
            return None

    def load_favorites(self):
        try:
            with open("favorites.json", "r", encoding="utf-8") as f:
                favorites = json.load(f)
                for fav in favorites:
                    fav.setdefault("tags", [])  # Добавляем пустой список тегов, если его нет
                return favorites
        except FileNotFoundError:
            return []

    def save_favorites(self):
        try:
            with open("favorites.json", "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить избранное: {e}")
            logging.error(f"Ошибка сохранения избранного: {e}")

    def save_history(self, ip, port_range, results):
        try:
            entry = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ip": ip,
                "ports": port_range,
                "servers": len(results),
                "results": results
            }
            self.history.append(entry)
            with open("history.json", "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Ошибка сохранения истории: {e}")

    def load_history(self):
        try:
            with open("history.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []
        except Exception as e:
            logging.error(f"Ошибка загрузки истории: {e}")
            return []

    def show_history(self):
        self.history_listbox.delete(0, tk.END)
        for entry in self.history:
            self.history_listbox.insert(
                tk.END,
                f"{entry['time']} | {entry['ip']}:{entry['ports']} | {entry['servers']} серверов"
            )

    def load_selected_history(self):
        idx = self.history_listbox.curselection()
        if not idx:
            messagebox.showinfo("Инфо", "Выберите запись из истории")
            return
        entry = self.history[idx[0]]
        self.results = entry["results"]
        self.filtered_results = self.results.copy()
        self.show_results(self.filtered_results)

    def toggle_theme(self):
        if self.theme == "light":
            self.theme = "dark"
            self.bg_color = "#2e2e2e"
            self.details_bg_color = "#3c3c3c"
            self.card_bg_color = "#4a4a4a"
            self.text_color = "#ffffff"
            self.btn_theme.config(text="Светлая тема")
        else:
            self.theme = "light"
            self.bg_color = "#f0f0f0"
            self.details_bg_color = "#ffffff"
            self.card_bg_color = "#e0e0e0"
            self.text_color = "#000000"
            self.btn_theme.config(text="Темная тема")
        self.update_theme()

    def update_theme(self):
        self.main_frame.config(bg=self.bg_color)
        self.fav_frame.config(bg=self.bg_color)
        self.server_list_frame.config(bg=self.bg_color)
        self.server_canvas.config(bg=self.bg_color)
        self.server_list.config(bg=self.bg_color)
        self.details_frame.config(bg=self.details_bg_color)
        self.fav_list_frame.config(bg=self.bg_color)
        self.fav_canvas.config(bg=self.bg_color)
        self.fav_list.config(bg=self.bg_color)
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, (tk.Label, tk.Radiobutton, tk.Checkbutton)):
                widget.config(bg=self.bg_color, fg=self.text_color)
        for widget in self.fav_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.config(bg=self.bg_color, fg=self.text_color)
        self.stats_label.config(bg=self.bg_color, fg=self.text_color)
        self.details_label.config(bg=self.details_bg_color, fg=self.text_color)
        if self.bg_label_main:
            self.bg_label_main.config(bg=self.bg_color)
            self.bg_label_main.lower()
        if self.bg_label_fav:
            self.bg_label_fav.config(bg=self.bg_color)
            self.bg_label_fav.lower()
        self.rescan_check.config(bg=self.bg_color, fg=self.text_color)
        self.rescan_interval_entry.config(bg=self.bg_color, fg=self.text_color)
        self.show_results(self.filtered_results)
        self.show_favorites([r for r in self.results + self.filtered_results if (r['ip'], r['port']) in {(f['ip'], f['port']) for f in self.favorites}])

    def update_scan_label(self, state):
        if state:
            self.scan_label.config(text=f"Сканирование ({self.progress_value:.1f}%)")
            self.root.after(100, lambda: self.update_scan_label(state and self.btn_scan['state'] == tk.DISABLED))
        else:
            self.scan_label.config(text="")

    def toggle_rescan(self):
        if self.rescan_active.get():
            self.update_rescan_interval(None)
            self.root.after(self.rescan_interval, self.rescan)
            logging.info("Автопроверка включена")
        else:
            logging.info("Автопроверка отключена")

    def update_rescan_interval(self, event):
        try:
            interval_minutes = float(self.rescan_interval_var.get())
            if interval_minutes < 1 or interval_minutes > 1440:
                raise ValueError("Интервал должен быть от 1 до 1440 минут")
            self.rescan_interval = int(interval_minutes * 60 * 1000)  # Минуты в миллисекунды
            logging.info(f"Интервал автопроверки обновлен: {interval_minutes} минут")
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректный интервал (1–1440 минут)")
            self.rescan_interval_var.set("5")
            self.rescan_interval = 300000
            logging.error("Некорректный интервал автопроверки, сброшен на 5 минут")

    async def update_progress(self, value):
        self.progress_value = value
        self.progress['value'] = value
        self.root.after(0, lambda: self.update_scan_label(True))

    def start_scan(self):
        ip = self.entry_ip.get().strip()
        port_range = self.entry_ports.get().strip()

        try:
            start_port, end_port = map(int, port_range.split("-"))
            if start_port < 1 or end_port > 65535 or start_port > end_port:
                raise ValueError("Недопустимый диапазон портов")
        except ValueError:
            messagebox.showerror("Ошибка", "Введите диапазон портов в формате 25565-25600")
            logging.error("Недопустимый диапазон портов")
            return

        self.btn_scan.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.progress_value = 0
        self.update_scan_label(True)
        for card in self.cards:
            card.destroy()
        for card in self.fav_cards:
            card.destroy()
        self.cards.clear()
        self.fav_cards.clear()
        self.results.clear()
        self.filtered_results.clear()

        self.scan_start_time = datetime.now()
        self.total_ports = end_port - start_port + 1
        threading.Thread(target=self.run_scan, args=(ip, start_port, end_port), daemon=True).start()

        # Запуск автопроверки, если включена
        if self.rescan_active.get():
            self.root.after(self.rescan_interval, self.rescan)

    def rescan(self):
        if self.rescan_active.get():
            self.start_scan()
            self.root.after(self.rescan_interval, self.rescan)

    def rescan_selected_history(self):
        idx = self.history_listbox.curselection()
        if not idx:
            messagebox.showinfo("Инфо", "Выберите запись из истории")
            return

        entry = self.history[idx[0]]

        ip = entry["ip"]
        port_range = entry["ports"]

        if "-" in port_range:
            start_port, end_port = port_range.split("-")
            start_port, end_port = int(start_port), int(end_port)
        else:
            start_port = end_port = int(port_range)

        # Покажем на главной вкладке статус
        self.status_label.config(
            text=f"🔄 Пересканирование {ip}:{port_range}..."
        )

        # Запускаем отдельный поток
        t = threading.Thread(
            target=self._run_scan_thread,
            args=(ip, start_port, end_port),
            daemon=True
        )
        t.start()

    def _run_scan_thread(self, ip, start_port, end_port):
        try:
            self.run_scan(ip, start_port, end_port)
            self.status_label.config(
                text=f"✅ Пересканирование завершено ({ip}:{start_port}-{end_port})"
            )
        except Exception as e:
            self.status_label.config(text=f"❌ Ошибка пересканирования: {e}")


    def run_scan(self, ip, start_port, end_port):
        try:
            start_time = datetime.now()
            # Сканируем избранные сервера
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fav_results = []
            for i, fav in enumerate(self.favorites):
                result = loop.run_until_complete(scan_ports(
                    fav["ip"], fav["port"], fav["port"], timeout=2.0, concurrency=1,
                    progress_callback=self.update_progress
                ))
                if result:
                    fav_results.extend([r for r in result if isinstance(r, dict)])
                self.progress_value = (i + 1) / len(self.favorites) * 100 if self.favorites else 0
                self.progress['value'] = self.progress_value
                self.root.after(0, lambda: self.update_scan_label(True))

            # Сканируем основной диапазон
            main_results = loop.run_until_complete(scan_ports(
                ip, start_port, end_port, timeout=2.0, concurrency=50,
                progress_callback=self.update_progress
            ))
            self.results = [r for r in main_results if isinstance(r, dict)]
            self.filtered_results = self.results.copy()
            self.progress_value = 100
            self.progress['value'] = 100
            self.root.after(0, lambda: self.show_results(self.filtered_results))
            self.root.after(0, lambda: self.show_favorites(fav_results))
            self.root.after(0, lambda: self.btn_scan.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.btn_save.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.update_scan_label(False))
            scan_time = (datetime.now() - start_time).total_seconds()
            self.stats_label.config(text=f"Статистика: {len(self.results)} серверов, {self.total_ports} портов, {scan_time:.1f} сек")
            logging.info(f"Сканирование завершено: {len(self.results)} серверов, {self.total_ports} портов, {scan_time:.1f} сек")
            loop.close()
            self.save_history(ip, f"{start_port}-{end_port}", self.results)
            self.show_history()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Произошла ошибка при сканировании: {e}"))
            self.root.after(0, lambda: self.btn_scan.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.progress['value'] == 0)
            self.root.after(0, lambda: self.update_scan_label(False))
            logging.error(f"Ошибка при сканировании: {e}")

    def check_favorites(self):
        if not self.favorites:
            messagebox.showinfo("Информация", "Нет избранных серверов")
            return
        self.btn_check_favs.config(state=tk.DISABLED)
        threading.Thread(target=self.run_fav_check, daemon=True).start()

    def run_fav_check(self):
        try:
            start_time = datetime.now()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fav_results = []
            for i, fav in enumerate(self.favorites):
                result = loop.run_until_complete(scan_ports(
                    fav["ip"], fav["port"], fav["port"], timeout=2.0, concurrency=1,
                    progress_callback=self.update_progress
                ))
                if result:
                    fav_results.extend([r for r in result if isinstance(r, dict)])
                self.progress_value = (i + 1) / len(self.favorites) * 100
                self.progress['value'] = self.progress_value
                self.root.after(0, lambda: self.update_scan_label(True))
            self.root.after(0, lambda: self.show_favorites(fav_results))
            self.root.after(0, lambda: self.btn_check_favs.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.update_scan_label(False))
            scan_time = (datetime.now() - start_time).total_seconds()
            self.stats_label.config(text=f"Статистика: {len(fav_results)} избранных серверов, {scan_time:.1f} сек")
            logging.info(f"Проверка избранного завершена: {len(fav_results)} серверов, {scan_time:.1f} сек")
            loop.close()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка при проверке избранного: {e}"))
            self.root.after(0, lambda: self.btn_check_favs.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.update_scan_label(False))
            logging.error(f"Ошибка при проверке избранного: {e}")

    def import_servers(self):
        try:
            import tkinter.filedialog as filedialog
            file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
            if not file_path:
                return
            with open(file_path, "r", encoding="utf-8") as f:
                servers = [line.strip() for line in f if line.strip()]
            for server in servers:
                try:
                    ip, port = server.split(":")
                    port = int(port)
                    self.favorites.append({"ip": ip, "port": port, "tags": []})
                except ValueError:
                    messagebox.showwarning("Предупреждение", f"Неверный формат: {server}")
                    logging.warning(f"Неверный формат импорта: {server}")
            self.favorites = list({(f['ip'], f['port']): f for f in self.favorites}.values())
            self.save_favorites()
            self.show_favorites([r for r in self.results if (r['ip'], r['port']) in {(f['ip'], f['port']) for f in self.favorites}])
            messagebox.showinfo("Успех", f"Импортировано {len(servers)} серверов")
            logging.info(f"Импортировано {len(servers)} серверов из {file_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при импорте: {e}")
            logging.error(f"Ошибка при импорте: {e}")

    def apply_filter(self, event=None):
        self.filtered_results = self.results.copy()
        # Фильтр по игрокам
        if self.filter_var.get() == "players":
            self.filtered_results = [r for r in self.filtered_results if r['players_online'] > 0]
        # Фильтр по ядру
        if self.core_var.get() != "all":
            self.filtered_results = [r for r in self.filtered_results if r['core'].lower() == self.core_var.get().lower()]
        # Фильтр по версии
        if self.version_var.get():
            self.filtered_results = [r for r in self.filtered_results if self.version_var.get().lower() in r['version'].lower()]
        # Фильтр по MOTD
        if self.motd_var.get():
            self.filtered_results = [r for r in self.filtered_results if self.motd_var.get().lower() in r['motd'].lower()]
        self.show_results(self.filtered_results)
        self.apply_sort(None)

    def apply_sort(self, _):
        sort_key = self.sort_var.get()
        if sort_key == "По пингу":
            self.filtered_results.sort(key=lambda x: x['ping'])
        elif sort_key == "По игрокам":
            self.filtered_results.sort(key=lambda x: x['players_online'], reverse=True)
        self.show_results(self.filtered_results)

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Успех", f"Скопировано в буфер обмена: {text}")
        logging.info(f"Скопировано в буфер: {text}")

    def show_results(self, results):
        for card in self.cards:
            card.destroy()
        self.cards.clear()

        if not results:
            messagebox.showinfo("Результат", "Сервера не найдены")
            logging.info("Сервера не найдены")
            return

        for r in results:
            if not isinstance(r, dict):
                logging.warning(f"Invalid result skipped: {r}")
                continue

            frame = tk.Frame(self.server_list, bd=2, relief="groove", padx=15, pady=10, bg=self.card_bg_color)
            frame.pack(fill="x", padx=10, pady=5)
            frame.bind("<Enter>", lambda e, f=frame: f.config(bg="#d0d0d0" if self.theme == "light" else "#5a5a5a"))
            frame.bind("<Leave>", lambda e, f=frame: f.config(bg=self.card_bg_color))
            self.cards.append(frame)

            # Индикатор онлайна
            online_color = "#00ff00" if r['players_online'] > 0 else "#ff0000"
            tk.Frame(frame, bg=online_color, width=5).pack(side="left", fill="y")

            # Фавикон
            has_favicon = bool(r.get("favicon") and isinstance(r["favicon"], str) and r["favicon"].startswith("data:image/"))
            if has_favicon:
                try:
                    img_data = base64.b64decode(r["favicon"].split(",")[1])
                    image = Image.open(BytesIO(img_data)).convert("RGBA").resize((64, 64))
                    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                    composite = Image.alpha_composite(background, image)
                    icon = ImageTk.PhotoImage(composite)
                    label_icon = tk.Label(frame, image=icon, bg=self.card_bg_color)
                    label_icon.image = icon
                    label_icon.pack(side="left", padx=5)
                    logging.info(f"Favicon отображен для {r['ip']}:{r['port']}")
                except Exception as e:
                    has_favicon = False
                    logging.error(f"Ошибка favicon для {r['ip']}:{r['port']}: {e}")
                    if self.default_icon:
                        tk.Label(frame, image=self.default_icon, bg=self.card_bg_color).pack(side="left", padx=5)
                    else:
                        tk.Label(frame, text="🖼", font=("Arial", 20), bg=self.card_bg_color).pack(side="left", padx=5)
            else:
                logging.info(f"Нет favicon для {r['ip']}:{r['port']}")
                if self.default_icon:
                    tk.Label(frame, image=self.default_icon, bg=self.card_bg_color).pack(side="left", padx=5)
                else:
                    tk.Label(frame, text="🖼", font=("Arial", 20), bg=self.card_bg_color).pack(side="left", padx=5)

            # Базовая информация на карточке
            tk.Label(frame, text=f"{r['ip']}:{r['port']}", font=("Arial", 12, "bold"), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            self.render_motd_colored(r['motd'], frame)
            tk.Label(frame, text=f"Версия: {r['version']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Игроки: {r['players_online']}/{r['players_max']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Forge: {'✔' if r['forge'] else '✘'}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Core: {r['core']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Ping: {r['ping']} ms", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Button(frame, text="Подробнее", command=lambda res=r: self.show_details(res), image=self.get_icon("details.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
            tk.Button(frame, text="В избранное", command=lambda res=r: self.add_to_favorites(res), image=self.get_icon("favorite.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
            tk.Button(frame, text="Копировать IP", command=lambda res=r: self.copy_to_clipboard(f"{res['ip']}:{res['port']}"), image=self.get_icon("copy.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")

        self.server_canvas.configure(scrollregion=self.server_canvas.bbox("all"))

    def show_favorites(self, fav_results):
        for card in self.fav_cards:
            card.destroy()
        self.fav_cards.clear()

        for r in fav_results:
            if not isinstance(r, dict):
                logging.warning(f"Invalid favorite result skipped: {r}")
                continue

            frame = tk.Frame(self.fav_list, bd=2, relief="groove", padx=15, pady=10, bg=self.card_bg_color)
            frame.pack(fill="x", padx=10, pady=5)
            frame.bind("<Enter>", lambda e, f=frame: f.config(bg="#d0d0d0" if self.theme == "light" else "#5a5a5a"))
            frame.bind("<Leave>", lambda e, f=frame: f.config(bg=self.card_bg_color))
            self.fav_cards.append(frame)

            # Индикатор онлайна
            online_color = "#00ff00" if r['players_online'] > 0 else "#ff0000"
            tk.Frame(frame, bg=online_color, width=5).pack(side="left", fill="y")

            # Фавикон
            has_favicon = bool(r.get("favicon") and isinstance(r["favicon"], str) and r["favicon"].startswith("data:image/"))
            if has_favicon:
                try:
                    img_data = base64.b64decode(r["favicon"].split(",")[1])
                    image = Image.open(BytesIO(img_data)).convert("RGBA").resize((64, 64))
                    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
                    composite = Image.alpha_composite(background, image)
                    icon = ImageTk.PhotoImage(composite)
                    label_icon = tk.Label(frame, image=icon, bg=self.card_bg_color)
                    label_icon.image = icon
                    label_icon.pack(side="left", padx=5)
                    logging.info(f"Favicon отображен для {r['ip']}:{r['port']} (избранное)")
                except Exception as e:
                    has_favicon = False
                    logging.error(f"Ошибка favicon для {r['ip']}:{r['port']} (избранное): {e}")
                    if self.default_icon:
                        tk.Label(frame, image=self.default_icon, bg=self.card_bg_color).pack(side="left", padx=5)
                    else:
                        tk.Label(frame, text="🖼", font=("Arial", 20), bg=self.card_bg_color).pack(side="left", padx=5)
            else:
                logging.info(f"Нет favicon для {r['ip']}:{r['port']} (избранное)")
                if self.default_icon:
                    tk.Label(frame, image=self.default_icon, bg=self.card_bg_color).pack(side="left", padx=5)
                else:
                    tk.Label(frame, text="🖼", font=("Arial", 20), bg=self.card_bg_color).pack(side="left", padx=5)

            # Базовая информация на карточке избранного
            tk.Label(frame, text=f"{r['ip']}:{r['port']}", font=("Arial", 12, "bold"), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            self.render_motd_colored(r['motd'], frame)
            tk.Label(frame, text=f"Версия: {r['version']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Игроки: {r['players_online']}/{r['players_max']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Forge: {'✔' if r['forge'] else '✘'}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Core: {r['core']}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Label(frame, text=f"Ping: {r['ping']} ms", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            fav = next((f for f in self.favorites if f['ip'] == r['ip'] and f['port'] == r['port']), None)
            if fav and fav.get("tags"):
                tk.Label(frame, text=f"Теги: {', '.join(fav['tags'])}", font=("Arial", 10), bg=self.card_bg_color, fg=self.text_color).pack(anchor="w")
            tk.Button(frame, text="Подробнее", command=lambda res=r: self.show_details(res), image=self.get_icon("details.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
            tk.Button(frame, text="Убрать из избранного", command=lambda res=r: self.remove_from_favorites(res), image=self.get_icon("remove_fav.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
            tk.Button(frame, text="Копировать IP", command=lambda res=r: self.copy_to_clipboard(f"{res['ip']}:{res['port']}"), image=self.get_icon("copy.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
            tk.Button(frame, text="Добавить тег", command=lambda res=r: self.add_tag(res), image=self.get_icon("tag.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")

        self.fav_canvas.configure(scrollregion=self.fav_canvas.bbox("all"))

    def render_motd_colored(self, motd, parent):
        text_widget = Text(parent, height=2, wrap="word", bg=self.card_bg_color, borderwidth=0, highlightthickness=0, fg=self.text_color, font=("Arial", 10))
        text_widget.pack(anchor="w", fill="x")
        current_text = ""
        current_tag = ""
        i = 0
        while i < len(motd):
            if motd[i] == '§' and i + 1 < len(motd):
                if current_text:
                    text_widget.insert("end", current_text, current_tag)
                    current_text = ""
                i += 1
                code = motd[i].lower()
                if code in self.colors:
                    current_tag = code
                    text_widget.tag_configure(code, foreground=self.colors[code])
                elif code == 'r':
                    current_tag = ""
            else:
                current_text += motd[i]
            i += 1
        if current_text:
            text_widget.insert("end", current_text, current_tag)
        text_widget.config(state="disabled")

    def show_details(self, result):
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.details_frame, padx=10, pady=10, bg=self.details_bg_color)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=f"Сервер: {result['ip']}:{result['port']}", font=("Arial", 14, "bold"), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        tk.Button(frame, text="Копировать IP", command=lambda: self.copy_to_clipboard(f"{result['ip']}:{result['port']}"), image=self.get_icon("copy.png"), compound=tk.LEFT, font=("Arial", 10)).pack(anchor="w")
        self.render_motd_colored(result['motd'], frame)
        tk.Label(frame, text=f"Версия: {result['version']} (протокол {result['protocol']})", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        tk.Label(frame, text=f"Игроки: {result['players_online']}/{result['players_max']}", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        # Индикатор изменения онлайна
        prev_result = next((r for r in self.results + self.filtered_results if r['ip'] == result['ip'] and r['port'] == result['port']), None)
        if prev_result and prev_result['players_online'] != result['players_online']:
            change = result['players_online'] - prev_result['players_online']
            tk.Label(frame, text=f"Изм. онлайна: {'+' if change > 0 else ''}{change}", fg="#00ff00" if change > 0 else "#ff0000", bg=self.details_bg_color, font=("Arial", 10)).pack(anchor="w")
        tk.Label(frame, text=f"Forge: {'✔' if result['forge'] else '✘'}", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        tk.Label(frame, text=f"Core: {result['core']}", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        tk.Label(frame, text=f"Ping: {result['ping']} ms", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        favicon_status = "✔" if result.get("favicon") and isinstance(result["favicon"], str) and result["favicon"].startswith("data:image/") else "✘ (отсутствует или поврежден)"
        tk.Label(frame, text=f"Favicon: {favicon_status}", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        # Теги
        fav = next((f for f in self.favorites if f['ip'] == result['ip'] and f['port'] == result['port']), None)
        if fav and fav.get("tags"):
            tk.Label(frame, text=f"Теги: {', '.join(fav['tags'])}", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")

        # Скроллируемый список игроков
        tk.Label(frame, text="Игроки онлайн:", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        players_frame = tk.Frame(frame, bg=self.details_bg_color)
        players_frame.pack(fill="both", expand=True)
        players_scrollbar = ttk.Scrollbar(players_frame, orient="vertical")
        players_listbox = tk.Listbox(players_frame, yscrollcommand=players_scrollbar.set, height=5, bg=self.details_bg_color, fg=self.text_color, font=("Arial", 10))
        players_scrollbar.config(command=players_listbox.yview)
        players_scrollbar.pack(side="right", fill="y")
        players_listbox.pack(side="left", fill="both", expand=True)
        for player in result['players_sample'] or ["Нет данных об игроках"]:
            players_listbox.insert("end", player)

        # Скроллируемый список модов
        tk.Label(frame, text="Моды:", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        mods_frame = tk.Frame(frame, bg=self.details_bg_color)
        mods_frame.pack(fill="both", expand=True)
        mods_scrollbar = ttk.Scrollbar(mods_frame, orient="vertical")
        mods_listbox = tk.Listbox(mods_frame, yscrollcommand=mods_scrollbar.set, height=5, bg=self.details_bg_color, fg=self.text_color, font=("Arial", 10))
        mods_scrollbar.config(command=mods_listbox.yview)
        mods_scrollbar.pack(side="right", fill="y")
        mods_listbox.pack(side="left", fill="both", expand=True)
        for mod in result['mods'] or ["Нет модов"]:
            mods_listbox.insert("end", mod)

        # Скроллируемый список плагинов
        tk.Label(frame, text="Плагины:", font=("Arial", 10), bg=self.details_bg_color, fg=self.text_color).pack(anchor="w")
        plugins_frame = tk.Frame(frame, bg=self.details_bg_color)
        plugins_frame.pack(fill="both", expand=True)
        plugins_scrollbar = ttk.Scrollbar(plugins_frame, orient="vertical")
        plugins_listbox = tk.Listbox(plugins_frame, yscrollcommand=plugins_scrollbar.set, height=5, bg=self.details_bg_color, fg=self.text_color, font=("Arial", 10))
        plugins_scrollbar.config(command=plugins_listbox.yview)
        plugins_scrollbar.pack(side="right", fill="y")
        plugins_listbox.pack(side="left", fill="both", expand=True)
        for plugin in result['plugins'] or ["Нет плагинов"]:
            plugins_listbox.insert("end", plugin)

    def add_to_favorites(self, result):
        fav_key = (result['ip'], result['port'])
        if fav_key not in {(f['ip'], f['port']) for f in self.favorites}:
            self.favorites.append({"ip": result['ip'], "port": result['port'], "tags": []})
            self.save_favorites()
            self.show_favorites([r for r in self.results + [result] if (r['ip'], r['port']) in {(f['ip'], f['port']) for f in self.favorites}])
            messagebox.showinfo("Успех", f"Сервер {result['ip']}:{result['port']} добавлен в избранное")
            logging.info(f"Добавлен в избранное: {result['ip']}:{result['port']}")

    def remove_from_favorites(self, result):
        self.favorites = [f for f in self.favorites if not (f['ip'] == result['ip'] and f['port'] == result['port'])]
        self.save_favorites()
        self.show_favorites([r for r in self.results + [result] if (r['ip'], r['port']) in {(f['ip'], f['port']) for f in self.favorites}])
        messagebox.showinfo("Успех", f"Сервер {result['ip']}:{result['port']} удален из избранного")
        logging.info(f"Удален из избранного: {result['ip']}:{result['port']}")

    def add_tag(self, result):
        tag = tk.simpledialog.askstring("Добавить тег", f"Введите тег для {result['ip']}:{result['port']}:")
        if tag:
            for fav in self.favorites:
                if fav['ip'] == result['ip'] and fav['port'] == result['port']:
                    fav['tags'].append(tag)
            self.save_favorites()
            self.show_favorites([r for r in self.results + [result] if (r['ip'], r['port']) in {(f['ip'], f['port']) for f in self.favorites}])
            messagebox.showinfo("Успех", f"Тег '{tag}' добавлен")
            logging.info(f"Добавлен тег '{tag}' для {result['ip']}:{result['port']}")

    def save_results(self):
        if not self.results:
            messagebox.showinfo("Информация", "Нет результатов для сохранения")
            logging.info("Попытка сохранить пустые результаты")
            return

        filename = f"scan_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            data = {
                "scanned_at": datetime.utcnow().isoformat(),
                "servers_found": len(self.results),
                "results": self.results
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("Успех", f"Результаты сохранены в {filename}")
            logging.info(f"Результаты сохранены в {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить результаты: {e}")
            logging.error(f"Ошибка сохранения результатов: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerScannerGUI(root)
    root.mainloop()
