from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, abort, render_template, redirect, request, session
from flask_talisman import Talisman
from traceback import format_exc
from bank import Member, BASE_RATES

member_ids = []

try:
    for id in Member.cursor.execute('SELECT id FROM members;'):
        member_ids.append(id[0])

    for id in member_ids:
        Member(id)

    app = Flask(__name__)
    Talisman(app, force_https_permanent=True, frame_options='DENY', content_security_policy={
        'default-src': "'self'",
        'style-src': ["'self'", "'unsafe-inline'"],
        'navigate-to': "'self'",
        'form-action': "'self'",
        'object-src': "'none'",
        'frame-src': "'none'",
        'media-src': "'none'",
        'connect-src': "'none'"
    })

    app.secret_key = b'016480fad86b560ddda3776246a9d959c718dab93e2632b8c93e29142ad46a73'

    @app.route("/")
    def home():
        if session.get("id"):
            member = Member.get_member(session['id'])
            member.sync_balance()
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
                    return redirect(request.args.get('redir', default='/', type=str), 303)
                wrong = True
            except (ValueError, AttributeError, TypeError, KeyError):
                wrong = True
        return render_template('login.html', wrong=wrong, new=False, redir=request.args.get('redir', default='/', type=str))

    @app.post("/logout/")  # type: ignore
    def logout():
        session.pop("id", None)
        return redirect("/", 303)

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

    @app.route("/direct-transfer/", methods=['GET', 'POST'])
    def direct_transfer():
        if session.get('id'):
            exists = True
            remaining = ""
            if request.method == 'POST':
                try:
                    remaining = Member.get_member(session['id']).charge(Member.get_member(  # type: ignore
                            str(request.form['to'])), float(request.form['amount']), False)
                except AttributeError:
                    print(format_exc())
                    exists = False
            return render_template('direct-transfer.html', exists=exists, remaining=remaining)
        return redirect("/login/?redir=/direct-transfer/", 303)

    @app.route("/open-account/", methods=['GET', 'POST'])  # type: ignore
    def open_account():
        if session.get('id'):
            done = False
            if request.method == 'POST':
                if request.form['type'] == 'savings':
                    Member.get_member(session['id']).create_account(
                        float(request.form["starting-amount"]), Member.get_member(session['id']).calc_r('savings'))
                elif request.form['type'] == 'cd':
                    Member.get_member(session['id']).create_account(
                        float(request.form["starting-amount"]), Member.get_member(session['id']).calc_r('cd', float(request.form['term'])), float(request.form['term']))
                done = True
            rates = {-1: Member.get_member(session['id']).calc_r('savings')}  # type:ignore
            for term in BASE_RATES['cd']:
                rates.update({float(term): Member.get_member(session['id']).calc_r('cd', float(term))})  # type: ignore
            return render_template('open-account.html', rates=rates, done=done)  # type: ignore
        return redirect("/login/?redir=/open-account/", 303)
    

    @app.route("/get-loan/", methods=['GET', 'POST'])
    def get_loan():
        if session.get('id'):
            if request.method == 'POST':
                Member.get_member(session['id'])
            return render_template('get-loan.html', rate=Member.get_member(session['id']).calc_r('loan'))  # type: ignore
        return redirect("/login/?redir=/get-loan/", 303)


    @app.route("/accounts/<int:id>/")
    @app.route("/accounts/")
    def accounts(id=None):
        if session.get('id'):
            if id is None:
                return(render_template("accounts.html", accounts=Member.get_member(session['id']).accounts))  # type: ignore
            else:
                return render_template("account.html", account=[a for a in Member.get_member(session['id']).accounts if a.id == id][0])
        return redirect("/login/?redir=/accounts/", 303)
    

    @app.route("/transaction-history/")
    def transaction_history():
        if session.get('id'):
            return render_template("transactions.html", transactions=Member.get_member(session['id']).transactions, get_member=Member.get_member)  # type: ignore
        return redirect("/login/?redir=/transaction-history/", 303)

    
    @app.route("/get-credit-card/")
    def get_credit_card():
        # TODO
        return abort(503, "Under Development")


    @app.post("/charge/")
    def charge():
        if request.remote_addr not in [ip[0] for ip in Member.cursor.execute('SELECT ip FROM registered_ips')]:
            return "", 403
        if request.content_length is None:
            return "", 411
        elif request.content_length > 200:
            return "", 413
        try:
            return str(Member.get_member(request.json["payer-id"]).charge(Member.get_member(request.json["recipient-id"]), request.json["amount"], bool(request.json["taxable"]))), 200  # type: ignore
        except (TypeError, AttributeError):
            return "", 404
        except ValueError:
            pass
        return "", 404


    if __name__ == '__main__':
        app.run('0.0.0.0', 443, ssl_context='adhoc')
except:
    print(format_exc())
    Member.close()
    raise SystemExit
