"""
BarcodeGen — Desktop barcode generator (EAN-13 / Code128)
"""

import os
import sys
import json
import threading
import datetime
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
from PIL import Image as PILImage

from generator import BarcodeGenerator, BarcodeError
from lang import LANG

# ─── Constants ───────────────────────────────────────────────────────────────

APP_NAME = "BarcodeGen"
VERSION = "1.0.0"
DEFAULT_SETTINGS = {
    "output_dir": "",
    "height": 9.0,
    "distance": 0.15,
    "font_size": 1.3,
    "dpi": 300,
    "language": "PL",
}

# ─── Path helpers (PyInstaller-safe) ─────────────────────────────────────────

def resource_path(name: str) -> Path:
    """Path to a bundled asset — works both in dev and frozen .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / name
    return Path(__file__).parent / name


def app_dir() -> Path:
    """Directory of the running .exe (or script during development).
    Used for settings.json and default output folder so they survive
    PyInstaller's temp-dir unpacking.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


SETTINGS_FILE = app_dir() / "settings.json"

# ─── Settings ────────────────────────────────────────────────────────────────

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_SETTINGS, **data}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


# ─── Main Application ────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        self.lang = self.settings["language"]
        self.t = LANG[self.lang]
        self.generator = BarcodeGenerator()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("860x640")
        self.minsize(800, 580)
        self.resizable(True, True)

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_main()
        self._build_statusbar()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=56, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)  # spacer column expands

        col = 0

        # Logo image
        try:
            pil_logo = PILImage.open(resource_path("logo.png")).resize((38, 38), PILImage.LANCZOS)
            ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(38, 38))
            ctk.CTkLabel(bar, image=ctk_logo, text="").grid(
                row=0, column=col, padx=(10, 2), pady=8
            )
            col += 1
        except Exception:
            pass  # logo file missing — skip silently

        # App title
        ctk.CTkLabel(
            bar,
            text=APP_NAME,
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=col, padx=(4, 12), pady=8, sticky="w")

        # Spacer (column 2 is weight=1)

        # Right-side buttons
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=3, padx=12, pady=8, sticky="e")

        self.lang_btn = ctk.CTkButton(
            btn_frame, text=self._other_lang(),
            width=60, command=self._toggle_lang,
        )
        self.lang_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text=self.t["settings"],
            width=100, command=self._open_settings,
        ).pack(side="left")

    def _build_main(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=16, pady=(12, 0))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # ── Input area ──
        input_card = ctk.CTkFrame(main)
        input_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            input_card,
            text=self.t["input_label"],
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.code_input = ctk.CTkTextbox(input_card, height=140, font=ctk.CTkFont(size=13))
        self.code_input.grid(row=1, column=0, padx=14, pady=(0, 6), sticky="ew")

        btn_row = ctk.CTkFrame(input_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=14, pady=(0, 6), sticky="w")

        ctk.CTkButton(
            btn_row, text=self.t["import_excel"],
            width=180, command=self._import_excel,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text=self.t["clear"],
            width=90, fg_color="#555", hover_color="#444",
            command=self._clear_input,
        ).pack(side="left")

        # Excel hint label
        ctk.CTkLabel(
            input_card,
            text=self.t["excel_hint"],
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            anchor="w",
            wraplength=780,
            justify="left",
        ).grid(row=3, column=0, padx=14, pady=(0, 10), sticky="w")

        # ── Log / results ──
        log_card = ctk.CTkFrame(main)
        log_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        log_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_hdr,
            text=self.t["log_label"],
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.open_folder_btn = ctk.CTkButton(
            log_hdr,
            text=self.t["open_folder"],
            width=180,
            command=self._open_output_folder,
            state="disabled",
        )
        self.open_folder_btn.grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_card, font=ctk.CTkFont(size=12), state="disabled")
        self.log_box.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="nsew")

        # ── Progress + generate ──
        action_row = ctk.CTkFrame(main, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        action_row.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(action_row)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.generate_btn = ctk.CTkButton(
            action_row,
            text=self.t["generate"],
            width=180,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_generate,
        )
        self.generate_btn.grid(row=0, column=1)

    def _build_statusbar(self):
        bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            bar, text="", font=ctk.CTkFont(size=11), anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=12, sticky="w")

        self.count_label = ctk.CTkLabel(
            bar, text="", font=ctk.CTkFont(size=11), anchor="e"
        )
        self.count_label.grid(row=0, column=1, padx=12, sticky="e")

    # ── Actions ──────────────────────────────────────────────────────────────

    def _import_excel(self):
        path = filedialog.askopenfilename(
            title=self.t["import_excel"],
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.worksheets[0]
            codes = []
            for row in ws.iter_rows(min_row=1, values_only=True):
                val = row[0] if row else None
                if val is not None:
                    stripped = str(val).strip()
                    if stripped:
                        codes.append(stripped)
            wb.close()

            existing = self.code_input.get("1.0", "end").strip()
            existing_codes = [c for c in existing.splitlines() if c.strip()]
            merged = existing_codes + codes
            self.code_input.delete("1.0", "end")
            self.code_input.insert("1.0", "\n".join(merged))

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

    def _on_generate(self):
        raw = self.code_input.get("1.0", "end").strip()
        codes = [c.strip() for c in raw.splitlines() if c.strip()]

        if not codes:
            messagebox.showwarning(APP_NAME, self.t["no_codes"])
            return

        if len(codes) > 100:
            messagebox.showwarning(APP_NAME, self.t["too_many"].format(n=len(codes)))
            return

        # Detect duplicates
        seen: set = set()
        dupes: list = []
        unique_codes: list = []
        for c in codes:
            if c in seen:
                if c not in dupes:
                    dupes.append(c)
            else:
                seen.add(c)
                unique_codes.append(c)

        if dupes:
            msg = self.t["duplicates_found"].format(codes=", ".join(dupes))
            if not messagebox.askyesno(APP_NAME, msg):
                return
            codes = unique_codes

        out_dir = self._resolve_output_dir()

        # Check for existing files
        existing_files = [c for c in codes if (out_dir / f"{c}.png").exists()]
        if existing_files:
            examples = ", ".join(existing_files[:3]) + ("..." if len(existing_files) > 3 else "")
            msg = self.t["files_exist"].format(n=len(existing_files), examples=examples)
            if not messagebox.askyesno(APP_NAME, msg):
                return

        self._run_generation(codes, out_dir)

    def _run_generation(self, codes: list, out_dir: Path):
        self.generate_btn.configure(state="disabled")
        self._log_clear()
        self.progress_bar.set(0)
        self.open_folder_btn.configure(state="disabled")
        self._last_out_dir = out_dir

        def worker():
            errors = []
            total = len(codes)

            for i, code in enumerate(codes, 1):
                try:
                    self.generator.generate(
                        code=code,
                        out_dir=out_dir,
                        height=self.settings["height"],
                        distance=self.settings["distance"],
                        font_size=self.settings["font_size"],
                        dpi=self.settings["dpi"],
                    )
                    self._log(f"[OK] {code}")
                except BarcodeError as e:
                    errors.append((code, str(e)))
                    self._log(f"[ERR] {code} — {e}")
                except Exception as e:
                    errors.append((code, str(e)))
                    self._log(f"[ERR] {code} — {e}")

                self.after(0, lambda v=i / total: self.progress_bar.set(v))

            self.after(0, lambda: self._on_generation_done(total, errors, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    def _on_generation_done(self, total: int, errors: list, out_dir: Path):
        ok = total - len(errors)
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

    # ── Settings window ───────────────────────────────────────────────────────

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title(self.t["settings"])
        win.geometry("480x380")
        win.resizable(False, False)
        win.grab_set()

        win.grid_columnconfigure(1, weight=1)  # entry column expands

        pad = {"padx": 20, "pady": 7}

        def label(text, row_i):
            ctk.CTkLabel(win, text=text, anchor="w", width=160).grid(
                row=row_i, column=0, sticky="w", **pad
            )

        # Output dir
        label(self.t["output_dir"], 0)
        dir_var = tk.StringVar(value=self.settings["output_dir"])
        ctk.CTkEntry(win, textvariable=dir_var).grid(
            row=0, column=1, sticky="ew", **pad
        )
        ctk.CTkButton(
            win, text="...", width=36,
            command=lambda: dir_var.set(filedialog.askdirectory() or dir_var.get()),
        ).grid(row=0, column=2, padx=(0, 20), pady=7)

        # Numeric params
        fields = [
            ("height",    self.t["param_height"],    1),
            ("distance",  self.t["param_distance"],  2),
            ("font_size", self.t["param_font_size"], 3),
            ("dpi",       self.t["param_dpi"],       4),
        ]
        vars_: dict = {}
        for key, lbl, r in fields:
            label(lbl, r)
            v = tk.StringVar(value=str(self.settings[key]))
            vars_[key] = v
            ctk.CTkEntry(win, textvariable=v, width=120).grid(
                row=r, column=1, sticky="w", **pad
            )

        def _save():
            try:
                self.settings["output_dir"] = dir_var.get().strip()
                self.settings["height"] = float(vars_["height"].get())
                self.settings["distance"] = float(vars_["distance"].get())
                self.settings["font_size"] = float(vars_["font_size"].get())
                self.settings["dpi"] = int(vars_["dpi"].get())
                save_settings(self.settings)
                win.destroy()
            except ValueError:
                messagebox.showerror(APP_NAME, self.t["invalid_params"], parent=win)

        ctk.CTkButton(win, text=self.t["save"], command=_save, width=120).grid(
            row=5, column=0, columnspan=3, pady=20
        )

    # ── Language ──────────────────────────────────────────────────────────────

    def _toggle_lang(self):
        self.lang = "EN" if self.lang == "PL" else "PL"
        self.settings["language"] = self.lang
        save_settings(self.settings)
        self.t = LANG[self.lang]
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()

    def _other_lang(self) -> str:
        return "EN" if self.lang == "PL" else "PL"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_output_dir(self) -> Path:
        base = self.settings.get("output_dir", "").strip()
        base = Path(base) if base else app_dir() / "output"
        dated = base / datetime.date.today().isoformat()
        dated.mkdir(parents=True, exist_ok=True)
        return dated

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
