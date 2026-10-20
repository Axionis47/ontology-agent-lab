"""Isolated official grading, with an explicit read-only MC01 implementation handoff."""
import json
import subprocess
import sys
from core import ROOT, WORLD, configure_world, digest, encode, Inconclusive


def application_hashes(models):
    result = {}
    for name in models.app_names:
        sqlmodel = models[name].SQLModel
        connection = sqlmodel.db.connection
        tables = {}
        for model in sqlmodel.models():
            table = model.__tablename__
            quoted = '"'+table.replace('"', '""')+'"'
            columns = list(connection.execute('PRAGMA table_info('+quoted+')'))
            rows = sorted((list(row) for row in connection.execute('SELECT * FROM '+quoted)), key=encode)
            tables[table] = digest({'columns':columns, 'rows':rows})
        result[name] = tables
    return result


def grade_saved(task_id, experiment):
    process = subprocess.run([sys.executable, str(ROOT/'grading.py'), task_id, experiment],
                             cwd=ROOT, capture_output=True, text=True)
    lines = [line[len('OWB_GRADE:'):] for line in process.stdout.splitlines() if line.startswith('OWB_GRADE:')]
    if process.returncode or len(lines) != 1:
        raise Inconclusive('Isolated official grading failed; inspect local worker log')
    return json.loads(lines[0])


def main():
    configure_world()
    from appworld import evaluate_task
    from appworld.task import Task
    from appworld.collections.models import ModelCollection
    from appworld.apps.lib.models.db import get_db_home_path
    task_id, experiment = sys.argv[1:]
    grade = evaluate_task(task_id, experiment_name=experiment, suppress_errors=True).to_dict()
    task = Task.load(task_id=task_id, load_ground_truth=False)
    directory = WORLD/'experiments/outputs'/experiment/'tasks'/task_id/'dbs'
    models = ModelCollection.load(
        to_db_home_path=get_db_home_path(storage_type='memory', type='task_output', task_id=task_id),
        from_db_home_path=str(directory), load_apps=task.allowed_apps)
    packet = {'grade':grade, 'application_hashes':application_hashes(models),
              'state_hash_method':'canonical ORM tables, columns, sorted rows; search index internals excluded',
              'model_hashes_sha256':digest((directory/'model_hashes.json').read_bytes()),
              'evaluator':'official AppWorld evaluate_task', 'isolation':'fresh subprocess',
              'model_output':'not-a-model'}
    print('OWB_GRADE:'+json.dumps(packet))


if __name__ == '__main__':
    main()
