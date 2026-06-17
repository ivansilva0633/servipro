
import os, sqlite3, datetime
from flask import Flask, request, redirect, render_template, jsonify, url_for
from urllib.parse import quote

app = Flask(__name__)
DB = "servipro.db"

def db():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS servicos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente TEXT, telefone TEXT, descricao TEXT,
        valor REAL, data TEXT, status TEXT DEFAULT 'agendado',
        pago INTEGER DEFAULT 0,
        criado_em TEXT)""")
    con.commit(); con.close()

@app.route("/")
def home():
    con = db()
    hoje = datetime.date.today().isoformat()
    servicos = con.execute("SELECT * FROM servicos ORDER BY data ASC").fetchall()
    # metricas
    mes = datetime.date.today().strftime("%Y-%m")
    ganho = con.execute("SELECT COALESCE(SUM(valor),0) t FROM servicos WHERE pago=1 AND data LIKE ?", (mes+"%",)).fetchone()["t"]
    receber = con.execute("SELECT COALESCE(SUM(valor),0) t FROM servicos WHERE pago=0 AND status='concluido'").fetchone()["t"]
    agendados = con.execute("SELECT COUNT(*) c FROM servicos WHERE status='agendado'").fetchone()["c"]
    con.close()
    return render_template("index.html", servicos=servicos, ganho=ganho,
                           receber=receber, agendados=agendados, hoje=hoje)

@app.route("/novo", methods=["POST"])
def novo():
    f = request.form
    con = db()
    con.execute("""INSERT INTO servicos(cliente,telefone,descricao,valor,data,criado_em)
        VALUES(?,?,?,?,?,?)""",
        (f["cliente"], f["telefone"], f["descricao"], float(f["valor"] or 0),
         f["data"], datetime.datetime.now().isoformat()))
    con.commit(); con.close()
    return redirect("/")

@app.route("/concluir/<int:sid>")
def concluir(sid):
    con = db(); con.execute("UPDATE servicos SET status='concluido' WHERE id=?", (sid,))
    con.commit(); con.close(); return redirect("/")

@app.route("/pago/<int:sid>")
def pago(sid):
    con = db(); con.execute("UPDATE servicos SET pago=1,status='concluido' WHERE id=?", (sid,))
    con.commit(); con.close(); return redirect("/")

@app.route("/excluir/<int:sid>")
def excluir(sid):
    con = db(); con.execute("DELETE FROM servicos WHERE id=?", (sid,))
    con.commit(); con.close(); return redirect("/")

@app.route("/orcamento/<int:sid>")
def orcamento(sid):
    con = db(); s = con.execute("SELECT * FROM servicos WHERE id=?", (sid,)).fetchone(); con.close()
    msg = f"*Orcamento - ServiPro*%0A%0A Ola {s['cliente']}!%0A%0AServico: {s['descricao']}%0AValor: R$ {s['valor']:.2f}%0AData: {s['data']}%0A%0AQualquer duvida estou a disposicao!"
    tel = "".join(c for c in s["telefone"] if c.isdigit())
    return redirect(f"https://wa.me/55{tel}?text={msg}")

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
