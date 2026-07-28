# backend/run.py
# Entrypoint de desarrollo. En produccion se sirve con un WSGI real.

from app import create_app

app = create_app()

if __name__ == '__main__':
    # 127.0.0.1 y no 0.0.0.0: en desarrollo no exponemos la API a la red
    app.run(host='127.0.0.1', port=5000, debug=app.config['DEBUG'])
