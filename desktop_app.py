import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

# ======================================================
# PROJECT FOLDERS
# ======================================================
# CSV ve NotebookLM'e yüklenecek TXT çıktılarının tek bir yerde düzenli durması için
# proje köküne göre sabit klasörler tanımlıyoruz.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Senin yapına göre: data/csv ve data/notebooklm_txt
CSV_DIR = os.path.join(BASE_DIR, "data", "csv")
TXT_DIR = os.path.join(BASE_DIR, "data", "notebooklm_txt")

os.makedirs(CSV_DIR, exist_ok=True)
os.makedirs(TXT_DIR, exist_ok=True)

APP_TITLE = "TikTok Scraper – Masaüstü Arayüz"
SCRIPT_NAME = "tiktok_scraper_raw.py"

NOTEBOOKLM_URL = "https://notebooklm.google.com/"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1050x760")
        self.minsize(980, 720)

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

        # UI Theme / Styles
        self._apply_theme()

        self._build_ui()
        self._sync_mode_ui()
        self.refresh_csv_list()

    # ======================================================
    # THEME
    # ======================================================
    def _apply_theme(self):
        self.style = ttk.Style(self)

        # mümkün olan en "modern" hissi veren ttk temaları
        preferred = ["clam", "vista", "xpnative", "alt", "default"]
        for t in preferred:
            try:
                self.style.theme_use(t)
                break
            except tk.TclError:
                continue

        # Renk paleti
        self.COL_BG = "#0b1220"        # ana arka plan (lacivert)
        self.COL_CARD = "#101a2f"      # kart
        self.COL_CARD2 = "#0f1a33"     # kart2
        self.COL_TEXT = "#e6eefc"      # yazı
        self.COL_MUTED = "#9bb0d0"     # ikincil yazı
        self.COL_ACCENT = "#4f8cff"    # mavi vurgu
        self.COL_ACCENT2 = "#26c6da"   # turkuaz vurgu
        self.COL_BAD = "#ff5c6c"
        self.COL_OK = "#27e1a0"

        self.configure(bg=self.COL_BG)

        default_font = ("Segoe UI", 10)
        self.option_add("*Font", default_font)

        # Genel ttk ayarları
        self.style.configure(".", background=self.COL_BG, foreground=self.COL_TEXT)
        self.style.configure("TFrame", background=self.COL_BG)
        self.style.configure("Card.TFrame", background=self.COL_CARD)
        self.style.configure("Card2.TFrame", background=self.COL_CARD2)

        self.style.configure("TLabel", background=self.COL_BG, foreground=self.COL_TEXT)
        self.style.configure("Muted.TLabel", background=self.COL_BG, foreground=self.COL_MUTED)
        self.style.configure("Title.TLabel", background=self.COL_BG, foreground=self.COL_TEXT, font=("Segoe UI", 16, "bold"))
        self.style.configure("Subtitle.TLabel", background=self.COL_BG, foreground=self.COL_MUTED, font=("Segoe UI", 10))

        self.style.configure("TLabelframe", background=self.COL_BG, foreground=self.COL_TEXT)
        self.style.configure("TLabelframe.Label", background=self.COL_BG, foreground=self.COL_TEXT, font=("Segoe UI", 10, "bold"))

        self.style.configure("TEntry", fieldbackground="#0a1020", foreground=self.COL_TEXT)
        self.style.configure("TCombobox", fieldbackground="#0a1020", foreground=self.COL_TEXT)
        self.style.map("TCombobox", fieldbackground=[("readonly", "#0a1020")])

        # Butonlar
        self.style.configure(
            "Primary.TButton",
            background=self.COL_ACCENT,
            foreground="#ffffff",
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", "#3f7dff"), ("disabled", "#2a3550")],
            foreground=[("disabled", "#cfd7e6")],
        )

        self.style.configure(
            "Danger.TButton",
            background=self.COL_BAD,
            foreground="#ffffff",
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        self.style.map("Danger.TButton", background=[("active", "#ff3a50"), ("disabled", "#2a3550")])

        self.style.configure(
            "Ghost.TButton",
            background=self.COL_CARD,
            foreground=self.COL_TEXT,
            padding=(12, 7),
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        self.style.map("Ghost.TButton", background=[("active", "#172445")])

        self.style.configure(
            "Notebook.TButton",
            background=self.COL_ACCENT2,
            foreground="#041018",
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        self.style.map("Notebook.TButton", background=[("active", "#1fb6c8"), ("disabled", "#2a3550")])


    # ======================================================
    # UI
    # ======================================================
    def _build_ui(self):
        # HEADER
        header = ttk.Frame(self, padding=(16, 14), style="TFrame")
        header.pack(fill="x")

        ttk.Label(header, text="TikTok Scraper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Hashtag / kullanıcıdan veri çek • Risk analizi üret • CSV çıktılarını yönet",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # MAIN WRAP
        wrap = ttk.Frame(self, padding=(16, 10))
        wrap.pack(fill="both", expand=True)

        # ÜST KART: Ayarlar
        top_card = ttk.Frame(wrap, padding=14, style="Card.TFrame")
        top_card.pack(fill="x", pady=(0, 12))

        # Grid ayarı
        top_card.columnconfigure(3, weight=1)

        ttk.Label(top_card, text="Mod").grid(row=0, column=0, sticky="w")
        self.mode_combo = ttk.Combobox(
            top_card,
            textvariable=self.mode_var,
            values=["hashtag", "user"],
            state="readonly",
            width=12,
        )
        self.mode_combo.grid(row=0, column=1, padx=(10, 18), sticky="w")
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self._sync_mode_ui())

        self.query_label = ttk.Label(top_card, text="Hashtag")
        self.query_label.grid(row=0, column=2, sticky="w")
        self.query_entry = ttk.Entry(top_card, textvariable=self.query_var, width=46)
        self.query_entry.grid(row=0, column=3, padx=(10, 18), sticky="ew")

        ttk.Label(top_card, text="Limit").grid(row=0, column=4, sticky="w")
        self.limit_spin = tk.Spinbox(
       top_card,
       from_=1,
       to=500,
       textvariable=self.limit_var,
       width=8,
        fg="black",          # sayı rengi siyah
        bg="white",          # arka plan beyaz
       highlightthickness=0,
        relief="flat",
        )
       
        self.limit_spin.grid(row=0, column=5, padx=(10, 0), sticky="w")

        # Ops row
        opts = ttk.Frame(top_card, padding=(0, 12, 0, 0), style="Card.TFrame")
        opts.grid(row=1, column=0, columnspan=6, sticky="ew")

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

        # CSV name row
        csv_row = ttk.Frame(top_card, padding=(0, 12, 0, 0), style="Card.TFrame")
        csv_row.grid(row=2, column=0, columnspan=6, sticky="ew")

        ttk.Label(csv_row, text="Çıktı CSV adı").pack(side="left")
        ttk.Entry(csv_row, textvariable=self.csv_name_var, width=30).pack(side="left", padx=10)
        ttk.Label(csv_row, text="(varsa üzerine yazılır)", style="Muted.TLabel").pack(side="left")

        # BUTTON BAR
        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(0, 12))

        self.run_btn = ttk.Button(btns, text="Çalıştır", command=self.on_run, style="Primary.TButton")
        self.run_btn.pack(side="left")

        self.stop_btn = ttk.Button(btns, text="Durdur", command=self.on_stop, state="disabled", style="Danger.TButton")
        self.stop_btn.pack(side="left", padx=10)

        self.clear_btn = ttk.Button(btns, text="Log Temizle", command=self.clear_log, style="Ghost.TButton")
        self.clear_btn.pack(side="left", padx=10)

        # NOTEBOOKLM BUTONU
        self.notebook_btn = ttk.Button(
            btns,
            text="NOTEBOOKLM",
            command=self.open_notebooklm_with_prompt,
            style="Notebook.TButton",
        )
        self.notebook_btn.pack(side="right")

        # CSV LIST + LOG iki kolon
        body = ttk.Frame(wrap)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # Sol: CSV kartı
        csv_card = ttk.Frame(body, padding=12, style="Card.TFrame")
        csv_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ttk.Label(csv_card, text="Mevcut CSV Dosyaları", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        list_wrap = ttk.Frame(csv_card, style="Card.TFrame")
        list_wrap.pack(fill="both", expand=True)

        self.csv_listbox = tk.Listbox(
            list_wrap,
            height=10,
            bg="#0a1020",
            fg=self.COL_TEXT,
            selectbackground=self.COL_ACCENT,
            selectforeground="#ffffff",
            highlightthickness=0,
            bd=0,
        )
        self.csv_listbox.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.csv_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.csv_listbox.configure(yscrollcommand=scroll.set)
        self.csv_listbox.bind("<Double-Button-1>", self.on_csv_double_click)

        csv_btns = ttk.Frame(csv_card, padding=(0, 10, 0, 0), style="Card.TFrame")
        csv_btns.pack(fill="x")

        ttk.Button(csv_btns, text="CSV’yi Aç", command=self.on_csv_double_click, style="Ghost.TButton").pack(side="left")
        ttk.Button(csv_btns, text="Klasörde Göster", command=self.open_in_finder, style="Ghost.TButton").pack(side="left", padx=8)
        ttk.Button(csv_btns, text="Listeyi Yenile", command=self.refresh_csv_list, style="Ghost.TButton").pack(side="left", padx=8)

        # Sağ: LOG kartı
        log_card = ttk.Frame(body, padding=12, style="Card.TFrame")
        log_card.grid(row=0, column=1, sticky="nsew")

        ttk.Label(log_card, text="Canlı Log", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        log_wrap = ttk.Frame(log_card, style="Card.TFrame")
        log_wrap.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            bg="#0a1020",
            fg=self.COL_TEXT,
            insertbackground=self.COL_TEXT,
            highlightthickness=0,
            bd=0,
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    # ======================================================
    # Helpers
    # ======================================================
    def _sync_mode_ui(self):
        mode = self.mode_var.get()
        if mode == "hashtag":
            self.query_label.config(text="Hashtag")
            # placeholder hissi için başlık değil, kullanıcının göreceği şekilde
        else:
            self.query_label.config(text="Kullanıcı adı")

    def log(self, msg: str):
        try:
            msg = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        except Exception:
            pass
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def clear_log(self):
        self.log_text.delete("1.0", "end")

    def refresh_csv_list(self):
        self.csv_listbox.delete(0, "end")
        try:
            # CSV'leri artık data/csv klasöründen listeliyoruz
            for f in sorted(os.listdir(CSV_DIR)):
                if f.lower().endswith(".csv"):
                    self.csv_listbox.insert("end", f)
        except Exception as e:
            self.log(f"❌ CSV listeleme hatası: {e}")

    def get_selected_csv_path(self):
        sel = self.csv_listbox.curselection()
        if not sel:
            return None
        filename = self.csv_listbox.get(sel[0])
        return os.path.join(CSV_DIR, filename)

    def on_csv_double_click(self, event=None):
        path = self.get_selected_csv_path()
        if not path or not os.path.exists(path):
            messagebox.showerror("Hata", "Seçilen CSV bulunamadı.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:
            messagebox.showerror("Hata", f"CSV açılamadı: {e}")

    def open_in_finder(self):
        path = self.get_selected_csv_path()
        if not path or not os.path.exists(path):
            messagebox.showerror("Hata", "Seçilen CSV bulunamadı.")
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path], check=False)
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)], check=False)
        except Exception as e:
            messagebox.showerror("Hata", f"Klasör açılamadı: {e}")

    # ======================================================
    # NOTEBOOKLM
    # ======================================================
    def build_notebooklm_prompt(self, csv_path: str | None):
        base = (
           "ROLÜN:\n"
        "Sen sosyal medya içeriklerinden üretilmiş çoklu risk göstergelerini birleştirerek "
        "video bazında ve veri seti genelinde bütüncül bir risk değerlendirmesi yapan analitik asistansın.\n\n"

        "VERİ SETİ:\n"
        "Yüklenen CSV dosyasında her satır 1 TikTok videosunu temsil eder. CSV içinde genellikle şu tür alanlar bulunur:\n"
        "- Video linki / kimliği (örn. video_url)\n"
        "- Metin alanları (örn. caption_raw, overlay_text_raw, transcript_raw)\n"
        "- Risk göstergeleri ve skorlar (örn. caption_risk, overlay_risk, transcript_risk gibi 0–1 arası değerler)\n\n"

        "AMAÇ:\n"
        "Bu veriyi inceleyerek iki seviyede değerlendirme üret:\n"
        "1) Her video için tek bir 'Birleşik Risk Skoru' (0–100)\n"
        "2) Tüm videoları temsil eden tek bir 'Overall Risk Score' (0–100)\n\n"

        "ÖNEMLİ KISIT:\n"
        "Sana herhangi bir ağırlık/formül verilmiyor. "
        "CSV’deki risk kolonlarını, metin alanlarını ve varsa ek sinyalleri (boşluk/eksik veri vb.) "
        "analiz ederek birleşik skoru kendin tasarla. "
        "Kullandığın yaklaşımı 3–6 madde ile şeffaf biçimde açıkla (formül yazmak zorunda değilsin; mantık/heuristic açıklaması yeterli).\n\n"

        "İŞ AKIŞI / İSTENEN ÇIKTILAR:\n"
        "A) Önce veri setini kısaca tanı:\n"
        "- Kaç video var (N)\n"
        "- Hangi risk kolonları var, hangi alanlarda eksik veri var (ör. transcript boş olanlar)\n\n"

        "B) Video bazında skor üret:\n"
        "- Her satır için 0–100 arası 'video_risk_score' oluştur.\n"
        "- Skoru belirlerken metin alanlarındaki risk göstergelerini (umutsuzluk, kendine zarar verme ima/niyet, yardım çağrısı vb.) "
        "ve mevcut sayısal risk kolonlarını birlikte değerlendir.\n"
        "- Eksik alan varsa (ör. transcript yoksa) adil bir şekilde telafi ederek karar ver.\n\n"

        "C) Overall Risk Score üret:\n"
        "- Veri setinin tamamını temsil eden tek bir 0–100 skor ver.\n"
        "- Sadece ortalamaya bakma: Çok riskli az sayıda içerik varsa bunun etkisini ayrıca vurgula.\n\n"

        "D) Sonuç formatı (aynen bu başlıklarla):\n"
        "1) Overall Risk Score (0–100): X\n"
        "2) Risk Seviyesi (Low/Moderate/High/Critical): ...\n"
        "3) Kısa Yönetici Özeti (3-5 cümle)\n\n"

        "E) Kanıt/Şeffaflık:\n"
        "- Top 10 en riskli video tablosu üret:\n"
        "  video_url | video_risk_score | ilgili kolonlar (caption_risk/overlay_risk/transcript_risk varsa) | kısa gerekçe\n"
        "- Risk dağılımı:\n"
        "  0–25 / 25–50 / 50–75 / 75–100 aralıklarında kaç video var?\n\n"

        "F) Asıl Yorum (en önemli bölüm):\n"
        "- Bu içeriklerde riskin hangi kaynaklardan yükseldiğini açıkla (caption mı, transcript mi, overlay mi?).\n"
        "- En yaygın 'risk temaları' neler? (ör. yalnızlık, umutsuzluk, kendine zarar verme ima, yardım çağrısı, vb.)\n"
        "- Veri kalitesi sınırlılıklarını yaz (eksik transcript, kısa caption, spam hashtag vb.).\n\n"

        "DİL VE ETİK:\n"
        "- Klinik tanı/teşhis koyma.\n"
        "- Kesin hüküm kurma; 'risk göstergesi', 'olası işaretler', 'önleyici değerlendirme' dili kullan.\n"
        "- Akademik, profesyonel ve tarafsız yaz.\n"
        )

        if csv_path:
            base += f"\nDOSYA:\n- Seçili CSV: {os.path.basename(csv_path)}\n"
        else:
            base += "\nDOSYA:\n- (Henüz seçili CSV yok. CSV yükledikten sonra bu promptu kullan.)\n"

        base += "\nÇIKTI:\nÖnce kısa özet, sonra tablo, sonra 'Top 10 riskli satır' listesi.\n"
        return base

    def export_csv_for_notebooklm(self, csv_path: str | None):
        """NotebookLM'in CSV kabul etmediği durumlar için CSV'yi TXT'ye dönüştürür.

        - TXT çıktısı: data/notebooklm_txt klasörüne yazılır.
        - Encoding sorunlarına karşı birkaç olası encoding denenir.
        """
        if not csv_path or not os.path.exists(csv_path):
            return None

        base_name = os.path.splitext(os.path.basename(csv_path))[0]
        out_path = os.path.join(TXT_DIR, f"{base_name}_notebooklm.txt")

        raw = open(csv_path, "rb").read()
        text = None
        for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                pass

        if text is None:
            raise ValueError("CSV decode edilemedi (encoding sorunu).")

        # newline normalize
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        return out_path

    def open_notebooklm_with_prompt(self):
        csv_path = self.get_selected_csv_path()
        prompt = self.build_notebooklm_prompt(csv_path)

        # CSV seçiliyse NotebookLM için TXT üret (CSV kabul etmeyebilir)
        txt_path = None
        if csv_path:
            try:
                txt_path = self.export_csv_for_notebooklm(csv_path)
            except Exception as e:
                messagebox.showerror("Hata", f"NotebookLM TXT oluşturulamadı: {e}")
                return

        # Panoya kopyala
        try:
            self.clipboard_clear()
            self.clipboard_append(prompt)
            self.update()  # clipboard garanti yazılsın
        except Exception as e:
            messagebox.showerror("Hata", f"Panoya kopyalanamadı: {e}")
            return

        # Siteyi aç
        try:
            webbrowser.open_new_tab(NOTEBOOKLM_URL)
        except Exception as e:
            messagebox.showerror("Hata", f"NotebookLM açılamadı: {e}")
            return

        # Kullanıcıya net yönlendirme
        msg = (
            "✅ NotebookLM açıldı.\n\n"
            "Hazır prompt PANODA.\n"
            "1) NotebookLM'de yeni notebook aç\n"
            "2) Soldan kaynak ekle\n"
        )

        if txt_path:
            msg += (
                "3) CSV yerine şu TXT dosyasını yükle:\n"
                f"   {os.path.basename(txt_path)}\n"
                "4) Sohbet alanına Ctrl+V ile promptu yapıştır ve çalıştır\n"
            )
        else:
            msg += "3) Sohbet alanına Ctrl+V ile promptu yapıştır ve çalıştır\n"

        if csv_path:
            msg += f"\nSeçili CSV: {os.path.basename(csv_path)}"
        if txt_path:
            msg += f"\nÜretilen TXT: {os.path.basename(txt_path)} (data/notebooklm_txt içinde)"
        messagebox.showinfo("NOTEBOOKLM", msg)

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

        # Çıktı CSV'yi her zaman data/csv içine yaz
        out_csv_path = os.path.join(CSV_DIR, csv_name)

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
            out_csv_path,
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
            env = os.environ.copy()
            if sys.platform.startswith("win"):
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=self.script_dir,
                env=env,
            )

            if self.proc.stdout:
                for line in self.proc.stdout:
                    clean = line.rstrip("\n").rstrip("\r")
                    self.after(0, lambda l=clean: self.log(l))

            code = self.proc.wait()
            if code == 0:
                self.after(0, lambda: self.log("✅ İşlem tamamlandı."))
            else:
                self.after(0, lambda: self.log(f"❌ Script hata ile bitti (code={code})"))

        except Exception as e:
            err = str(e)
            self.after(0, lambda err=err: self.log(f"❌ Çalıştırma hatası: {err}"))

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
