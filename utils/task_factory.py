# task_factory.py
from tasks.hand_representation import HandRepresentationTask


def create_task(config, win):

    base_kwargs = {
        "win": win,
        "nom": config["nom"],
        "enregistrer": config["enregistrer"],
    }
    task_name = config["tache"]

    # ═════════════════════════════════════════════════════════════════════
    # HandRepresentation
    # ═════════════════════════════════════════════════════════════════════
    if task_name == "HandRepresentation":

        return HandRepresentationTask(
            **base_kwargs,
            n_blocks=config.get("n_blocks", 1),
            trial_duration=config.get("trial_duration", 4.0),
            camera_index=config.get("camera_index", 0),
            handedness=config.get("handedness", "droitier"),
            block_label=config.get("block_label", "Block 1 Pre"),
            block_number=config.get("block_number", 1),
        )

    else:
        print(f"Tâche inconnue : {task_name}")
        return None