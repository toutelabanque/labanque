from bcrypt import checkpw, gensalt, hashpw
from flask import Flask, abort, render_template, redirect, request, session
from flask_talisman import Talisman
from traceback import print_exc
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
                return render_template('home.html', balance=member.balance, accounts=member.accounts)
            except AttributeError:
                session.pop("id")
        return render_template('index.html')

    @app.route("/login/", methods=["GET", "POST"])
    def login():
        wrong = False
        if request.method == "POST":
            try:
                if checkpw(request.form["password"].encode('utf-8'), Member.get_member(request.form['id']).pass_hash()):
                    session.update({"id": str(request.form["id"])})
                    return redirect(request.args.get('redir', default='/', type=str), 303)
                wrong = True
            except (ValueError, AttributeError, TypeError, KeyError):
                wrong = True
        return render_template('login.html', wrong=wrong, new=False, redir=request.args.get('redir', default='/', type=str))

    @app.post("/logout/")
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
                return render_template("login.html", wrong=False, new=member.id, redir='/')
            return render_template('sign-up.html', match_issue=True)
        return render_template('sign-up.html', match_issue=False)

    @app.route("/direct-transfer/", methods=['GET', 'POST'])
    def direct_transfer():
        if session.get('id'):
            exists = True
            charged = ""
            remaining = ""
            if request.method == 'POST':
                try:
                    charged, remaining, _ = Member.get_member(session['id']).charge(Member.get_member(
                        str(request.form['to'])), float(request.form['amount']), False)
                except AttributeError:
                    exists = False
            return render_template('direct-transfer.html', exists=exists, charged=charged, remaining=remaining)
        return redirect("/login/?redir=/direct-transfer/", 303)

    @app.route("/open-account/", methods=['GET', 'POST'])
    def open_account():
        if session.get('id'):
            done = False
            poor = False
            if request.method == 'POST':
                try:
                    if request.form['type'] == 'savings':
                        done = Member.get_member(session['id']).create_account(
                            float(request.form["starting-amount"]), Member.get_member(session['id']).calc_r('savings'))
                    elif request.form['type'] == 'cd':
                        done = Member.get_member(session['id']).create_account(
                            float(request.form["starting-amount"]), Member.get_member(session['id']).calc_r('cd', float(request.form['term'])), float(request.form['term']))
                    elif request.form['type'] == 'checking':
                        done = Member.get_member(session['id']).create_account(
                            float(request.form["starting-amount"]))
                    poor = False
                except ValueError:
                    done = False
                    poor = True
            rates = {-1: Member.get_member(session['id']).calc_r('savings')}
            for term in BASE_RATES['cd']:
                rates.update({float(term): Member.get_member(
                    session['id']).calc_r('cd', float(term))})
            return render_template('open-account.html', rates=rates, done=done, poor=poor)
        return redirect("/login/?redir=/open-account/", 303)

    @app.route("/get-loan/", methods=['GET', 'POST'])
    def get_loan():
        if session.get('id'):
            if request.method == 'POST':
                # TODO
                pass
            return render_template('get-loan.html', rate=Member.get_member(session['id']).calc_r('loan'))
        return redirect("/login/?redir=/get-loan/", 303)

    @app.route("/accounts/<int:id>/", methods=['GET', 'POST'])
    @app.route("/accounts/")
    def accounts(id=None):
        if session.get('id'):
            member = Member.get_member(session['id'])
            # Page displaying all accounts
            if id is None:
                return(render_template("accounts.html", accounts=member.accounts))
            else:
                # Page with more info on one account
                if request.method == 'GET':
                    account = [a for a in member.accounts if a.id == id][0]
                    return render_template("account.html", account=account, checking=True if account is member.checking else False, accounts=member.accounts)
                if request.form.get('debit') == True:
                    pass
        return redirect("/login/?redir=/accounts/", 303)

    @app.route("/accounts/close/<int:id>/", methods=['GET', 'POST'])
    def close_account(id: int):
        if session.get('id'):
            accounts = Member.get_member(session['id']).accounts
            account = None
            for account in accounts:
                if account.id == id:
                    break
            if account is None:
                return "Whoops, that account doesn't exist", 404
            if account.balance > 0:
                return redirect("/accounts/transfer/" + str(id) + "/", 303)
            else:
                accounts.remove(account)
                Member.get_member(session['id']).sync_balance
                Member.get_member(session['id']).save()
                return redirect("/accounts/", 303)
        return redirect("/login/?redir=/accounts/close-account/" + str(id) + "/", 303)

    @app.route("/accounts/transfer/<int:id>/", methods=['GET', 'POST'])
    def transfer(id: int):
        """Not to be confused with direct transfer, this is for
        transferring from one of one's accounts to another, not from
        one's checking to another's.
        """
        if session.get('id'):
            for account in Member.get_member(session['id']).accounts:
                if account.id == id:
                    from_ = account
                    break
                # Invalid `id`
                elif account is Member.get_member(session['id']).accounts[-1]:
                    abort(400)
            if request.method == 'GET':
                theirs = False
                accounts = Member.get_member(session['id']).accounts.copy()
                for account in Member.get_member(session['id']).accounts:
                    if account.id == id:
                        theirs = True
                        accounts.remove(account)
                        break
                if not theirs:
                    return "Whoops, that account doesn't exist", 404
                Member.get_member(session['id']).sync_balance
                Member.get_member(session['id']).save()
                return render_template("transfer.html", account=account, accounts=accounts, funds=from_.balance)
            else:
                for account in Member.get_member(session['id']).accounts:
                    if account.id == int(request.form['to']):
                        to = account
                        break
                if from_.balance >= float(request.form['amount']):
                    from_.balance -= float(request.form['amount'])
                else:
                    abort(400)
                to.balance += float(request.form['amount'])
                return redirect("/accounts/" + str(id) + "/", 303)
        return redirect("/login/?redir=/accounts/transfer/" + str(id) + "/", 303)

    @app.route("/accounts/manage-debit-access/<_>/", methods=['GET', 'POST'])
    def manage_debit_access(_=None):
        if _ is not None:
            redirect("/accounts/manage-debit-access/", 308)
        if session.get('id'):
            if request.method == 'POST':
                # Setting/changing PIN
                if request.form.get('turn-on') == 'on':
                    pin_hash = hashpw(request.form['pin'].encode('utf-8'), gensalt())
                    Member.get_member(session['id']).pin_hash = lambda: pin_hash
                # Turning off access
                else:
                    Member.get_member(session['id']).pin_hash = lambda: None
                Member.get_member(session['id']).save()
                return redirect("/accounts/" + str(Member.get_member(session['id']).checking.id) + "/", 303)
            return render_template("debit.html", checked=bool(Member.get_member(session['id']).pin_hash()))
        return redirect("/login/?redir=/accounts/manage-debit-access/", 303)

    @app.route("/transaction-history/")
    def transaction_history():
        if session.get('id'):
            return render_template("transactions.html", transactions=Member.get_member(session['id']).transactions, get_member=Member.get_member)
        return redirect("/login/?redir=/transaction-history/", 303)

    @app.route("/get-credit-card/")
    def get_credit_card():
        # TODO
        abort(503, "Under Development")

    @app.post("/charge/")
    def charge():
        # If the request is from an unregistered IP
        if request.remote_addr not in [ip[0] for ip in Member.cursor.execute('SELECT ip FROM registered_ips')]:
            return "", 403
        # If the request doesn't say how long it is
        if request.content_length is None:
            return "", 411
        # If the request is waaay too long
        elif request.content_length > 200:
            return "", 413
        try:
            # If the account is not debit enabled
            if Member.get_member(str(request.json['payer-id'])).pin_hash() is None:
                return "", 404
            # If all goes well
            if checkpw(str(request.json["pin"]).encode('utf-8'), Member.get_member(str(request.json['payer-id'])).pin_hash()):
                Member.get_member(str(request.json['payer-id'])).sync_balance()
                Member.get_member(str(request.json['payer-id'])).save()
                Member.get_member(str(request.json['recipient-id'])).sync_balance()
                Member.get_member(str(request.json['recipient-id'])).save()
                return list(Member.get_member(request.json["payer-id"]).charge(Member.get_member(str(request.json["recipient-id"])), float(request.json["amount"]), bool(request.json["taxable"]))), 200
            # If password is incorrect
            return "", 401
        # If some Member didn't exist
        except (TypeError, AttributeError, ValueError):
            return "", 404
        # If anything else goes wrong, blame it on the client
        except:
           return "", 400

    if __name__ == '__main__':
        app.run('0.0.0.0', 443, ssl_context='adhoc')
except:
    print_exc()
    Member.close()
    raise SystemExit
