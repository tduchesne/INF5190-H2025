from functools import wraps
from werkzeug.utils import secure_filename
from database import Database
from flask import Flask, render_template, redirect, url_for, request, g, session, Response, make_response, \
    send_from_directory
import re

app = Flask(__name__, static_url_path='', static_folder='static')

MAX_FILE_SIZE = 10 * 1024 * 1024
EXTENSIONS_PERMISES = frozenset({'png', 'jpg', 'jpeg', 'gif'})
regex = r"[A-Za-z0-9#$%&'*+/=?@]{8,}" #possiblement incomplet
mdp_format_test = re.compile(regex).match


def valider_type_fichier_pour_images(nom_du_fichier):
    if not isinstance(nom_du_fichier, str) or '.' not in nom_du_fichier:
        return False

    nom_du_fichier = secure_filename(nom_du_fichier)  # Sécurise le nom du fichier
    extension = nom_du_fichier.rsplit('.', 1)[-1].lower()
    est_permise = extension in EXTENSIONS_PERMISES
    return est_permise


def valider_courriel_existe(courriel):
    return get_db().courriel_existe(courriel)


def valider_courriel(courriel, validation_courriel):
    return courriel == validation_courriel


# Non testé et à revoir
def valider_mdp(mdp):
    try:
        if mdp_format_test(mdp) is not None:
            return True
    except:
        pass
    return False


def connection_requise(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id' not in session:
            return redirect(url_for('login')), 302
        return f(*args, **kwargs)
    return decorated_function


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        g._database = Database()
    return g._database


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close_connection()


@app.route('/')
def index():
    """Affiche les énoncés sous forme de fiches."""
    title = "INF5190 PROJET SESSION"
    return render_template('index.html',
                           title=title), 200


@app.route('/signin', methods=['GET', 'POST'])
def signin():
    title = "Mon site - veuillez vous inscrire"

    if request.method == "GET":
        return render_template("sign-in.html", title=title), 200

    # Gestion des requêtes POST
    form_data = {
        'nom': request.form.get('nom', "").strip(),
        'prenom': request.form.get('prenom', "").strip(),
        'courriel': request.form.get('courriel', "").strip(),
        'validation-courriel': request.form.get('courriel', "").strip(),
        'mdp': request.form.get('mdp', "")
    }

    erreurs = {}

    if not all(form_data.values()):
        erreurs["message_erreur"] = "Tous les champs doivent être remplis"

    if valider_courriel_existe(form_data['courriel']):
        erreurs["courriel_erreur"] = "Ce courriel existe déjà"

    if not valider_mdp(form_data['mdp']):
        erreurs["mdp_erreur"] = "Votre mot de passe ne respecte pas les critères"

    if erreurs:
        return render_template("sign-in.html", title=title, **erreurs, **form_data), 400

    # Tentative de création de l'utilisateur
    try:
        get_db().creer_utilisateur(
            form_data['nom'],
            form_data['prenom'],
            form_data['courriel'],
            form_data['mdp']
        )
    except Exception as e:
        erreurs["db_erreur"] = "Une erreur est survenue lors de l'inscription. Veuillez réessayer."
        return render_template("sign-in.html", title=title, **erreurs, **form_data), 500

    return redirect(url_for("confirmation")), 302


@app.route('/confirmation', methods=['GET'])
def confirmation():
    title = "Confirmation"
    return render_template('confirmation.html',
                           title=title), 200


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.route('/my/avatar/<avatar_id>')
def telecharger_avatar(avatar_id):
    """
    Permet à un utilisateur de télécharger une image d'avatar.
    Les avatars par défaut sont récupérés depuis un dossier statique,
    tandis que les avatars personnalisés sont chargés depuis la base de données.
    """

    try:
        # Gestion des avatars par défaut
        avatars_par_defaut = [
            'anime.png', 'batman.png', 'bear-russia.png',
            'coffee.png', 'jason.png', 'zombie.png'
        ]

        if avatar_id in avatars_par_defaut:
            return send_from_directory('static/images/def-avatar', avatar_id)

        # Gestion des avatars personnalisés
        binary_data = get_db().charger_avatar(avatar_id)
        if binary_data is None:
            return Response(status=404)

        response = make_response(binary_data)
        response.headers.set('Content-Type', 'image/png')
        return response

    except Exception as e:
        return Response(status=500)


@app.route('/my/avatar/update_avatar', methods=['POST'])
@connection_requise
def mettre_avatar_a_jour():
    """
    Permet à un utilisateur connecté de mettre à jour son avatar.
    Valide le fichier envoyé, limite sa taille, et enregistre les données dans la base.
    """
    user_id = session['id']

    try:
        if 'avatar' not in request.files:
            return "Aucun fichier joint...", 400

        file = request.files['avatar']

        if file.filename == '':
            return "Aucun fichier sélectionné...", 400

        if file and valider_type_fichier_pour_images(file.filename):
            if file.content_length <= MAX_FILE_SIZE:
                avatar_data = file.read()
                get_db().mettre_avatar_a_jour(user_id, avatar_data)
                return redirect(url_for('profile'))
            else:
                return "Le fichier excède la grosseur permise...", 400
        else:
            return "Type de fichier non permis...", 400

    except Exception as e:
        return "Une errreur innatendu c'est produite, veuillez réessayer plus tard...", 500


if __name__ == '__main__':
    app.run()
