import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

APP_TITLE = "TikTok Scraper – Masaüstü Arayüz"
SCRIPT_NAME = "tiktok_scraper_raw.py"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1000x720")

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.script_path = os.path.join(self.script_dir, SCRIPT_NAME)

        if not os.path.exists(self.script_path):
            messagebox.showerror(
                "Hata",
                f"{SCRIPT_NAME} bulunamadı.\nBeklenen yol:\n{self.script_path}",
            )
            self.destroy()
            return

        # ---------------- Variables ----------------
        self.mode_var = tk.StringVar(value="hashtag")
        self.query_var = tk.StringVar(value="")
        self.limit_var = tk.IntVar(value=5)

        self.analyze_var = tk.BooleanVar(value=True)
        self.headless_var = tk.BooleanVar(value=False)

        self.csv_name_var = tk.StringVar(value="tiktok_analyzed.csv")

        self.proc = None
        self.running = False

        self._build_ui()
        self._sync_mode_ui()
        self.refresh_csv_list()

    # ======================================================
    # UI
    # ======================================================
    def _build_ui(self):
        # -------- Top controls --------
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        ttk.Label(top, text="Mod:").grid(row=0, column=0, sticky="w")
        self.mode_combo = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=["hashtag", "user"],
            state="readonly",
            width=12,
        )
        self.mode_combo.grid(row=0, column=1, padx=(8, 16))
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_mode_ui())

        self.query_label = ttk.Label(top, text="Hashtag:")
        self.query_label.grid(row=0, column=2, sticky="w")
        self.query_entry = ttk.Entry(top, textvariable=self.query_var, width=40)
        self.query_entry.grid(row=0, column=3, padx=(8, 16))

        self.limit_label = ttk.Label(top, text="Limit:")
        self.limit_spin = ttk.Spinbox(
            top, from_=1, to=500, textvariable=self.limit_var, width=8
        )
        self.limit_label.grid(row=0, column=4, sticky="w")
        self.limit_spin.grid(row=0, column=5, padx=(8, 0))

        # -------- Options --------
        opts = ttk.Frame(self, padding=(12, 0, 12, 12))
        opts.pack(fill="x")

        ttk.Checkbutton(
            opts,
            text="Risk analizi üret (BERT)",
            variable=self.analyze_var,
        ).pack(side="left")

        ttk.Checkbutton(
            opts,
            text="Headless çalıştır (tarayıcı görünmesin)",
            variable=self.headless_var,
        ).pack(side="left", padx=(20, 0))

        # -------- CSV name --------
        csv_frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        csv_frame.pack(fill="x")

        ttk.Label(csv_frame, text="Çıktı CSV adı:").pack(side="left")
        ttk.Entry(
            csv_frame, textvariable=self.csv_name_var, width=30
        ).pack(side="left", padx=8)
        ttk.Label(csv_frame, text="(varsa üzerine yazılır)").pack(side="left")

        # -------- Buttons --------
        btns = ttk.Frame(self, padding=(12, 0, 12, 12))
        btns.pack(fill="x")

        self.run_btn = ttk.Button(btns, text="Çalıştır", command=self.on_run)
        self.run_btn.pack(side="left")

        self.stop_btn = ttk.Button(
            btns, text="Durdur", command=self.on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=10)

        self.clear_btn = ttk.Button(btns, text="Log Temizle", command=self.clear_log)
        self.clear_btn.pack(side="left", padx=10)

        # -------- CSV list --------
        csv_list_frame = ttk.LabelFrame(self, text="Mevcut CSV Dosyaları", padding=10)
        csv_list_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.csv_listbox = tk.Listbox(csv_list_frame, height=6)
        self.csv_listbox.pack(side="left", fill="x", expand=True)

        scroll = ttk.Scrollbar(
            csv_list_frame, orient="vertical", command=self.csv_listbox.yview
        )
        scroll.pack(side="right", fill="y")
        self.csv_listbox.configure(yscrollcommand=scroll.set)

        # ✅ Double click to open CSV
        self.csv_listbox.bind("<Double-Button-1>", self.on_csv_double_click)

        # CSV action buttons
        csv_btns = ttk.Frame(self, padding=(12, 0, 12, 12))
        csv_btns.pack(fill="x")

        ttk.Button(csv_btns, text="CSV’yi Aç", command=self.on_csv_double_click).pack(
            side="left"
        )
        ttk.Button(csv_btns, text="Finder’da Göster", command=self.open_in_finder).pack(
            side="left", padx=10
        )
        ttk.Button(csv_btns, text="Listeyi Yenile", command=self.refresh_csv_list).pack(
            side="left", padx=10
        )

        # -------- Log area --------
        log_frame = ttk.LabelFrame(self, text="Canlı Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log_text = tk.Text(log_frame, wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    # ======================================================
    # Helpers
    # ======================================================
    def _sync_mode_ui(self):
        mode = self.mode_var.get()
        if mode == "hashtag":
            self.query_label.config(text="Hashtag:")
        else:
            self.query_label.config(text="Kullanıcı adı:")

    def log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def refresh_csv_list(self):
        self.csv_listbox.delete(0, "end")
        for f in sorted(os.listdir(self.script_dir)):
            if f.lower().endswith(".csv"):
                self.csv_listbox.insert("end", f)

    def get_selected_csv_path(self):
        sel = self.csv_listbox.curselection()
        if not sel:
            return None
        filename = self.csv_listbox.get(sel[0])
        return os.path.join(self.script_dir, filename)

    def on_csv_double_click(self, event=None):
        path = self.get_selected_csv_path()
        if not path or not os.path.exists(path):
            messagebox.showerror("Hata", "Seçilen CSV bulunamadı.")
            return
        try:
            # macOS: open with default app (Excel/Numbers)
            subprocess.run(["open", path], check=False)
        except Exception as e:
            messagebox.showerror("Hata", f"CSV açılamadı: {e}")

    def open_in_finder(self):
        path = self.get_selected_csv_path()
        if not path or not os.path.exists(path):
            messagebox.showerror("Hata", "Seçilen CSV bulunamadı.")
            return
        try:
            # macOS: reveal in Finder
            subprocess.run(["open", "-R", path], check=False)
        except Exception as e:
            messagebox.showerror("Hata", f"Finder açılamadı: {e}")

    # ======================================================
    # Run / Stop
    # ======================================================
    def build_cmd(self):
        mode = self.mode_var.get().strip()
        query = self.query_var.get().strip()

        if not query:
            raise ValueError("Query boş olamaz.")

        csv_name = self.csv_name_var.get().strip()
        if not csv_name:
            csv_name = "tiktok_analyzed.csv"
        if not csv_name.lower().endswith(".csv"):
            csv_name += ".csv"

        cmd = [
            sys.executable,
            self.script_path,
            "--mode",
            mode,
            "--query",
            query,
            "--limit",
            str(int(self.limit_var.get())),
            "--analyze",
            "1" if self.analyze_var.get() else "0",
            "--headless",
            "1" if self.headless_var.get() else "0",
            "--out_csv",
            csv_name,
        ]
        return cmd

    def on_run(self):
        if self.running:
            return

        try:
            cmd = self.build_cmd()
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return

        self.running = True
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        self.log("Komut:")
        self.log(" ".join(cmd))
        self.log("-" * 60)

        thread = threading.Thread(target=self._run_process, args=(cmd,), daemon=True)
        thread.start()

    def _run_process(self, cmd):
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.script_dir,
            )

            for line in self.proc.stdout:
                self.after(0, lambda l=line: self.log(l.rstrip()))

            code = self.proc.wait()
            if code == 0:
                self.after(0, lambda: self.log("✅ İşlem tamamlandı."))
            else:
                self.after(0, lambda: self.log(f"❌ Script hata ile bitti (code={code})"))

        except Exception as e:
            self.after(0, lambda: self.log(f"❌ Çalıştırma hatası: {e}"))

        finally:
            self.proc = None
            self.running = False
            self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.refresh_csv_list()

    def on_stop(self):
        if self.proc and self.running:
            try:
                self.proc.terminate()
                self.log("🛑 Durdurma sinyali gönderildi.")
            except Exception as e:
                self.log(f"❌ Durdurma hatası: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
