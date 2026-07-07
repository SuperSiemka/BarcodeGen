"""
BarcodeGen — Desktop barcode generator (EAN-13 / Code128)
"""

import os
import sys
import winreg
import webbrowser
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from PIL import Image as PILImage

from generator import (BarcodeGenerator, BarcodeError, safe_filename,
                       _LEGACY_TEXT_MM_PER_UNIT)
from lang import LANG

# ─── Constants ───────────────────────────────────────────────────────────────

APP_NAME = "BarcodeGen"
VERSION  = "1.0.0"
REG_KEY  = r"Software\BarcodeGen"

DEFAULT_SETTINGS: dict = {
    "output_dir": "",
    "height":     9.0,
    "distance":   0.33,     # module width in mm (EAN-13 nominal SC2)
    "font_size":  2.2,      # text height in mm (2.2 = historic default look)
    "font_unit":  "mm",     # marker: font_size stored in mm (absent = legacy unitless)
    "dpi":        300,
    "scale":      1.0,
    "language":   "PL",
    "theme":      "dark",
}

# ─── Path helpers (PyInstaller-safe) ─────────────────────────────────────────

def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name
    return Path(__file__).parent / name


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# ─── Registry settings (no external files) ───────────────────────────────────

def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    found: set = set()
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        for k, default in DEFAULT_SETTINGS.items():
            try:
                val, _ = winreg.QueryValueEx(key, k)
                # cast to original type
                if isinstance(default, float):
                    settings[k] = float(val)
                elif isinstance(default, int):
                    settings[k] = int(val)
                else:
                    settings[k] = str(val)
                found.add(k)
            except (FileNotFoundError, ValueError, TypeError):
                # Missing key, or a corrupt/mistyped stored value (e.g. "300.0"
                # where an int is expected) — fall back to the default, never crash.
                pass
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    # Clamp scale to valid range — guards against stale registry values
    settings["scale"] = max(0.5, min(3.0, settings["scale"]))
    # Migrate the legacy unitless "Skala tekstu" to millimetres. Stored values
    # written before the mm change carry no "font_unit" marker — convert them
    # once (e.g. old default 1.3 -> 2.2 mm), after which save_settings() always
    # writes the marker.
    if "font_size" in found and "font_unit" not in found:
        settings["font_size"] = round(settings["font_size"] * _LEGACY_TEXT_MM_PER_UNIT, 1)
    settings["font_unit"] = "mm"
    # Migrate the old dead "distance" default (0.15) — the field never affected
    # output before this release, so a stored 0.15 can only be that legacy value.
    # Reset it to the working default rather than render suddenly-narrow bars.
    if abs(settings["distance"] - 0.15) < 1e-9:
        settings["distance"] = DEFAULT_SETTINGS["distance"]
    return settings


def save_settings(settings: dict) -> None:
    # Best-effort persistence — a registry write failure (e.g. GPO restriction)
    # must never take down the app or interrupt generation.
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        for k, v in settings.items():
            winreg.SetValueEx(key, k, 0, winreg.REG_SZ, str(v))
        winreg.CloseKey(key)
    except OSError:
        pass


# ─── Main Application ────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings  = load_settings()
        self.lang      = self.settings["language"]
        self.t         = LANG[self.lang]
        self.generator = BarcodeGenerator()
        self._last_result = None   # (ok, total) of the last batch — kept as raw
                                   # numbers so the counter can be re-rendered in
                                   # the new language after a UI rebuild

        ctk.set_appearance_mode(self.settings.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{VERSION}")
        try:
            self.iconbitmap(str(resource_path("icon.ico")))
        except Exception:
            pass
        self.geometry("860x700")
        self.minsize(800, 620)
        self.resizable(True, True)

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_topbar()
        self._build_logo_section()
        self._build_main()
        self._build_statusbar()
        self._build_footer()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=48, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bar, text=APP_NAME,
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=8, sticky="w")

        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=12, pady=8, sticky="e")

        self.lang_btn = ctk.CTkButton(
            btn_frame, text=self._other_lang(),
            width=60, command=self._toggle_lang,
        )
        self.lang_btn.pack(side="left", padx=(0, 8))

        self.theme_btn = ctk.CTkButton(
            btn_frame, text=self._theme_icon(),
            width=40, command=self._toggle_theme,
        )
        self.theme_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text=self.t["help"],
            width=100, command=self._open_help,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text=self.t["settings"],
            width=100, command=self._open_settings,
        ).pack(side="left")

    def _build_logo_section(self):
        section = ctk.CTkFrame(self, corner_radius=0, fg_color=("white", "#1a1a1a"))
        section.grid(row=1, column=0, sticky="ew")
        section.grid_columnconfigure(0, weight=1)

        try:
            pil_logo  = PILImage.open(resource_path("logo.png"))
            target_h  = 90
            target_w  = int(pil_logo.width * target_h / pil_logo.height)
            pil_logo  = pil_logo.resize((target_w, target_h), PILImage.LANCZOS)
            ctk_logo  = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo,
                                     size=(target_w, target_h))
            ctk.CTkLabel(section, image=ctk_logo, text="").grid(row=0, column=0, pady=16)
        except Exception:
            ctk.CTkLabel(section, text=APP_NAME,
                         font=ctk.CTkFont(size=28, weight="bold")).grid(row=0, column=0, pady=16)

    def _build_main(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=2, column=0, sticky="nsew", padx=16, pady=(12, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # ── Input card ───────────────────────────────────────────────────────
        input_card = ctk.CTkFrame(main)
        input_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            input_card, text=self.t["input_label"],
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.code_input = ctk.CTkTextbox(input_card, height=130, font=ctk.CTkFont(size=13))
        self.code_input.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="ew")

        btn_row = ctk.CTkFrame(input_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=14, pady=(0, 4), sticky="w")

        ctk.CTkButton(
            btn_row, text=self.t["import_excel"],
            width=180, command=self._import_excel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text=self.t["clear"],
            width=90, fg_color="#555", hover_color="#444",
            command=self._clear_input,
        ).pack(side="left")

        ctk.CTkLabel(
            input_card, text=self.t["excel_hint"],
            font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"),
            anchor="w", wraplength=780, justify="left",
        ).grid(row=3, column=0, padx=14, pady=(0, 8), sticky="w")

        # ── Scale / size slider ──────────────────────────────────────────────
        scale_row = ctk.CTkFrame(input_card, fg_color="transparent")
        scale_row.grid(row=4, column=0, padx=14, pady=(0, 10), sticky="ew")
        scale_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            scale_row, text=self.t["scale_label"],
            font=ctk.CTkFont(size=12, weight="bold"), width=120, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._scale_var = tk.DoubleVar(value=self.settings.get("scale", 1.0))

        self._scale_slider = ctk.CTkSlider(
            scale_row,
            from_=0.5, to=3.0, number_of_steps=50,
            variable=self._scale_var,
            command=self._on_scale_slider,
        )
        self._scale_slider.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        self._scale_entry = ctk.CTkEntry(scale_row, width=60, justify="center")
        self._scale_entry.insert(0, f"{self._scale_var.get():.1f}")
        self._scale_entry.grid(row=0, column=2)
        self._scale_entry.bind("<Return>",   self._on_scale_entry)
        self._scale_entry.bind("<FocusOut>", self._on_scale_entry)

        ctk.CTkLabel(
            scale_row, text=self.t["scale_unit"],
            font=ctk.CTkFont(size=12), width=20,
        ).grid(row=0, column=3, padx=(2, 0))

        # ── Log card ─────────────────────────────────────────────────────────
        log_card = ctk.CTkFrame(main)
        log_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        log_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_hdr, text=self.t["log_label"],
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.open_folder_btn = ctk.CTkButton(
            log_hdr, text=self.t["open_folder"],
            width=180, command=self._open_output_folder, state="disabled",
        )
        self.open_folder_btn.grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_card, font=ctk.CTkFont(size=12), state="disabled")
        self.log_box.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="nsew")

        # ── Progress + generate ───────────────────────────────────────────────
        action_row = ctk.CTkFrame(main, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        action_row.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(action_row)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.generate_btn = ctk.CTkButton(
            action_row, text=self.t["generate"],
            width=180, font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_generate,
        )
        self.generate_btn.grid(row=0, column=1)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=11), anchor="w")
        self.status_label.grid(row=0, column=0, padx=12, sticky="w")

        self.count_label = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=11), anchor="e")
        self.count_label.grid(row=0, column=1, padx=12, sticky="e")

    def _build_footer(self):
        bar = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color=("gray80", "#111111"))
        bar.grid(row=4, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.grid(row=0, column=0, pady=3)

        def _lbl(text, **kw):
            return ctk.CTkLabel(inner, text=text, font=ctk.CTkFont(size=10), **kw)

        def _link(text, url):
            lbl = ctk.CTkLabel(
                inner, text=text,
                font=ctk.CTkFont(size=10, underline=True),
                text_color=("#0066cc", "#4fc3f7"),
                cursor="hand2",
            )
            lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
            return lbl

        _lbl("Wszelkie prawa zastrzeżone © 2026  |  by ").pack(side="left")
        _link("dCoded", "https://www.dcoded.pl").pack(side="left")
        _lbl(" & ").pack(side="left")
        _link("id3ntity", "https://www.id3ntity.pl").pack(side="left")

    # ── Scale slider handlers ─────────────────────────────────────────────────

    def _on_scale_slider(self, value: float):
        rounded = round(value, 1)
        self._scale_entry.delete(0, "end")
        self._scale_entry.insert(0, f"{rounded:.1f}")
        self.settings["scale"] = rounded

    def _on_scale_entry(self, _event=None):
        try:
            val = float(self._scale_entry.get().replace(",", "."))
            val = max(0.5, min(3.0, round(val, 1)))
            self._scale_var.set(val)
            self._scale_entry.delete(0, "end")
            self._scale_entry.insert(0, f"{val:.1f}")
            self.settings["scale"] = val
        except ValueError:
            # restore slider value on bad input
            self._scale_entry.delete(0, "end")
            self._scale_entry.insert(0, f"{self._scale_var.get():.1f}")

    # ── Actions ──────────────────────────────────────────────────────────────

    def _import_excel(self):
        path = filedialog.askopenfilename(
            title=self.t["import_excel"],
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.worksheets[0]
            codes = [
                str(row[0]).strip()
                for row in ws.iter_rows(min_row=1, values_only=True)
                if row and row[0] is not None and str(row[0]).strip()
            ]
            wb.close()
            existing = [c for c in self.code_input.get("1.0", "end").splitlines() if c.strip()]
            self.code_input.delete("1.0", "end")
            self.code_input.insert("1.0", "\n".join(existing + codes))
            self._set_status(self.t["excel_loaded"].format(n=len(codes), file=Path(path).name))
        except Exception as e:
            messagebox.showerror(APP_NAME, f"{self.t['excel_error']}\n{e}")

    def _clear_input(self):
        self.code_input.delete("1.0", "end")
        self._log_clear()
        self.progress_bar.set(0)
        self._set_status("")
        self.count_label.configure(text="")
        self.open_folder_btn.configure(state="disabled")
        self._last_result = None

    def _on_generate(self):
        raw   = self.code_input.get("1.0", "end").strip()
        codes = [c.strip() for c in raw.splitlines() if c.strip()]

        if not codes:
            messagebox.showwarning(APP_NAME, self.t["no_codes"])
            return
        if len(codes) > 100:
            messagebox.showwarning(APP_NAME, self.t["too_many"].format(n=len(codes)))
            return

        # Duplicates
        seen, dupes, unique = set(), [], []
        for c in codes:
            if c in seen:
                if c not in dupes:
                    dupes.append(c)
            else:
                seen.add(c); unique.append(c)

        if dupes:
            if not messagebox.askyesno(APP_NAME,
                    self.t["duplicates_found"].format(codes=", ".join(dupes))):
                return
            codes = unique

        try:
            out_dir = self._resolve_output_dir()
        except OSError as e:
            # Invalid/unavailable output path (bad drive, no permission, etc.).
            # In a --windowed exe an unhandled error would silently do nothing.
            messagebox.showerror(APP_NAME, f"{self.t['output_dir_error']}\n{e}")
            return

        # Check against the SAME sanitized name the generator will write, so the
        # overwrite prompt also fires for codes containing / \ : * ? " < > |.
        existing_files = [c for c in codes if (out_dir / f"{safe_filename(c)}.png").exists()]
        if existing_files:
            ex = ", ".join(existing_files[:3]) + ("..." if len(existing_files) > 3 else "")
            if not messagebox.askyesno(APP_NAME,
                    self.t["files_exist"].format(n=len(existing_files), examples=ex)):
                return

        # Save current scale before generating
        save_settings(self.settings)
        self._run_generation(codes, out_dir)

    def _run_generation(self, codes: list, out_dir: Path):
        self.generate_btn.configure(state="disabled")
        self._log_clear()
        self.progress_bar.set(0)
        self.open_folder_btn.configure(state="disabled")
        self._last_out_dir = out_dir

        s = dict(self.settings)  # snapshot COPY — mid-run slider/settings changes
                                 # must not affect codes already queued in this batch

        def worker():
            errors = []
            total  = len(codes)
            for i, code in enumerate(codes, 1):
                try:
                    self.generator.generate(
                        code=code, out_dir=out_dir,
                        height=s["height"], distance=s["distance"],
                        font_size=s["font_size"], dpi=int(s["dpi"]),
                        scale=s.get("scale", 1.0),
                    )
                    # Tkinter is not thread-safe — marshal every UI update onto
                    # the main thread via after(0, ...)
                    self.after(0, lambda c=code: self._log(f"[OK] {c}"))
                except Exception as e:            # BarcodeError is a subclass of Exception
                    errors.append((code, str(e)))
                    self.after(0, lambda c=code, err=str(e): self._log(f"[ERR] {c} — {err}"))
                self.after(0, lambda v=i / total: self.progress_bar.set(v))
            self.after(0, lambda: self._on_generation_done(total, errors, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    def _on_generation_done(self, total: int, errors: list, out_dir: Path):
        ok = total - len(errors)
        self._last_result = (ok, total)
        self.generate_btn.configure(state="normal")
        self.open_folder_btn.configure(state="normal")
        self.count_label.configure(text=self.t["result_count"].format(ok=ok, total=total))
        self._set_status(self.t["done"])
        if errors:
            self._log("─" * 40)
            self._log(self.t["errors_summary"].format(n=len(errors)))
            for code, msg in errors:
                self._log(f"  • {code}: {msg}")

    def _open_output_folder(self):
        if hasattr(self, "_last_out_dir") and self._last_out_dir.exists():
            os.startfile(str(self._last_out_dir))

    # ── Help / manual window ──────────────────────────────────────────────────

    def _open_help(self):
        # Reuse an already-open manual window instead of stacking duplicates.
        if getattr(self, "_help_win", None) is not None and self._help_win.winfo_exists():
            self._help_win.lift()
            self._help_win.focus()
            return

        win = ctk.CTkToplevel(self)
        self._help_win = win
        win.title(self.t["help_title"])
        win.geometry("640x560")
        win.minsize(520, 400)
        try:
            win.iconbitmap(str(resource_path("icon.ico")))
        except Exception:
            pass
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(0, weight=1)
        # Defer grab_set: on Windows a Toplevel must be viewable first, otherwise
        # grab_set() can raise and leave the window unusable.
        win.after(200, lambda: win.grab_set() if win.winfo_exists() else None)

        box = ctk.CTkTextbox(win, font=ctk.CTkFont(size=13), wrap="word")
        box.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        box.insert("1.0", self.t["help_body"])
        box.configure(state="disabled")

        ctk.CTkButton(
            win, text=self.t["help_close"], width=120, command=win.destroy,
        ).grid(row=1, column=0, pady=(0, 16))

    # ── Settings window ───────────────────────────────────────────────────────

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t["settings"])
        win.geometry("480x360")
        win.resizable(False, False)
        win.grab_set()
        win.grid_columnconfigure(1, weight=1)

        pad = {"padx": 20, "pady": 7}

        def lbl(text, row_i):
            ctk.CTkLabel(win, text=text, anchor="w", width=170).grid(
                row=row_i, column=0, sticky="w", **pad)

        # Output dir
        lbl(self.t["output_dir"], 0)
        dir_var = tk.StringVar(value=self.settings["output_dir"])
        ctk.CTkEntry(win, textvariable=dir_var).grid(row=0, column=1, sticky="ew", **pad)
        ctk.CTkButton(
            win, text="...", width=36,
            command=lambda: dir_var.set(filedialog.askdirectory() or dir_var.get()),
        ).grid(row=0, column=2, padx=(0, 20), pady=7)

        fields = [
            ("height",    self.t["param_height"],    1),
            ("distance",  self.t["param_distance"],  2),
            ("font_size", self.t["param_font_size"], 3),
            ("dpi",       self.t["param_dpi"],       4),
        ]
        vars_: dict = {}
        for key, label, r in fields:
            lbl(label, r)
            v = tk.StringVar(value=str(self.settings[key]))
            vars_[key] = v
            ctk.CTkEntry(win, textvariable=v, width=120).grid(row=r, column=1, sticky="w", **pad)

        def _save():
            try:
                height    = float(vars_["height"].get())
                distance  = float(vars_["distance"].get())
                font_size = float(vars_["font_size"].get())
                dpi       = int(vars_["dpi"].get())
                # Guard against values that would crash the generator
                # (e.g. dpi=0 → division by zero, non-positive sizes)
                if height <= 0 or distance <= 0 or font_size <= 0 or dpi <= 0:
                    raise ValueError("out of range")
                self.settings["output_dir"] = dir_var.get().strip()
                self.settings["height"]     = height
                self.settings["distance"]   = distance
                self.settings["font_size"]  = font_size
                self.settings["dpi"]        = dpi
                save_settings(self.settings)
                win.destroy()
            except ValueError:
                messagebox.showerror(APP_NAME, self.t["invalid_params"], parent=win)

        def _reset_defaults():
            if not messagebox.askyesno(APP_NAME, self.t["reset_confirm"], parent=win):
                return
            win.destroy()
            self.settings = dict(DEFAULT_SETTINGS)
            save_settings(self.settings)
            ctk.set_appearance_mode(self.settings["theme"])
            self.lang = self.settings["language"]
            self.t    = LANG[self.lang]
            # Full rebuild: refreshes labels for the (possibly changed) language,
            # the theme button icon and the size slider — codes/results survive.
            self._rebuild_ui()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.grid(row=5, column=0, columnspan=3, pady=20)
        ctk.CTkButton(btn_row, text=self.t["save"], command=_save, width=120).pack(
            side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row, text=self.t["reset_defaults"], command=_reset_defaults,
            width=150, fg_color="#555", hover_color="#444",
        ).pack(side="left")

    # ── Language ──────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        self.lang = "EN" if self.lang == "PL" else "PL"
        self.settings["language"] = self.lang
        save_settings(self.settings)
        self.t = LANG[self.lang]
        self._rebuild_ui()

    def _rebuild_ui(self):
        # Preserve session state — rebuilding the UI recreates every widget,
        # which would otherwise wipe the typed codes AND the results of the
        # last generation (log, progress, counter). Used by the language
        # toggle and by "restore defaults".
        preserved    = self.code_input.get("1.0", "end").strip()
        log_text     = self.log_box.get("1.0", "end").rstrip("\n")
        progress     = self.progress_bar.get()
        folder_state = self.open_folder_btn.cget("state")
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
        if preserved:
            self.code_input.insert("1.0", preserved)
        if log_text:
            self._log(log_text)
        self.progress_bar.set(progress)
        self.open_folder_btn.configure(state=folder_state)
        # Counter/status re-rendered from raw numbers so they appear in the
        # currently selected language
        if self._last_result is not None:
            ok, total = self._last_result
            self.count_label.configure(text=self.t["result_count"].format(ok=ok, total=total))
            self._set_status(self.t["done"])

    def _other_lang(self) -> str:
        return "EN" if self.lang == "PL" else "PL"

    def _toggle_theme(self):
        current = self.settings.get("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        self.settings["theme"] = new_theme
        save_settings(self.settings)
        ctk.set_appearance_mode(new_theme)
        self.theme_btn.configure(text=self._theme_icon())

    def _theme_icon(self) -> str:
        return "☀" if self.settings.get("theme", "dark") == "dark" else "☾"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_output_dir(self) -> Path:
        base = self.settings.get("output_dir", "").strip()
        base = Path(base) if base else app_dir() / "output"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _set_status(self, msg: str):
        self.status_label.configure(text=f"  {msg}")

    def _log(self, msg: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_clear(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
