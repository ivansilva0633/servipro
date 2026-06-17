import os, sqlite3, datetime, hashlib
from flask import Flask, request, redirect, render_template, session, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-secreta-123")
DB = "servipro.db"

LIMITE_GRATIS = 5
LINK_PAGAMENTO = os.environ.get("LINK_PAGAMENTO", "https://seu-link-de-pagamento.com")

def db():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, email TEXT UNIQUE, senha TEXT,
        plano TEXT DEFAULT 'gratis', criado_em TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS servicos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        cliente TEXT, telefone TEXT, descricao TEXT,
        valor REAL, data TEXT, status TEXT DEFAULT 'agendado',
        pago INTEGER DEFAULT 0, criado_em TEXT)""")
    con.commit(); con.close()

def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def logado():
    return session.get("uid")

@app.route("/cadastro", methods=["GET","POST"])
def cadastro():
    if request.method=="POST":
        f=request.form; con=db()
        try:
            con.execute("INSERT INTO usuarios(nome,email,senha,criado_em) VALUES(?,?,?,?)",
                (f["nome"], f["email"].lower(), hash_senha(f["senha"]), datetime.datetime.now().isoformat()))
            con.commit()
            u=con.execute("SELECT * FROM usuarios WHERE email=?", (f["email"].lower(),)).fetchone()
            session["uid"]=u["id"]; session["nome"]=u["nome"]
            con.close(); return redirect("/")
        except sqlite3.IntegrityError:
            con.close(); flash("Esse email ja esta cadastrado!"); return redirect("/cadastro")
    return render_template("auth.html", modo="cadastro")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        f=request.form; con=db()
        u=con.execute("SELECT * FROM usuarios WHERE email=? AND senha=?",
            (f["email"].lower(), hash_senha(f["senha"]))).fetchone()
        con.close()
        if u:
            session["uid"]=u["id"]; session["nome"]=u["nome"]; return redirect("/")
        flash("Email ou senha incorretos!"); return redirect("/login")
    return render_template("auth.html", modo="login")

@app.route("/sair")
def sair():
    session.clear(); return redirect("/login")

@app.route("/")
def home():
    if not logado(): return redirect("/login")
    con=db(); uid=session["uid"]
    u=con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    servicos=con.execute("SELECT * FROM servicos WHERE usuario_id=? ORDER BY data ASC",(uid,)).fetchall()
    total=con.execute("SELECT COUNT(*) c FROM servicos WHERE usuario_id=?",(uid,)).fetchone()["c"]
    mes=datetime.date.today().strftime("%Y-%m")
    ganho=con.execute("SELECT COALESCE(SUM(valor),0) t FROM servicos WHERE usuario_id=? AND pago=1 AND data LIKE ?",(uid,mes+"%")).fetchone()["t"]
    receber=con.execute("SELECT COALESCE(SUM(valor),0) t FROM servicos WHERE usuario_id=? AND pago=0 AND status='concluido'",(uid,)).fetchone()["t"]
    agendados=con.execute("SELECT COUNT(*) c FROM servicos WHERE usuario_id=? AND status='agendado'",(uid,)).fetchone()["c"]
    con.close()
    gratis = (u["plano"]=="gratis")
    restantes = max(0, LIMITE_GRATIS - total) if gratis else None
    bloqueado = gratis and total >= LIMITE_GRATIS
    return render_template("index.html", servicos=servicos, ganho=ganho, receber=receber,
        agendados=agendados, hoje=datetime.date.today().isoformat(), nome=session["nome"],
        gratis=gratis, restantes=restantes, bloqueado=bloqueado,
        limite=LIMITE_GRATIS, link_pagamento=LINK_PAGAMENTO)

@app.route("/novo", methods=["POST"])
def novo():
    if not logado(): return redirect("/login")
    con=db(); uid=session["uid"]
    u=con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    total=con.execute("SELECT COUNT(*) c FROM servicos WHERE usuario_id=?",(uid,)).fetchone()["c"]
    if u["plano"]=="gratis" and total >= LIMITE_GRATIS:
        con.close(); flash("Voce atingiu o limite gratis! Assine o Pro para cadastrar ilimitado."); return redirect("/")
    f=request.form
    con.execute("""INSERT INTO servicos(usuario_id,cliente,telefone,descricao,valor,data,criado_em)
        VALUES(?,?,?,?,?,?,?)""",
        (uid, f["cliente"], f["telefone"], f["descricao"], float(f["valor"] or 0),
         f["data"], datetime.datetime.now().isoformat()))
    con.commit(); con.close(); return redirect("/")

@app.route("/concluir/<int:sid>")
def concluir(sid):
    if not logado(): return redirect("/login")
    con=db(); con.execute("UPDATE servicos SET status='concluido' WHERE id=? AND usuario_id=?",(sid,session["uid"]))
    con.commit(); con.close(); return redirect("/")

@app.route("/pago/<int:sid>")
def pago(sid):
    if not logado(): return redirect("/login")
    con=db(); con.execute("UPDATE servicos SET pago=1,status='concluido' WHERE id=? AND usuario_id=?",(sid,session["uid"]))
    con.commit(); con.close(); return redirect("/")

@app.route("/excluir/<int:sid>")
def excluir(sid):
    if not logado(): return redirect("/login")
    con=db(); con.execute("DELETE FROM servicos WHERE id=? AND usuario_id=?",(sid,session["uid"]))
    con.commit(); con.close(); return redirect("/")

@app.route("/orcamento/<int:sid>")
def orcamento(sid):
    if not logado(): return redirect("/login")
    con=db(); s=con.execute("SELECT * FROM servicos WHERE id=? AND usuario_id=?",(sid,session["uid"])).fetchone(); con.close()
    msg=f"*Orcamento - ServiPro*%0A%0AOla {s['cliente']}!%0A%0AServico: {s['descricao']}%0AValor: R$ {s['valor']:.2f}%0AData: {s['data']}%0A%0AQualquer duvida estou a disposicao!"
    tel="".join(c for c in s["telefone"] if c.isdigit())
    return redirect(f"https://wa.me/55{tel}?text={msg}")

init_db()
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
