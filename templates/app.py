from flask import Flask, render_template, request, redirect, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import smtplib
from email.mime.text import MIMEText
import matplotlib.pyplot as plt
from fpdf import FPDF
import urllib.parse
from datetime import datetime
from sqlalchemy import func

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configuration de la base de données SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///phishing_data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Modèle pour stocker les interactions des utilisateurs
class Interaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # reçu, ouvert, cliqué, soumis
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

# Création des tables
with app.app_context():
    db.create_all()

# Identifiants admin
ADMIN_USERNAME = "Reg"
ADMIN_PASSWORD = "Saouda2025!!"

# Configuration SMTP Office365
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SENDER_EMAIL = "regence.informatique@liquidationtravail.com"
SENDER_PASSWORD = "Saouda2025!!"

# Fonction pour envoyer un email de phishing avec un problème lié à Outlook
def send_email(recipient_email, recipient_name, phishing_link):

    # Construire le lien de phishing avec le tracking du clic
    phishing_link = f"https://outlook-regence.onrender.com/track_open?email={urllib.parse.quote(recipient_email)}&next=https://outlook-regence.onrender.com/"

    email_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <p>Bonjour <strong>{recipient_name}</strong>,</p>

        <p>Nous rencontrons actuellement un problème technique affectant certains comptes Outlook au sein de notre organisation. En raison d’une mise à jour récente, 
        certains utilisateurs pourraient rencontrer des difficultés d'accès à leurs emails ou voir des erreurs de synchronisation.</p>

        <p><strong>Action requise :</strong><br>
        Afin d’éviter toute interruption de service, nous vous invitons à réauthentifier votre compte Microsoft en suivant la procédure ci-dessous.</p>

        <p style="text-align: center;">
            <a href="{phishing_link}" style="background-color: #0078D4; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-size: 16px;">
                Réauthentifier mon compte
            </a>
        </p>

        <p>Cette opération ne prendra que quelques instants et permettra de restaurer l’accès normal à votre boîte mail.</p>

        <p>Si vous avez des questions ou rencontrez des difficultés, n’hésitez pas à contacter notre support technique.</p>

        <hr>
        <p><strong>Département Informatique - Régence</strong><br>
        Assistance IT Régence<br>
        www.regence.com<br>
        655 Rue de l'Argon, Québec, QC G2N 2G7</p>
    </body>
    </html>
    """
    try:
        msg = MIMEText(email_content, "html")
        msg["Subject"] = "Problème d'accès à Outlook - Action requise"
        msg["From"] = f"Département Informatique <{SENDER_EMAIL}>"
        msg["To"] = recipient_email

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()

        db.session.add(Interaction(email=recipient_email, event_type="email envoyé"))
        db.session.commit()
        print(f"? Email envoyé à {recipient_email}")

    except Exception as e:
        print(f"? Erreur lors de l'envoi de l'email : {e}")
        
        
@app.route("/track_open")
def track_open():
    email = request.args.get("email")
    next_url = request.args.get("next", "https://outlook.com")  # URL de redirection par défaut

    if email:
        # Enregistrez l'événement "lien cliqué" et associez-le à l'utilisateur
        db.session.add(Interaction(email=email, event_type="lien cliqué"))
        db.session.commit()
    
    return redirect(next_url)  # Redirige l'utilisateur vers la page cible

    
@app.route("/reset_stats", methods=["POST"])
def reset_stats():
    if not session.get("logged_in"):
        return {"success": False, "error": "Accès refusé"}, 403
    
    try:
        db.session.query(Interaction).delete()  # Supprime toutes les interactions
        db.session.commit()
        return {"success": True}
    except Exception as e:
        db.session.rollback()
        return {"success": False, "error": str(e)}, 500



@app.route("/capture", methods=["POST"])
def capture():
    email = request.form.get("email")
    password = request.form.get("password")  # Juste pour la simulation, ne l'affiche pas !
    
    if email:
        db.session.add(Interaction(email=email, event_type="formulaire soumis"))
        db.session.commit()
    
    return redirect("https://outlook.com")  # Rediriger l'utilisateur après soumission

@app.route("/")
def home():
    return render_template("index.html")  # Page d'accueil

# Route pour afficher le formulaire de login pour accéder à l'envoi d'email
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/send_email")  # Si l'utilisateur est authentifié, rediriger vers la page d'envoi d'email
        return "Accès refusé", 401  # Si les identifiants sont incorrects
    
    return render_template("login.html")  # Page de connexion

# Route pour envoyer un email de phishing
import csv
from werkzeug.utils import secure_filename

@app.route("/send_email", methods=["GET", "POST"])
def send_email_route():
    if not session.get("logged_in"):  # Vérifier si l'utilisateur est connecté
        return redirect("/login")  # Rediriger vers la page de login si non connecté

    if request.method == "POST":
        # Vérifier si un fichier CSV est téléchargé
        file = request.files.get("csv_file")
        if file and file.filename.endswith('.csv'):
            # Sauvegarder le fichier CSV
            filename = secure_filename(file.filename)
            file_path = os.path.join("uploads", filename)
            file.save(file_path)

            # Lire les emails et noms depuis le fichier CSV
            try:
                with open(file_path, mode="r", newline="", encoding="utf-8") as csvfile:

                    reader = csv.reader(csvfile)
                    next(reader)  # Ignorer l'entête du fichier CSV

                    # Envoi des emails de phishing à chaque destinataire
                    phishing_link = "https://outlook-regence.onrender.com"  # Lien de phishing
                    for row in reader:
                        if len(row) >= 2:  # Vérifier qu'il y a au moins un email et un nom
                            recipient_email = row[0].strip()
                            recipient_name = row[1].strip()
                            send_email(recipient_email, recipient_name)


                    return f"Emails envoyés avec succès à tous les destinataires du fichier CSV."
            except Exception as e:
                return f"Erreur lors du traitement du fichier CSV : {e}", 500
        
        # Sinon, envoyer un email à un seul destinataire
        recipient_email = request.form.get("recipient_email")
        recipient_name = request.form.get("recipient_name")
        
        if recipient_email and recipient_name:
            phishing_link = "https://outlook-regence.onrender.com"  # Lien de phishing
            send_email(recipient_email, recipient_name, phishing_link)
            return f"Email envoyé à {recipient_name} ({recipient_email}) avec succès !"

        return "Erreur : Email ou Nom manquant.", 400

    return render_template("send_email.html")  # Page pour envoyer un email


# Route pour afficher le formulaire de login pour accéder aux statistiques
@app.route("/stats", methods=["GET", "POST"])
def stats():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/stats_dashboard")
        return "Accès refusé", 401
    
    return render_template("login.html")  # Page de connexion admin

# Route pour afficher le tableau de bord des statistiques
@app.route("/stats_dashboard")
def stats_dashboard():
    if not session.get("logged_in"):
        return redirect("/stats")

    # Statistiques globales
    total_sent = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="email envoyé").scalar() or 0
    total_clicked = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="lien cliqué").scalar() or 0
    total_submitted = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="formulaire soumis").scalar() or 0

    # Récupérer les stats par utilisateur
    user_stats = db.session.query(
        Interaction.email,
        db.func.count(Interaction.id).filter(Interaction.event_type == "email envoyé").label("sent"),
        db.func.count(Interaction.id).filter(Interaction.event_type == "lien cliqué").label("clicked"),
        db.func.count(Interaction.id).filter(Interaction.event_type == "formulaire soumis").label("submitted"),
        db.func.max(Interaction.timestamp).label("action_date")
    ).group_by(Interaction.email).all()

    user_data = []
    for user in user_stats:
        email, sent, clicked, submitted, action_date = user
        click_rate = (clicked / sent * 100) if sent > 0 else 0
        submit_rate = (submitted / sent * 100) if sent > 0 else 0

        # Vérification et conversion de action_date si nécessaire
        if action_date and isinstance(action_date, str):
            try:
                action_date = datetime.strptime(action_date, '%Y-%m-%d %H:%M:%S')
            except ValueError as e:
                print(f"Erreur de conversion de la date : {action_date} - {e}")
                action_date = None

        action_date_display = (
            action_date.strftime('%d/%m/%Y %H:%M') if isinstance(action_date, datetime) 
            else 'Date non disponible'
        )

        user_data.append({
            "email": email,
            "sent": sent,
            "clicked": clicked,
            "submitted": submitted,
            "click_rate": round(click_rate, 2),
            "submit_rate": round(submit_rate, 2),
            "action_date": action_date_display
        })

    return render_template("stats_dashboard.html", 
                           total_sent=total_sent, 
                           total_clicked=total_clicked, 
                           total_submitted=total_submitted,
                           user_data=user_data,
                           user_stats=user_stats)
@app.template_filter('date')
def date_filter(value, format='%d/%m/%Y %H:%M'):
    if isinstance(value, datetime):
        return value.strftime(format)
    return 'Date non disponible'  # Ajoutez un message plus clair si la valeur est nulle ou incorrecte


                           
@app.route("/user_stats/<user_email>")
def user_stats(user_email):
    if not session.get("logged_in"):
        return redirect("/stats")

    # Récupérer les statistiques pour l'email spécifique
    total_sent = db.session.query(db.func.coalesce(db.func.count(Interaction.id), 0)).filter_by(email=user_email, event_type="email envoyé").scalar()
    total_clicked = db.session.query(db.func.coalesce(db.func.count(Interaction.id), 0)).filter_by(email=user_email, event_type="lien cliqué").scalar()
    total_submitted = db.session.query(db.func.coalesce(db.func.count(Interaction.id), 0)).filter_by(email=user_email, event_type="formulaire soumis").scalar()

    # Gestion des valeurs non valides ou nulles
    total_sent = max(0, total_sent or 0)
    total_clicked = max(0, total_clicked or 0)
    total_submitted = max(0, total_submitted or 0)

    # Liste des valeurs à afficher dans le graphique
    values = [total_sent, total_clicked, total_submitted]
    labels = ["Emails envoyés", "Liens cliqués", "Formulaires remplis"]

    # Générer les statistiques sous forme de graphique (par exemple, un graphique en camembert)
    try:
        plt.figure(figsize=(6, 6))
        plt.pie(values, labels=labels, autopct="%1.1f%%", colors=["blue", "orange", "red"])
        plt.title(f"Statistiques de l'utilisateur : {user_email}")
        plt.savefig(f"static/stats_{user_email}.png")
        plt.close()
    except Exception as e:
        print(f"Erreur lors de la génération du graphique : {e}")

    # Explication à afficher sur le tableau de bord
    explanation = f"Les graphiques ci-dessus montrent les résultats du test de phishing pour l'utilisateur : {user_email}. " \
                  "Les emails envoyés sont suivis des liens cliqués et des formulaires soumis."

    return render_template("user_dashboard.html", 
                           user_email=user_email, 
                           total_sent=total_sent, 
                           total_clicked=total_clicked, 
                           total_submitted=total_submitted,
                           explanation=explanation)
                           
@app.route("/get_stats")
def get_stats():
    if not session.get("logged_in"):
        return redirect("/stats")
    
    # Récupérer les statistiques actuelles
    total_sent = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="email envoyé").scalar() or 0
    total_clicked = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="lien cliqué").scalar() or 0
    total_submitted = db.session.query(db.func.count(Interaction.id)).filter_by(event_type="formulaire soumis").scalar() or 0

    return jsonify({
        "sent": total_sent,
        "clicked": total_clicked,
        "submitted": total_submitted
    })



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


