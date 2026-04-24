# task_factory.py
from tasks.camera_calibration  import CameraCalibrationTask
from tasks.hand_representation import HandRepresentationTask


def create_task(config, win):
    """Instantiate and return the appropriate task object.

    The caller is responsible for running the task::

        task = create_task(config, win)
        if task is not None:
            task.run(**getattr(task, "run_kwargs", {}))
    """
    base_kwargs = {
        "win":         win,
        "nom":         config["nom"],
        "enregistrer": config["enregistrer"],
    }
    task_name = config["tache"]

    # ═════════════════════════════════════════════════════════════════════
    # Camera Calibration
    # ═════════════════════════════════════════════════════════════════════
    if task_name == "CameraCalibration":

        task = CameraCalibrationTask(
            **base_kwargs,
            session      = config.get("session",      "01"),
            camera_index = config.get("camera_index", 0),
        )
        task.run_kwargs = {
            "calibration_types": tuple(config.get("calibration_types",
                                                  ("table", "plateau"))),
            "flip_feed":         config.get("flip_feed", False),
        }
        return task

    # ═════════════════════════════════════════════════════════════════════
    # Hand Representation
    # ═════════════════════════════════════════════════════════════════════
    elif task_name == "HandRepresentation":

        task = HandRepresentationTask(
            **base_kwargs,
            session        = config.get("session",        "01"),
            n_blocks       = config.get("n_blocks",       1),
            trial_duration = config.get("trial_duration", 4.0),
            camera_index   = config.get("camera_index",   0),
            hand           = config.get("hand",           "droite"),
        )
        task.run_kwargs = {}
        return task

    else:
        print(f"Tâche inconnue : {task_name}")
        return None