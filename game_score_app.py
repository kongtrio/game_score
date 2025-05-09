from flask import Flask, render_template, request, redirect, url_for, send_file, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import csv
import io
from functools import wraps
import logging

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///game_scores.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(
    filename="game_score.log", level=logging.INFO, format="%(asctime)s - %(message)s"
)

# Hardcoded password
PASSWORD = "114433"


# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player1 = db.Column(db.String(100), nullable=False)
    player2 = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=False)
    player1_score = db.Column(db.Integer, nullable=False)
    player2_score = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.now)
    match = db.relationship("Match", backref=db.backref("scores", lazy=True))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Incorrect password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    matches = Match.query.all()
    return render_template("index.html", matches=matches)


@app.route("/add_match", methods=["GET", "POST"])
@login_required
def add_match():
    if request.method == "POST":
        player1 = request.form["player1"]
        player2 = request.form["player2"]
        new_match = Match(player1=player1, player2=player2)
        db.session.add(new_match)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("add_match.html")


@app.route("/record_score/<int:match_id>", methods=["GET", "POST"])
@login_required
def record_score(match_id):
    match = Match.query.get_or_404(match_id)
    if request.method == "POST":
        player1_score = int(request.form["player1_score"])
        player2_score = int(request.form["player2_score"])
        new_score = Score(
            match_id=match_id, player1_score=player1_score, player2_score=player2_score
        )
        db.session.add(new_score)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("record_score.html", match=match)


@app.route("/stats/<int:match_id>")
@login_required
def stats(match_id):
    match = Match.query.get_or_404(match_id)
    scores = (
        Score.query.filter_by(match_id=match_id)
        .order_by(Score.recorded_at.desc())
        .all()
    )

    total_player1 = sum(score.player1_score for score in scores)
    total_player2 = sum(score.player2_score for score in scores)

    # 计算胜率(确保总和为100%)
    total_matches = total_player1 + total_player2
    player1_win_rate = (
        round(total_player1 / total_matches * 100, 2) if total_matches > 0 else 0
    )
    player2_win_rate = 100 - player1_win_rate

    # 按月汇总数据
    monthly_data = {}
    for score in scores:
        month_key = score.recorded_at.strftime("%Y-%m")
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                "player1_score": 0,
                "player2_score": 0,
                "player1_win_rate": 0,
                "player2_win_rate": 0,
                "total": 0,
            }

        monthly_data[month_key]["player1_score"] += score.player1_score
        monthly_data[month_key]["player2_score"] += score.player2_score
        monthly_data[month_key]["total"] += score.player1_score + score.player2_score

    # 计算每月胜率(确保总和为100%)
    for month in monthly_data.values():
        month["player1_win_rate"] = (
            round(month["player1_score"] / month["total"] * 100, 2)
            if month["total"] > 0
            else 0
        )
        month["player2_win_rate"] = 100 - month["player1_win_rate"]

    return render_template(
        "stats.html",
        match=match,
        scores=scores,
        total_player1=total_player1,
        total_player2=total_player2,
        player1_win_rate=player1_win_rate,
        player2_win_rate=player2_win_rate,
        monthly_data=monthly_data,
    )


@app.route("/export_scores/<int:match_id>")
@login_required
def export_scores(match_id):
    match = Match.query.get_or_404(match_id)
    scores = Score.query.filter_by(match_id=match_id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", match.player1 + "得分", match.player2 + "得分"])

    for score in scores:
        writer.writerow(
            [
                score.recorded_at.strftime("%Y-%m-%d"),
                score.player1_score,
                score.player2_score,
            ]
        )

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"{match.player1}_vs_{match.player2}_比分记录.csv",
    )


@app.route("/import_scores/<int:match_id>", methods=["GET", "POST"])
@login_required
def import_scores(match_id):
    match = Match.query.get_or_404(match_id)

    if request.method == "POST":
        if "file" not in request.files:
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            return redirect(request.url)

        if file and file.filename.endswith(".csv"):
            stream = io.StringIO(file.stream.read().decode("UTF-8"), newline=None)
            csv_reader = csv.reader(stream)
            next(csv_reader)  # Skip header

            for row in csv_reader:
                if len(row) == 3:
                    try:
                        try:
                            recorded_date = datetime.strptime(row[0], "%Y-%m-%d")
                        except ValueError:
                            recorded_date = datetime.strptime(row[0], "%Y%m%d")

                        player1_score = int(row[1])
                        player2_score = int(row[2])

                        new_score = Score(
                            match_id=match_id,
                            player1_score=player1_score,
                            player2_score=player2_score,
                            recorded_at=recorded_date,
                        )
                        db.session.add(new_score)
                    except (ValueError, IndexError):
                        continue

            db.session.commit()
            return redirect(url_for("stats", match_id=match_id))

    return render_template("import_scores.html", match=match)


@app.route("/delete_score/<int:score_id>", methods=["POST"])
@login_required
def delete_score(score_id):
    score = Score.query.get_or_404(score_id)
    reason = request.form.get("reason", "").strip()

    if not reason:
        return "Reason is required", 400

    # Log the deletion
    logging.info(
        f"Score deleted - ID: {score_id}, Match ID: {score.match_id}, "
        f"Player1: {score.match.player1}, Player2: {score.match.player2}, "
        f'Reason: {reason}, Deleted by: {session.get("username", "Unknown")}'
    )

    db.session.delete(score)
    db.session.commit()
    return redirect(url_for("stats", match_id=score.match_id))


app.secret_key = "super_secret_key"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=False, host="0.0.0.0", port=50020)
