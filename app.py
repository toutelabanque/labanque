from json import loads
from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, abort, jsonify, render_template, redirect, request, session
##from werkzeug.exceptions import HTTPException
from bank import Member

member_ids = []

for id in Member.cursor.execute('SELECT id FROM members;'):
    member_ids.append(id[0])

for id in member_ids:
    Member(id)

try:
    app = Flask(__name__)

    app.secret_key = b'016480fad86b560ddda3776246a9d959c718dab93e2632b8c93e29142ad46a73'


    @app.route("/")
    def home():
        if "id" in session:
            member = Member.get_member(session['id'])
            try:
                return render_template('home.html', balance=member.balance, accounts=member.accounts)  # type: ignore
            except AttributeError:
                session.pop("id")
        return render_template('index.html')


    @app.route("/login/", methods=["GET", "POST"])
    def login():
        wrong = False
        if request.method == "POST":
            try:
                if checkpw(request.form["password"].encode('utf-8'), Member.get_member(request.form['id']).pass_hash()):  # type: ignore
                    session.update({"id": str(request.form["id"])})
                    return redirect('/')
                wrong = True
            except (ValueError, AttributeError, TypeError) as e:
                print(e)
                wrong = True
        return render_template('login.html', wrong=wrong, new=False)
    

    @app.post("/logout/")  # type: ignore
    def logout():
        session.pop("id")
        return redirect("/")


    @app.route("/sign-up/", methods=['GET', 'POST'])
    def sign_up():
        if request.method == 'POST':
            if request.form['password'] == request.form['confirm-password']:
                member = Member(None, request.form['f-name'], request.form['l-name'],
                        hashpw(request.form['password'].encode('utf-8'), gensalt()))
                Member(member.id)
                return render_template("login.html", wrong=False, new=member.id)
            return render_template('sign-up.html', match_issue=True)
        return render_template('sign-up.html', match_issue=False)
    

    @app.route("/open-account/", methods=['GET', 'PUT'])  # type: ignore
    def open_account():
        pass


    @app.route("/account/<int:id>")  # type: ignore
    def account(id):
        return render_template("account.html", account=Member.cursor.execute('SELECT * from accounts WHERE id = ?', (id,)))


    @app.post("/charge/")
    def charge():
        member = Member.get_member(
            int(loads(request.get_json()["payer-id"])))  # type: ignore
        if isinstance(member, Member):
            try:
                member.charge(Member.get_member(loads(request.get_json()["recipient-id"])),  # type: ignore
                            loads(request.get_json()["amount"]), bool(loads(request.get_json()["taxable"])))  # type: ignore
                return jsonify(request.get_json()), 200
            except TypeError:
                return abort(404)
            except ValueError:
                pass
        return abort(400)



    ##@app.errorhandler(Exception)
    ##def handle_errors(e):
    ##    if isinstance(e, HTTPException):
    ##        code = e.code
    ##        name = e.name
    ##        description = e.description
    ##    else:
    ##        code = 500
    ##        name = 'Internal Server Error'
    ##        description = type(e)
    ##    return render_template('error.html', code=code, name=name, description=description)

    if __name__ == '__main__':
        app.run('0.0.0.0', 443, True, use_evalex=False, ssl_context='adhoc')
except:
    Member.close()
    raise SystemExit
