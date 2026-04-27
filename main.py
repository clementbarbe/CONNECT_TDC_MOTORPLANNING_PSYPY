import sys
import signal
from PyQt6.QtWidgets import QApplication
from gui.menu import ExperimentMenu
from utils.logger import get_logger

signal.signal(signal.SIGINT, signal.SIG_DFL)

# Tâches qui n'ont pas besoin d'une fenêtre PsychoPy
_NO_PSYCHOPY_WINDOW = {"CameraCalibration"}


def show_menu_and_get_config(app, last_config=None):
    menu = ExperimentMenu(last_config)
    menu.show()
    app.exec()
    config = menu.get_config()
    menu.deleteLater()
    app.processEvents()
    return config


def run_task_logic(config):
    logger = get_logger()
    from utils.task_factory import create_task

    task_name = config.get('tache')

    # ── Tâches sans fenêtre PsychoPy (calibration, etc.) ──────────────────
    if task_name in _NO_PSYCHOPY_WINDOW:
        task = create_task(config, win=None)
        if not task:
            logger.err(f"Factory Error: Could not create task '{task_name}'")
            return
        try:
            task.run(**getattr(task, 'run_kwargs', {}))
        except Exception as e:
            logger.err(f"Runtime Error during task execution: {e}")
            import traceback
            traceback.print_exc()
        return

    # ── Tâches avec fenêtre PsychoPy ──────────────────────────────────────
    from psychopy import visual, core, logging
    logging.console.setLevel(logging.ERROR)

    win = visual.Window(
        fullscr=config.get('fullscr', True),
        color='black',
        units='norm',
        screen=config.get('screenid', 0),
        checkTiming=False,
        waitBlanking=True,
    )
    win.mouseVisible = False

    task = create_task(config, win)
    if not task:
        logger.err(f"Factory Error: Could not create task '{task_name}'")
        win.close()
        return

    try:
        win.flip()
        core.wait(0.5)
        task.run(**getattr(task, 'run_kwargs', {}))
    except Exception as e:
        logger.err(f"Runtime Error during task execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        win.close()


def main():
    logger = get_logger()
    app = QApplication(sys.argv)
    last_config = None

    while True:
        config = show_menu_and_get_config(app, last_config)

        if not config:
            logger.log("Sortie demandée par l'utilisateur.")
            break

        try:
            logger.log(f"Lancement de la tâche : {config.get('tache', 'Unknown')}...")
            run_task_logic(config)
            last_config = config
        except Exception as e:
            logger.err(f"Erreur fatale dans la boucle principale : {e}")

    logger.log("Application shutdown.")
    app.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()