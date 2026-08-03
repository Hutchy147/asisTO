"""
backend/scripts/generar_hashes.py

Genera hashes bcrypt reales para los usuarios del seed e imprime los UPDATE
de SQL correspondientes.

Existe porque los contrasena_hash de seed.sql son placeholders: no son
bcrypt valido y ningun login funciona con ellos. Los hashes NO se escriben
a mano en seed.sql porque bcrypt genera un salt distinto en cada corrida,
asi que hardcodearlos daria una unica contrasena fija commiteada en el
repositorio, que es justo lo que se quiere evitar.

Uso (desde backend/, con el venv activo):

    python scripts/generar_hashes.py                    # imprime el SQL
    python scripts/generar_hashes.py --aplicar          # lo aplica a la base

La contrasena por defecto es de DESARROLLO. No usar en ningun entorno real.
"""

import argparse
import os
import sys

# Permite ejecutar el script directamente desde backend/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import bcrypt  # noqa: E402

CONTRASENA_DESARROLLO = 'asisto2026'

# Los 6 usuarios del seed. Si cambian en seed.sql, cambian aca.
EMAILS_SEED = (
    'laura.fernandez@asisto.local',
    'diego.moyano@asisto.local',
    'silvia.quiroga@asisto.local',
    'marta.ledesma@asisto.local',
    'jorge.bustos@asisto.local',
    'camila.rios@asisto.local',
)


def hashear(contrasena):
    return bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def escapar(texto):
    """Escapa comillas simples para SQL. Los hashes bcrypt no las traen."""
    return texto.replace("\\", "\\\\").replace("'", "\\'")


def generar_sentencias(contrasena, emails=EMAILS_SEED):
    """Un hash distinto por usuario: cada uno con su propio salt."""
    sentencias = []
    for email in emails:
        sentencias.append(
            "UPDATE usuarios SET contrasena_hash = '{}' WHERE email = '{}';".format(
                escapar(hashear(contrasena)), escapar(email)
            )
        )
    return sentencias


def emails_de_la_base():
    """Todos los emails cargados en usuarios. Para seeds con otros usuarios."""
    from app import create_app, db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        filas = db.session.execute(text('SELECT email FROM usuarios ORDER BY id')).all()
    return [fila[0] for fila in filas]


def aplicar(sentencias):
    """Aplica los UPDATE usando la configuracion del .env."""
    from app import create_app, db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        for sentencia in sentencias:
            db.session.execute(text(sentencia))
        db.session.commit()

        total = db.session.execute(
            text('SELECT COUNT(*) FROM usuarios WHERE contrasena_hash LIKE :patron'),
            {'patron': '$2b$%'},
        ).scalar()

    return total


def main():
    parser = argparse.ArgumentParser(
        description='Genera hashes bcrypt para los usuarios del seed.'
    )
    parser.add_argument(
        '--contrasena', default=CONTRASENA_DESARROLLO,
        help=f'Contrasena a hashear (por defecto: {CONTRASENA_DESARROLLO})',
    )
    parser.add_argument(
        '--aplicar', action='store_true',
        help='Aplica los UPDATE a la base en vez de solo imprimirlos.',
    )
    parser.add_argument(
        '--todos', action='store_true',
        help='Toma los emails de la base en vez de la lista de seed.sql. '
             'Necesario despues de cargar seed_demo.sql, que trae otros '
             'usuarios. Requiere conexion.',
    )
    args = parser.parse_args()

    emails = emails_de_la_base() if args.todos else EMAILS_SEED
    if not emails:
        print('-- No hay usuarios cargados en la base. Corré primero un seed.')
        return

    sentencias = generar_sentencias(args.contrasena, emails)

    print('-- Hashes bcrypt para los usuarios del seed')
    print(f'-- Contrasena: {args.contrasena}')
    print('-- Cada usuario lleva un salt distinto, por eso los hashes diferen.')
    print()
    for sentencia in sentencias:
        print(sentencia)

    if args.aplicar:
        print()
        total = aplicar(sentencias)
        print(f'-- Aplicado. Usuarios con hash bcrypt valido: {total}')


if __name__ == '__main__':
    main()
