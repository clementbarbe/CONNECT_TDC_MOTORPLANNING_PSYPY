# tasks/camera_calibration.py
"""
Camera Calibration Task
=======================
Lance _calibration_ui.py en subprocess indépendant pour chaque surface.
Évite tout conflit de thread Qt / PsychoPy / psychtoolbox.

Sortie : S{session}_{table|plateau}_calibration.json  dans data_dir/
"""

import json
import os
import sys
import subprocess
import tempfile

from utils.base_task import BaseTask


# Chemin absolu vers le script UI (même dossier que ce fichier)
_UI_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_calibration_ui.py")


class CameraCalibrationTask(BaseTask):
    """Lance la calibration dans un subprocess PyQt6 dédié.

    Aucune dépendance à PsychoPy ou à la fenêtre principale.
    Chaque surface (table / plateau) ouvre sa propre fenêtre.
    """

    def __init__(
        self,
        win,
        nom,
        session="01",
        camera_index=0,
        enregistrer=True,
        **kwargs,
    ):
        super().__init__(
            win=win, nom=nom, session=session,
            task_name="CameraCalibration",
            folder_name="calibration",
            eyetracker_actif=False,
            parport_actif=False,
            enregistrer=enregistrer,
            et_prefix="CAL",
        )
        self.camera_index = int(camera_index)
        self.results      = {}

        self.logger.ok("=" * 60)
        self.logger.ok("CAMERA CALIBRATION — READY")
        self.logger.ok(f"Participant : {self.nom}  |  Session : {self.session}")
        self.logger.ok(f"Camera index: {self.camera_index}")
        self.logger.ok(f"UI script   : {_UI_SCRIPT}")
        self.logger.ok("=" * 60)

    # =========================================================================
    # HELPERS
    # =========================================================================

    @property
    def _session_label(self):
        try:
            return str(int(self.session))
        except ValueError:
            return self.session

    def _save_result(self, result):
        cal_type  = result["calibration_type"]
        filename  = f"S{self._session_label}_{cal_type}_calibration.json"
        save_path = os.path.join(self.data_dir, filename)
        os.makedirs(self.data_dir, exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
        self.logger.ok(f"Calibration saved → {filename}")
        return save_path

    # =========================================================================
    # ENTRY POINT
    # =========================================================================

    def run(self, calibration_types=("table", "plateau"), flip_feed=False):
        """Lance un subprocess de calibration pour chaque surface.

        Parameters
        ----------
        calibration_types : iterable[str]  – 'table', 'plateau', ou les deux
        flip_feed         : bool           – retourner le flux verticalement

        Returns
        -------
        dict  mapping calibration_type → result dict (ou None si annulé)
        """
        try:
            for cal_type in calibration_types:
                self.logger.log(f"Starting calibration: {cal_type.upper()}")

                # Fichier temporaire pour recevoir le JSON du subprocess
                tmp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"calibration_{cal_type}_{os.getpid()}.json",
                )
                # S'assurer qu'il n'existe pas déjà
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

                cmd = [
                    sys.executable, _UI_SCRIPT,
                    "--type",    cal_type,
                    "--camera",  str(self.camera_index),
                    "--nom",     self.nom,
                    "--session", self.session,
                    "--output",  tmp_path,
                ]
                if flip_feed:
                    cmd.append("--flip")

                try:
                    # Lance la fenêtre et attend sa fermeture (max 10 min)
                    proc = subprocess.run(cmd, timeout=600)

                    if proc.returncode == 0 and os.path.exists(tmp_path):
                        with open(tmp_path, encoding="utf-8") as fh:
                            result = json.load(fh)

                        hom_ok = "OK" if result.get("homography") else "FAILED"
                        self.logger.ok(
                            f"Calibration '{cal_type}' confirmed — "
                            f"Homography: {hom_ok}."
                        )
                        self.results[cal_type] = result

                        if self.enregistrer:
                            self._save_result(result)

                    else:
                        self.logger.warn(f"Calibration '{cal_type}' cancelled (code={proc.returncode}).")
                        self.results[cal_type] = None

                except subprocess.TimeoutExpired:
                    self.logger.warn(f"Calibration '{cal_type}' timed out.")
                    self.results[cal_type] = None

                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            self.logger.ok("Calibration session completed.")

        except (KeyboardInterrupt, SystemExit):
            self.logger.warn("Manual interruption.")
        except Exception as e:
            self.logger.err(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise

        return self.results