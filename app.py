import io, math, uuid, os, hmac, datetime, base64
import pandas as pd
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, session, abort
from storage import get_store

ON_VERCEL = bool(os.environ.get("VERCEL"))
HOSTED = ON_VERCEL or bool(os.environ.get("RENDER"))

# On Vercel, static files are served from public/ by the CDN (URL stays /static/...).
app = Flask(__name__, static_folder="public/static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
if ON_VERCEL and (app.secret_key == "dev-only-change-me"
                  or not os.environ.get("APP_USERNAME") or not os.environ.get("APP_PASSWORD")):
    raise RuntimeError("Set SECRET_KEY, APP_USERNAME and APP_PASSWORD in Vercel > Settings > Environment Variables, then redeploy.")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_SECURE=HOSTED,
                  PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=7))
store = get_store()
OWNER_USER = os.environ.get("APP_USERNAME", "admin")
OWNER_PASS = os.environ.get("APP_PASSWORD", "admin")
FAILS = {}

@app.before_request
def require_login():
    if request.endpoint in ("login", "static") or session.get("owner"):
        return
    if request.path.startswith("/api/"):
        abort(401)
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        n, t = FAILS.get(ip, (0, 0))
        if n >= 5 and datetime.datetime.now().timestamp() - t < 300:
            flash("Too many attempts. Wait 5 minutes."); return render_template("login.html")
        ok = hmac.compare_digest(request.form.get("username", ""), OWNER_USER) & hmac.compare_digest(request.form.get("password", ""), OWNER_PASS)
        if ok:
            FAILS.pop(ip, None); session.clear(); session["owner"] = True; session.permanent = True
            return redirect(url_for("ledger"))
        FAILS[ip] = (n + 1, datetime.datetime.now().timestamp()); flash("Wrong username or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/api/funds", methods=["GET", "POST"])
def api_funds():
    if request.method == "POST":
        name = (request.get_json(force=True).get("name") or "").strip()[:80]
        if not name: return {"error": "Name required"}, 400
        return {"id": store.create(name)}
    return {"funds": store.list_funds()}

@app.route("/api/funds/<fid>", methods=["GET", "PUT", "PATCH", "DELETE"])
def api_fund(fid):
    f = store.get(fid)
    if not f: return {"error": "Not found"}, 404
    if request.method == "PUT":
        rows = request.get_json(force=True).get("rows", [])
        if not isinstance(rows, list) or len(rows) > 5000: return {"error": "Bad data"}, 400
        clean = [{k: str(r.get(k, ""))[:200] for k in ("date", "description", "category", "type", "amount", "tax")} for r in rows]
        store.save_rows(fid, clean); return {"ok": True}
    if request.method == "PATCH":
        store.rename(fid, (request.get_json(force=True).get("name") or f["name"]).strip()[:80]); return {"ok": True}
    if request.method == "DELETE":
        store.delete(fid); return {"ok": True}
    return {"name": f["name"], "rows": f.get("rows", [])}
app.config["MAX_CONTENT_LENGTH"] = (4 if ON_VERCEL else 20) * 1024 * 1024  # Vercel caps request bodies at ~4.5 MB
REPORTS = {}

ALIASES = {
    "date": ["date", "transaction_date", "txn_date", "posted"],
    "amount": ["amount", "value", "total", "debit", "sum"],
    "vendor": ["vendor", "payee", "supplier", "merchant", "customer"],
    "invoice": ["invoice", "invoice_no", "id", "reference", "ref"],
    "description": ["description", "memo", "details", "narration"],
}

def detect(df):
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    return {k: next((cols[a] for a in v if a in cols), None) for k, v in ALIASES.items()}

def read_file(f):
    name = f.filename.lower()
    if name.endswith(".csv"):
        return pd.read_csv(f)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    raise ValueError("Please upload a .csv or .xlsx file")

def audit(df):
    m = detect(df)
    if not m["amount"]:
        raise ValueError("Could not find an 'amount' column")
    df = df.copy()
    df.insert(0, "Row", range(2, len(df) + 2))
    amt = pd.to_numeric(df[m["amount"]], errors="coerce")
    flags = {}

    def add(mask, label):
        for i in df.index[mask.fillna(False)]:
            flags.setdefault(i, []).append(label)

    key = [c for c in (m["date"], m["amount"], m["vendor"], m["invoice"]) if c]
    add(df.duplicated(subset=key, keep=False), "Duplicate")
    if m["invoice"]:
        add(df[m["invoice"]].notna() & df.duplicated(subset=[m["invoice"]], keep=False), "Duplicate invoice #")
    add(df.drop(columns="Row").isna().any(axis=1), "Missing data")
    add(amt.isna() & df[m["amount"]].notna(), "Non-numeric amount")
    add(amt < 0, "Negative amount")
    if amt.notna().sum() > 3:
        q1, q3 = amt.quantile([.25, .75]); iqr = q3 - q1
        add((amt > q3 + 3 * iqr) | (amt < q1 - 3 * iqr), "Outlier")
    add((amt.abs() >= 1000) & (amt % 1000 == 0), "Round number")
    if m["date"]:
        d = pd.to_datetime(df[m["date"]], errors="coerce")
        add(d.dt.dayofweek >= 5, "Weekend")
        add(d > pd.Timestamp.now(), "Future date")

    flagged = df.loc[list(flags)].copy()
    flagged.insert(1, "Issues", [", ".join(flags[i]) for i in flagged.index])
    flagged = flagged.sort_values("Row")

    counts = {}
    for v in flags.values():
        for l in v: counts[l] = counts.get(l, 0) + 1

    digits = amt.abs()[amt.abs() >= 1].astype(str).str.lstrip("0.").str[0]
    digits = digits[digits.str.isdigit() & (digits != "0")].astype(int)
    n = len(digits)
    benford = pd.DataFrame({
        "Digit": range(1, 10),
        "Expected %": [round(math.log10(1 + 1 / d) * 100, 1) for d in range(1, 10)],
        "Actual %": [round((digits == d).sum() / n * 100, 1) if n else 0 for d in range(1, 10)],
    })
    benford["Deviation"] = (benford["Actual %"] - benford["Expected %"]).round(1)

    summary = {
        "Total rows": len(df),
        "Flagged rows": len(flagged),
        "Total amount": round(float(amt.sum()), 2),
        "Flagged amount": round(float(amt.loc[flagged.index].sum()), 2),
        "Average": round(float(amt.mean()), 2) if amt.notna().any() else 0,
        "Largest": round(float(amt.max()), 2) if amt.notna().any() else 0,
    }
    return summary, counts, flagged, benford, df

@app.route("/")
def ledger():
    return render_template("ledger.html", owner_name=OWNER_USER)

@app.route("/upload")
def index():
    return render_template("index.html")

def tax_pct(v):
    x = pd.to_numeric(v, errors="coerce")
    if pd.isna(x): return 0
    return round(float(x) * 100, 2) if 0 < x < 1 else float(x)

@app.route("/ledger/import", methods=["POST"])
def ledger_import():
    f = request.files.get("file")
    try:
        df = read_file(f)
    except Exception as e:
        return {"error": str(e)}, 400
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    def pick(*names):
        return next((cols[n] for n in names if n in cols), None)
    m = {"date": pick("date","transaction_date"), "description": pick("description","memo","details"),
         "category": pick("category","account"), "type": pick("type","kind"),
         "amount": pick("amount","value","total"), "tax": pick("tax_%","tax_rate","tax")}
    rows = []
    for _, r in df.iterrows():
        g = lambda k: ("" if not m[k] or pd.isna(r[m[k]]) else r[m[k]])
        d = g("date")
        d = pd.to_datetime(d, errors="coerce").strftime("%Y-%m-%d") if d != "" and not pd.isna(pd.to_datetime(d, errors="coerce")) else ""
        a = pd.to_numeric(g("amount"), errors="coerce")
        t = str(g("type")).lower()
        rows.append({"date": d, "description": str(g("description")), "category": str(g("category")),
                     "type": "income" if t.startswith("inc") else "expense",
                     "amount": "" if pd.isna(a) else float(abs(a)), "tax": tax_pct(g("tax"))})
    return {"rows": rows}

@app.route("/ledger/export", methods=["POST"])
def ledger_export():
    rows = request.get_json(force=True).get("rows", [])
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "Ledger"
    hdr = ["Date","Description","Category","Type","Amount","Tax %","Tax","Total","Signed Total"]
    ws.append(hdr)
    for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", start_color="1F4E3D")
    for i, r in enumerate(rows, start=2):
        ws.append([r.get("date"), r.get("description"), r.get("category"), r.get("type"),
                   float(r.get("amount") or 0), float(r.get("tax") or 0) / 100,
                   f"=E{i}*F{i}", f"=E{i}+G{i}", f'=IF(D{i}="income",H{i},-H{i})'])
        for col in "EGHI": ws[f"{col}{i}"].number_format = "#,##0.00;(#,##0.00);-"
        ws[f"F{i}"].number_format = "0.0%"
    n = len(rows) + 1
    s = wb.create_sheet("Summary")
    for row in [("Total income", f'=SUMIF(Ledger!D2:D{n},"income",Ledger!H2:H{n})'),
                ("Total expenses", f'=SUMIF(Ledger!D2:D{n},"expense",Ledger!H2:H{n})'),
                ("Net", "=B1-B2"), ("Total tax", f"=SUM(Ledger!G2:G{n})"),
                ("Transactions", f"=COUNTA(Ledger!A2:A{n})")]:
        s.append(row)
    for r in range(1, 5): s[f"B{r}"].number_format = "#,##0.00;(#,##0.00);-"
    for w in (ws, s):
        for col in w.columns: w.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="ledger.xlsx")

@app.route("/audit", methods=["POST"])
def run_audit():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Choose a file first"); return redirect(url_for("index"))
    try:
        summary, counts, flagged, benford, data = audit(read_file(f))
    except Exception as e:
        flash(str(e)); return redirect(url_for("index"))
    rid = uuid.uuid4().hex
    REPORTS[rid] = (summary, counts, flagged, benford, data, f.filename)
    if len(REPORTS) > 50: REPORTS.pop(next(iter(REPORTS)))
    # Serverless instances don't share memory, so also embed the Excel report in the page itself.
    dl = None
    try:
        raw = build_report_xlsx(summary, counts, flagged, benford, data).getvalue()
        if len(raw) <= 2_500_000:
            dl = "data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64," + base64.b64encode(raw).decode()
    except Exception:
        dl = None
    return render_template("report.html", rid=rid, dl=dl, dl_name=f"audit_{f.filename.rsplit('.',1)[0]}.xlsx", summary=summary, counts=counts,
        flagged=flagged.head(500).fillna("").to_dict("records"), cols=list(flagged.columns),
        benford=benford.to_dict("records"), filename=f.filename)

def build_report_xlsx(summary, counts, flagged, benford, data):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(list(summary.items()), columns=["Metric", "Value"]).to_excel(w, sheet_name="Summary", index=False)
        pd.DataFrame(list(counts.items()), columns=["Issue", "Count"]).to_excel(w, sheet_name="Issue Counts", index=False)
        flagged.to_excel(w, sheet_name="Flagged", index=False)
        benford.to_excel(w, sheet_name="Benford", index=False)
        data.to_excel(w, sheet_name="All Data", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(40, max(len(str(c.value or "")) for c in col) + 2)
    buf.seek(0)
    return buf

@app.route("/export/<rid>")
def export(rid):
    if rid not in REPORTS: return redirect(url_for("index"))
    summary, counts, flagged, benford, data, name = REPORTS[rid]
    return send_file(build_report_xlsx(summary, counts, flagged, benford, data), as_attachment=True, download_name=f"audit_{name.rsplit('.',1)[0]}.xlsx")

@app.route("/sample")
def sample():
    df = pd.DataFrame({
        "Date": ["2026-01-05","2026-01-06","2026-01-06","2026-01-10","2026-01-12","2026-01-15","2026-01-18","2026-01-20"],
        "Invoice": ["INV-001","INV-002","INV-002","INV-003","INV-004","INV-005","INV-006","INV-007"],
        "Vendor": ["Acme","Globex","Globex","Initech","Acme",None,"Umbrella","Acme"],
        "Description": ["Supplies","Consulting","Consulting","Software","Supplies","Travel","Repairs","Supplies"],
        "Amount": [245.50, 1800.00, 1800.00, 5000, 312.75, 189.20, 98000, -45.00],
    })
    buf = io.BytesIO(); df.to_excel(buf, index=False); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="sample_transactions.xlsx")

if __name__ == "__main__":
    app.run(debug=not HOSTED)
