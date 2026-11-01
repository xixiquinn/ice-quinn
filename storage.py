"""Fund storage: Firebase Firestore when FIREBASE_CREDENTIALS is set, else a local JSON file (for testing)."""
import json, os, re, time

def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "fund"

class LocalStore:
    # Vercel's filesystem is read-only except /tmp (temporary; use Firebase for real data).
    path = "/tmp/local_db.json" if os.environ.get("VERCEL") else "local_db.json"
    def _load(self):
        return json.load(open(self.path)) if os.path.exists(self.path) else {}
    def _save(self, d):
        json.dump(d, open(self.path, "w"))
    def list_funds(self):
        return sorted(({"id": k, "name": v["name"], "count": len(v["rows"])} for k, v in self._load().items()), key=lambda f: f["name"])
    def get(self, fid):
        return self._load().get(fid)
    def create(self, name):
        d = self._load(); fid = _slug(name)
        while fid in d: fid += "-1"
        d[fid] = {"name": name, "rows": [], "updated": time.time()}; self._save(d); return fid
    def save_rows(self, fid, rows):
        d = self._load(); d[fid]["rows"] = rows; d[fid]["updated"] = time.time(); self._save(d)
    def rename(self, fid, name):
        d = self._load(); d[fid]["name"] = name; self._save(d)
    def delete(self, fid):
        d = self._load(); d.pop(fid, None); self._save(d)

class FirestoreStore:
    def __init__(self, creds_json):
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(json.loads(creds_json)))
        self.col = firestore.client().collection("funds")
    def list_funds(self):
        return sorted(({"id": d.id, "name": d.get("name"), "count": len(d.to_dict().get("rows", []))} for d in self.col.stream()), key=lambda f: f["name"])
    def get(self, fid):
        s = self.col.document(fid).get()
        return s.to_dict() if s.exists else None
    def create(self, name):
        fid = _slug(name)
        while self.col.document(fid).get().exists: fid += "-1"
        self.col.document(fid).set({"name": name, "rows": [], "updated": time.time()}); return fid
    def save_rows(self, fid, rows):
        self.col.document(fid).update({"rows": rows, "updated": time.time()})
    def rename(self, fid, name):
        self.col.document(fid).update({"name": name})
    def delete(self, fid):
        self.col.document(fid).delete()

def get_store():
    c = os.environ.get("FIREBASE_CREDENTIALS")
    return FirestoreStore(c) if c else LocalStore()
