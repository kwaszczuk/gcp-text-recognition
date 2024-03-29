from flask import Flask, flash, render_template, redirect, request, url_for, Markup
from google.cloud import storage, firestore

import uuid
import hashlib

from auth import AuthMiddleware, require_authentication

ALLOWED_UPLOADS_EXTENSIONS = {'.png', '.jpg', '.jpeg'}

app = Flask(__name__)
app.wsgi_app = AuthMiddleware(app)

def file_was_processed(file_dig, db=None):
    if db is None:
        db = firestore.Client()

    res = db.collection('text-recognitions')\
        .where('file_digest', '==', file_dig)\
        .limit(1)\
        .get()

    return len(res) == 1

@app.route('/login', methods=['GET'])
def login():
    if request.environ['user'] is not None:
        return redirect(url_for('home'))
    else:
        return render_template('login.html', CLIENT_ID=app.config['OAUTH_CLIENT_ID'])


# Logout action, removes authentication token from cookies
@app.route('/logout', methods=['GET'])
def logout():
    res = redirect(url_for('home'))
    res.delete_cookie('token')
    return res


@app.route('/', methods=['GET'])
@require_authentication
def home():
    return render_template('index.html', user=request.environ['user'], CLIENT_ID=app.config['OAUTH_CLIENT_ID'])

@app.route('/check-duplicate', methods=['POST'])
@require_authentication
def check_duplicate():
    return {
        'duplicate': file_was_processed(request.form['hash'])
    }

@app.route('/recognize', methods=['POST'])
@require_authentication
def recognize():
    file = request.files['file']
    file_extension = '.' + file.filename.split('.')[-1]

    if file_extension not in ALLOWED_UPLOADS_EXTENSIONS:
        flash(Markup(f'Files with the extension <strong>{file_extension}</strong>, are not supported.'), 'upload_error')
        return redirect(url_for('home'))

    file_content = file.read()
    file_dig = hashlib.md5(file_content).hexdigest()
    file_id = str(uuid.uuid4())

    # upload image to bucket
    bucket = storage.Client().get_bucket(app.config['IMAGES_BUCKET_NAME'])
    blob = bucket.blob(file_id)
    blob.upload_from_string(
        file_content,
        content_type=file.content_type
    )

    db = firestore.Client()
    db.collection('text-recognitions').document(file_id).set({
        'file_digest': file_dig,
        'file_name': file.filename,
        'sender_email': request.environ['user']['email'],
        'sender_firstname': request.environ['user']['given_name']
    })

    flash('', 'upload_success')

    return redirect(url_for('home'))


import config
if __name__ == '__main__':
    app.config.from_object(config.DevelopmentConfig())
    app.run(host='127.0.0.1', port=8000)
else:
    app.config.from_object(config.ProductionConfig())