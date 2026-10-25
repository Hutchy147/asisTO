"""
backend/scripts/comparar_modelos_ia.py

Genera el MISMO informe con varios modelos de Ollama para compararlos lado a
lado: tiempo, velocidad, largo, otro alfabeto y marcas [COMPLETAR]. Cada
informe queda en un archivo para leerlo.

Uso (desde backend/, con el venv activo y `ollama serve` corriendo):

    python scripts/comparar_modelos_ia.py --listar
    python scripts/comparar_modelos_ia.py --paciente 3 --periodo 2026-10
    python scripts/comparar_modelos_ia.py --paciente 3 --periodo 2026-10 --modelos llama3.2:3b gemma3:4b
    python scripts/comparar_modelos_ia.py --paciente 3 --temperatura 0.3 --repeticion 1.1 --semilla 0

Los parametros (--temperatura, --repeticion, --semilla, --top-p) se aplican a
todos los modelos de la corrida; sin ellos se usan los del .env o los de fabrica.

Solo LEE de la base y no guarda ningun informe. Los textos salen en
backend/scripts/_salida_ia/ (carpeta ignorada por git: lleva datos clinicos).
"""

import argparse
import datetime as dt
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db  # noqa: E402
from app.models import Paciente  # noqa: E402
from app.services import informes_generador as g  # noqa: E402

MODELOS_POR_DEFECTO = ['llama3.2:3b', 'gemma3:4b']
SALIDA = os.path.join(os.path.dirname(__file__), '_salida_ia')


def _periodo_por_defecto():
    return dt.date.today().strftime('%Y-%m')


def _listar():
    from sqlalchemy import text
    filas = db.session.execute(text(
        'SELECT p.id, p.nombre, p.apellido, COUNT(s.id) AS sesiones '
        'FROM pacientes p LEFT JOIN sesiones s ON s.id_paciente = p.id '
        'GROUP BY p.id ORDER BY sesiones DESC LIMIT 15'
    )).all()
    print('id  paciente                         sesiones')
    for f in filas:
        print(f'{f[0]:<3} {f[1] + " " + f[2]:<32} {f[3]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--listar', action='store_true', help='muestra pacientes con mas sesiones')
    ap.add_argument('--paciente', type=int)
    ap.add_argument('--tipo', default='mensual', choices=['mensual', 'semestral'])
    ap.add_argument('--periodo', default=_periodo_por_defecto(), help='AAAA-MM o AAAA-S1/S2')
    ap.add_argument('--modelos', nargs='+', default=MODELOS_POR_DEFECTO)
    ap.add_argument('--temperatura', type=float, help='0 a 1; mas bajo = mas fiel y repetible')
    ap.add_argument('--repeticion', type=float, help='1.0 a 1.3; mas alto = menos frases repetidas')
    ap.add_argument('--semilla', type=int, help='0 = distinto en cada corrida')
    ap.add_argument('--top-p', type=float, dest='top_p')
    ap.add_argument('--url', default='http://127.0.0.1:11434')
    ap.add_argument('--ctx', type=int, default=8192)
    ap.add_argument('--timeout', type=int, default=600)
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        if args.listar:
            _listar()
            return
        if not args.paciente:
            ap.error('falta --paciente (usar --listar para ver los ids)')
        paciente = db.session.get(Paciente, args.paciente)
        if paciente is None:
            sys.exit(f'No existe el paciente {args.paciente}.')

        clave, desde, hasta = g.calcular_periodo(args.tipo, args.periodo)
        datos = g.recolectar(paciente, args.tipo, desde, hasta)
        datos['clave'] = clave
        etiqueta = g.etiqueta_periodo(args.tipo, clave)
        cabecera = g._encabezado(datos, etiqueta)
        entrada = g.datos_para_ia(datos)
        print(f'Paciente {paciente.id} | {args.tipo} {clave} | {len(datos["diarios"])} sesiones | '
              f'{len(str(entrada))} caracteres hacia la IA\n')

        os.makedirs(SALIDA, exist_ok=True)
        resumen = []
        for modelo in args.modelos:
            print(f'--- {modelo} ...', flush=True)
            opciones = {}
            if args.temperatura is not None:
                opciones['temperature'] = args.temperatura
            if args.repeticion is not None:
                opciones['repeat_penalty'] = args.repeticion
            if args.top_p is not None:
                opciones['top_p'] = args.top_p
            if args.semilla:
                opciones['seed'] = args.semilla
            proveedor = g.ProveedorOllama(args.url, modelo, args.timeout, args.ctx, '10m', opciones)
            if args.semilla == 0:
                proveedor.opciones.pop('seed', None)
            inicio = time.time()
            fila = {'modelo': modelo, 'reintentos': 0, 'problemas': []}
            try:
                texto = g._redactar_con_ia(proveedor, datos, cabecera)
                fila['estado'] = 'ok'
            except Exception as fallo:  # noqa: BLE001 - es una herramienta de prueba
                texto = f'(sin informe: {type(fallo).__name__}: {fallo})'
                fila['estado'] = f'fallo: {type(fallo).__name__}'
            fila['segundos'] = round(time.time() - inicio, 1)
            m = proveedor.ultima_medicion or {}
            fila['tokens_s'] = m.get('tokens_por_s')
            fila['palabras'] = len(texto.split())
            fila['completar'] = texto.count(g.MARCA_COMPLETAR)
            fila['otro_alfabeto'] = bool(g._OTRO_ALFABETO.search(texto))
            fila['reintentos'] = proveedor.reintentos
            fila['problemas'] = list(proveedor.problemas)
            nombre = modelo.replace(':', '_').replace('/', '_')
            ruta = os.path.join(SALIDA, f'{args.tipo}_{clave}_p{paciente.id}_{nombre}.md')
            with open(ruta, 'w', encoding='utf-8') as archivo:
                archivo.write(texto)
            fila['archivo'] = ruta
            resumen.append(fila)
            print(f'    {fila["estado"]} en {fila["segundos"]} s, {fila["tokens_s"]} tokens/s, {fila["palabras"]} palabras')

        print('\nmodelo            estado  seg    tok/s  palabras  [COMPLETAR]  2da pasada  problemas que quedan')
        for f in resumen:
            print(f'{f["modelo"]:<17} {f["estado"][:6]:<7} {f["segundos"]:<6} {str(f["tokens_s"]):<6} '
                  f'{f["palabras"]:<9} {f["completar"]:<12} {"si" if f["reintentos"] else "no":<11} '
                  f'{len(f["problemas"])}')
        for f in resumen:
            for problema in f['problemas']:
                print(f'  {f["modelo"]}: {problema}')
        print(f'\nInformes en: {SALIDA}')


if __name__ == '__main__':
    main()
