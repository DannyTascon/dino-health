from flask import Flask

from app.config import SECRET_KEY
from app.routes.route import app as main_blueprint

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = SECRET_KEY
app.register_blueprint(main_blueprint)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

