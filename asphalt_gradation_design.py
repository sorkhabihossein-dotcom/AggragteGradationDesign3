"""
Asphalt Gradation Design (Packing Theory + Volumetrics)
Implements: Yu, Shen, Qian, Gong (2020), J. Mater. Civ. Eng. 32(6): 04020110
Valid for dense-graded mixes, NMPS = 12.5 mm (fv tables from the paper, Table 2).
"""
import csv
import itertools
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ----------------------------------------------------------------- core ---
SIEVES = [19, 12.5, 9.5, 4.75, 2.36, 1.18, 0.6, 0.3, 0.15, 0.075]
DMAX = 19.0
# Table 2 (12.5 mm NMPS)
FV = {
    "Coarse-graded": [0.411, 0.411, 0.411, 0.410, 0.169, -0.366, -0.366, -0.366, -0.536, -0.952],
    "Medium-graded": [0.436, 0.436, 0.436, 0.436, 0.178, -0.405, -0.405, -0.430, -0.589, -0.899],
    "Fine-graded":   [0.455, 0.455, 0.455, 0.455, 0.174, 0.107, -0.035, -0.397, -0.568, -0.755],
}
# Superpave control points, 12.5 mm NMS: sieve -> (min, max)
CONTROL = {12.5: (90, 100), 2.36: (28, 58), 0.075: (2, 10)}


def blend(stock, props):
    """Combine stockpile passing (list of 10 lists) with proportions (%)."""
    return [sum(s[i] * p / 100 for s, p in zip(stock, props)) for i in range(len(SIEVES))]


def gradation_type(P):
    pdv = [P[i] - 100 * (d / DMAX) ** 0.45 for i, d in enumerate(SIEVES)]
    pdc = sum(pdv[i] for i in (2, 3, 4, 5))  # 9.5, 4.75, 2.36, 1.18 mm  (Eq. 3)
    t = "Coarse-graded" if pdc <= 0 else ("Medium-graded" if pdc <= 20 else "Fine-graded")
    return pdv, pdc, t


def predict_vma(P, gtype):
    """Eq. 14: p = sum(fv*Va) / (100 + sum(fv*Va)); fv taken from next-larger sieve row."""
    fv = FV[gtype]
    ret, fvs = [], []
    for k in range(1, 10):
        ret.append(P[k - 1] - P[k]); fvs.append(fv[k - 1])
    ret.append(P[9]); fvs.append(fv[9])           # pan
    ret = [0.0] + ret; fvs = [None] + fvs         # 19 mm row has nothing retained
    s = sum(r * f for r, f in zip(ret[1:], fvs[1:]))
    return 100 * s / (100 + s), ret, fvs


def binder(vma, va, gb, gsb, pba):
    vfa = 100 * (1 - va / vma)                    # Eq. 7
    pbe = (vma - va) * gb / gsb                   # Eq. 8
    pb = pbe + pba / 100 * (100 - pbe)            # Eq. 9
    return vfa, pbe, pb


def hirsch(vma, va, g_mpa):
    """Modified Hirsch (Eqs. 10-11). g_mpa = |G*m| in MPa; returns |E*| in MPa."""
    vma_e = vma + 2.5 if va < 7 else vma          # correct VMA to 7 % air-void specimens
    vfa = 100 * (1 - 7.0 / vma_e)
    g = g_mpa * 145.038                           # psi
    x = vfa * 3 * g / vma_e
    pc = (20 + x) ** 0.67 / (10000 + x ** 0.67)
    e = pc * (1e7 * (1 - vma_e / 100) + 3 * g * vfa * vma_e / 10000) + \
        (1 - pc) / ((1 - vma_e / 100) / 1e7 + vma_e / (vfa * 3 * g))
    return e / 145.038, vma_e


def control_ok(P):
    return all(lo <= P[SIEVES.index(d)] <= hi for d, (lo, hi) in CONTROL.items())


def optimise(stock, vma_lo, vma_hi, step=5):
    mid = (vma_lo + vma_hi) / 2
    best = []
    for a in range(0, 101, step):
        for b in range(0, 101 - a, step):
            props = (a, b, 100 - a - b)
            P = blend(stock, props)
            if not control_ok(P):
                continue
            vma = predict_vma(P, gradation_type(P)[2])[0]
            best.append((abs(vma - mid), props, vma))
    best.sort()
    return best[:5]


def analyse(stock, props, gb, gsb, va, pba, gstar=None):
    P = blend(stock, props)
    pdv, pdc, gt = gradation_type(P)
    vma, ret, fvs = predict_vma(P, gt)
    vfa, pbe, pb = binder(vma, va, gb, gsb, pba)
    r = dict(P=P, pd=pdv, pdc=pdc, type=gt, vma=vma, ret=ret, fv=fvs,
             vfa=vfa, pbe=pbe, pb=pb, ctrl=control_ok(P), E=None)
    if gstar:
        r["E"], r["vma_e"] = hirsch(vma, va, gstar)
    return r


# ------------------------------------------------------------------ GUI ---
DEFAULT_STOCK = {
    "X": [100, 99, 60, 2.8, 1.8, 1.6, 1.5, 1.4, 1.3, 1.1],
    "Y": [100, 100, 98, 62, 38, 24, 17, 12, 9, 6.9],
    "Z": [100, 98, 90, 66, 48, 33, 23, 16, 12, 9.8],
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Asphalt Gradation Design – Packing Theory & Volumetrics")
        self.geometry("1280x820")
        self.res = None
        self.cells = {}
        self.vars = {}
        self._build()
        self.calculate()

    def _build(self):
        left = ttk.Frame(self, padding=8); left.pack(side="left", fill="y")
        right = ttk.Frame(self, padding=8); right.pack(side="right", fill="both", expand=True)

        ttk.Label(left, text="1. Stockpile gradations (% passing)", font=("Segoe UI", 10, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w")
        for j, h in enumerate(["Sieve (mm)", "X", "Y", "Z"]):
            ttk.Label(left, text=h).grid(row=1, column=j)
        for i, d in enumerate(SIEVES):
            ttk.Label(left, text=str(d)).grid(row=2 + i, column=0)
            for j, k in enumerate("XYZ"):
                v = tk.StringVar(value=str(DEFAULT_STOCK[k][i]))
                ttk.Entry(left, textvariable=v, width=8, justify="center").grid(row=2 + i, column=1 + j, padx=1, pady=1)
                self.cells[(i, k)] = v
        r = 13
        ttk.Label(left, text="Proportion (%)").grid(row=r, column=0)
        for j, (k, dv) in enumerate(zip("XYZ", (30, 50, 20))):
            v = tk.StringVar(value=str(dv)); self.vars["p" + k] = v
            ttk.Entry(left, textvariable=v, width=8, justify="center").grid(row=r, column=1 + j)

        ttk.Label(left, text="2. Mix parameters", font=("Segoe UI", 10, "bold")).grid(
            row=r + 1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        params = [("Binder Gb", "gb", 1.02), ("Aggregate Gsb", "gsb", 2.680),
                  ("Design air voids Va (%)", "va", 4.0), ("Binder absorption Pba (%)", "pba", 1.0),
                  ("Target VMA min (%)", "vlo", 14.0), ("Target VMA max (%)", "vhi", 16.0),
                  ("Mastic |G*m| (MPa) – optional", "g", "")]
        for n, (lab, key, dv) in enumerate(params):
            ttk.Label(left, text=lab).grid(row=r + 2 + n, column=0, columnspan=2, sticky="w")
            v = tk.StringVar(value=str(dv)); self.vars[key] = v
            ttk.Entry(left, textvariable=v, width=8, justify="center").grid(row=r + 2 + n, column=2, columnspan=2)

        b = r + 10
        ttk.Button(left, text="Calculate", command=self.calculate).grid(row=b, column=0, columnspan=4, sticky="ew", pady=(10, 2))
        ttk.Button(left, text="Optimise proportions (to target VMA)", command=self.optimise).grid(row=b + 1, column=0, columnspan=4, sticky="ew", pady=2)
        ttk.Button(left, text="Export results (CSV)", command=self.export_csv).grid(row=b + 2, column=0, columnspan=4, sticky="ew", pady=2)
        ttk.Button(left, text="Save diagram (PNG)", command=self.save_png).grid(row=b + 3, column=0, columnspan=4, sticky="ew", pady=2)
        ttk.Label(left, text="NMPS 12.5 mm dense-graded mixes only\n(fv values from Table 2 of the paper).",
                  foreground="gray").grid(row=b + 4, column=0, columnspan=4, pady=6)

        self.fig = Figure(figsize=(7, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        cols = ["Sieve", "X", "Y", "Z", "Combined", "MDL", "Pd", "Retained", "fv", "Retained×fv"]
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=11)
        for c in cols:
            self.tree.heading(c, text=c); self.tree.column(c, width=85, anchor="center")
        self.tree.pack(fill="x", pady=(6, 0))
        self.summary = tk.Text(right, height=7, font=("Consolas", 10), state="disabled", bg="#f6f6f6")
        self.summary.pack(fill="x", pady=(6, 0))

    # ---- helpers
    def _read(self):
        try:
            stock = [[float(self.cells[(i, k)].get()) for i in range(10)] for k in "XYZ"]
            props = [float(self.vars["p" + k].get()) for k in "XYZ"]
            f = lambda k: float(self.vars[k].get())
            g = self.vars["g"].get().strip()
            return stock, props, f("gb"), f("gsb"), f("va"), f("pba"), f("vlo"), f("vhi"), (float(g) if g else None)
        except ValueError:
            messagebox.showerror("Input error", "Please enter numeric values in all required fields.")
            return None

    def calculate(self):
        d = self._read()
        if not d:
            return
        stock, props, gb, gsb, va, pba, vlo, vhi, g = d
        if abs(sum(props) - 100) > 0.01:
            messagebox.showwarning("Proportions", "Stockpile proportions must total 100 %.")
            return
        for s in stock:
            if any(s[i] < s[i + 1] for i in range(9)):
                messagebox.showwarning("Gradation", "Each stockpile's % passing must decrease with smaller sieves.")
                return
        self.res = res = analyse(stock, props, gb, gsb, va, pba, g)
        self.stock = stock
        self._plot(res)
        self._table(res, stock)
        ok = "within" if vlo <= res["vma"] <= vhi else "OUTSIDE"
        txt = (f"Gradation type : {res['type']}   (Pdc = {res['pdc']:.1f})\n"
               f"Predicted VMA  : {res['vma']:.1f} %   -> {ok} target {vlo}-{vhi} %\n"
               f"VFA            : {res['vfa']:.1f} %   (Va = {va} %)\n"
               f"Effective binder Pbe : {res['pbe']:.2f} %\n"
               f"Design binder content Pb : {res['pb']:.2f} %\n"
               f"Superpave control points : {'PASS' if res['ctrl'] else 'FAIL'}\n")
        txt += (f"Dynamic modulus |E*| (7% Va specimen, VMA={res['vma_e']:.1f}) : {res['E']:,.0f} MPa"
                if res["E"] else "Dynamic modulus : enter mastic |G*m| to estimate")
        self.summary.config(state="normal"); self.summary.delete("1.0", "end")
        self.summary.insert("end", txt); self.summary.config(state="disabled")

    def _plot(self, res):
        ax = self.ax; ax.clear()
        x = [d ** 0.45 for d in SIEVES]
        ax.plot(x, [100 * (d / DMAX) ** 0.45 for d in SIEVES], "r--", label="Max. density line")
        ax.plot(x, res["P"], "s-", color="tab:blue", label="Design gradation")
        for d, (lo, hi) in CONTROL.items():
            ax.plot([d ** 0.45] * 2, [lo, hi], "k_", markersize=12, mew=2)
            ax.plot([d ** 0.45] * 2, [lo, hi], "k-", lw=1)
        ax.plot([], [], "k-", label="Control points")
        ax.set_xticks(x); ax.set_xticklabels([str(d) for d in SIEVES], rotation=45)
        ax.set_ylim(0, 100); ax.set_xlabel("Sieve size (mm), raised to 0.45"); ax.set_ylabel("Percent passing (%)")
        ax.set_title(f"Aggregate gradation – {res['type']}, VMA = {res['vma']:.1f} %")
        ax.grid(True, ls=":"); ax.legend(loc="upper left"); self.fig.tight_layout(); self.canvas.draw()

    def _table(self, res, stock):
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        for i, d in enumerate(SIEVES):
            mdl = 100 * (d / DMAX) ** 0.45
            fv = res["fv"][i] if i else None
            rt = res["ret"][i] if i else None
            row = [d, *[f"{s[i]:.1f}" for s in stock], f"{res['P'][i]:.1f}", f"{mdl:.1f}", f"{res['pd'][i]:.1f}",
                   "-" if i == 0 else f"{rt:.1f}", "-" if i == 0 else f"{fv:.3f}",
                   "-" if i == 0 else f"{rt * fv:.2f}"]
            self.tree.insert("", "end", values=row); self.rows.append(row)
        pan = res["ret"][-1] if False else res["P"][9]
        row = ["Pan", "", "", "", "", "", "", f"{pan:.1f}", f"{FV[res['type']][9]:.3f}", f"{pan * FV[res['type']][9]:.2f}"]
        self.tree.insert("", "end", values=row); self.rows.append(row)

    def optimise(self):
        d = self._read()
        if not d:
            return
        stock, _, *_rest = d
        vlo, vhi = d[6], d[7]
        top = optimise(stock, vlo, vhi)
        if not top:
            messagebox.showinfo("Optimise", "No blend meets the Superpave control points.")
            return
        _, p, vma = top[0]
        for k, v in zip("XYZ", p):
            self.vars["p" + k].set(str(v))
        self.calculate()
        messagebox.showinfo("Optimise", "Best blend X/Y/Z = %d/%d/%d %%  (predicted VMA %.1f %%)" % (*p, vma))

    def export_csv(self):
        if not self.res:
            return
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if f:
            with open(f, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["Sieve", "X", "Y", "Z", "Combined", "MDL", "Pd", "Retained", "fv", "Retained*fv"])
                w.writerows(self.rows)
                r = self.res
                w.writerow([]); w.writerow(["Type", r["type"]]); w.writerow(["Pdc", round(r["pdc"], 2)])
                w.writerow(["VMA %", round(r["vma"], 2)]); w.writerow(["VFA %", round(r["vfa"], 2)])
                w.writerow(["Pbe %", round(r["pbe"], 2)]); w.writerow(["Pb %", round(r["pb"], 2)])
                if r["E"]:
                    w.writerow(["E* MPa", round(r["E"])])

    def save_png(self):
        f = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if f:
            self.fig.savefig(f, dpi=200)


if __name__ == "__main__":
    App().mainloop()
