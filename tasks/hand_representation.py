# hand_representation.py
"""
Hand Representation Task
========================

Principe :
    - 10 positions au total (2 zones x 5 doigts)
    - 1 block = 100 trials, 10 miniblocks de 10 trials
    - chaque miniblock contient les 10 positions une fois, ordre randomisé
    - à chaque trial :
        1) affichage image cible (miroir si main gauche)
        2) progress bar 7 sec (noire sur fond gris)
        3) acquisition webcam
        4) sauvegarde photo + log CSV
"""

import os
import csv
import cv2
import random
from datetime import datetime

from psychopy import visual, core

from utils.base_task import BaseTask


class HandRepresentationTask(BaseTask):

    DEFAULT_POSITIONS = [
        {"label": "thumb_zone1",  "finger": "thumb",  "zone": 1, "image": "a1.png"},
        {"label": "thumb_zone2",  "finger": "thumb",  "zone": 2, "image": "a2.png"},
        {"label": "index_zone1",  "finger": "index",  "zone": 1, "image": "a3.png"},
        {"label": "index_zone2",  "finger": "index",  "zone": 2, "image": "a4.png"},
        {"label": "middle_zone1", "finger": "middle", "zone": 1, "image": "a5.png"},
        {"label": "middle_zone2", "finger": "middle", "zone": 2, "image": "a6.png"},
        {"label": "ring_zone1",   "finger": "ring",   "zone": 1, "image": "a7.png"},
        {"label": "ring_zone2",   "finger": "ring",   "zone": 2, "image": "a8.png"},
        {"label": "little_zone1", "finger": "little", "zone": 1, "image": "a9.png"},
        {"label": "little_zone2", "finger": "little", "zone": 2, "image": "a10.png"},
    ]

    BACKGROUND_COLOR = [0, 0, 0]

    # Barre de progression : géométrie en coordonnées norm
    BAR_Y = -0.75
    BAR_LEFT = -0.59
    BAR_MAX_WIDTH = 1.18
    BAR_TRACK_W = 1.2
    BAR_TRACK_H = 0.08
    BAR_FILL_H = 0.06

    def __init__(self, win, nom, session='01',
                 n_blocks=1,
                 trial_duration=7.0,
                 camera_index=1,
                 hand='droite',
                 enregistrer=True,
                 positions=None,
                 **kwargs):

        super().__init__(
            win=win,
            nom=nom,
            session=session,
            task_name="HandRepresentation",
            folder_name="hand_representation",
            eyetracker_actif=False,
            parport_actif=False,
            enregistrer=enregistrer,
            et_prefix='HND'
        )

        self.n_blocks = int(n_blocks)
        self.trial_duration = float(trial_duration)
        self.camera_index = int(camera_index)

        self.hand = hand.lower().strip()
        if self.hand not in ('droite', 'gauche'):
            raise ValueError(
                f"Le paramètre 'hand' doit être 'droite' ou 'gauche'. Reçu : '{hand}'"
            )
        self.flip_horiz = (self.hand == 'gauche')

        self.positions = positions if positions is not None else self.DEFAULT_POSITIONS
        self.global_records = []

        self.hand_img_dir = os.path.join(self.img_dir, 'hand')
        self.photo_dir = os.path.join(self.data_dir, 'photos')

        if self.enregistrer:
            os.makedirs(self.photo_dir, exist_ok=True)

        self.win.color = self.BACKGROUND_COLOR

        self._validate_positions()
        self._setup_stimuli()
        self._preload_images()
        self._init_incremental_file()

        self.camera = None

        hand_label = "GAUCHE (flip)" if self.flip_horiz else "DROITE"
        self.logger.ok("=" * 60)
        self.logger.ok("HAND REPRESENTATION TASK READY")
        self.logger.ok(f"Participant: {self.nom} | Session: {self.session}")
        self.logger.ok(f"Main: {hand_label}")
        self.logger.ok(f"Blocks: {self.n_blocks} | Trial duration: {self.trial_duration}s")
        self.logger.ok(f"Positions: {len(self.positions)}")
        self.logger.ok("=" * 60)

    # =========================================================================
    # INITIALISATION
    # =========================================================================

    def _validate_positions(self):
        if len(self.positions) != 10:
            raise ValueError(
                f"La tâche attend exactement 10 positions. Reçu: {len(self.positions)}"
            )
        required = {'label', 'finger', 'zone', 'image'}
        for i, pos in enumerate(self.positions):
            missing = required - set(pos.keys())
            if missing:
                raise ValueError(f"Position {i} invalide, champs manquants: {missing}")

    def _setup_stimuli(self):
        self.image_stim = visual.ImageStim(
            self.win,
            image=None,
            pos=(0, 0.1),
            size=(1.1, 1.1),
            flipHoriz=self.flip_horiz
        )

        # Piste (fond de la barre) — gris clair
        self.progress_track = visual.Rect(
            self.win,
            width=self.BAR_TRACK_W,
            height=self.BAR_TRACK_H,
            pos=(0, self.BAR_Y),
            lineColor=[0.6, 0.6, 0.6],
            lineWidth=2,
            fillColor=[0.3, 0.3, 0.3]
        )

        # Remplissage noir — Rect classique, PAS de anchor
        self.progress_fill = visual.Rect(
            self.win,
            width=0.001,
            height=self.BAR_FILL_H,
            pos=(self.BAR_LEFT, self.BAR_Y),
            lineColor=None,
            fillColor=[-1, -1, -1]
        )

    def _preload_images(self):
        self.loaded_images = {}
        for pos in self.positions:
            img_path = os.path.join(self.hand_img_dir, pos['image'])
            if not os.path.exists(img_path):
                raise FileNotFoundError(f"Image introuvable: {img_path}")
            self.loaded_images[pos['label']] = img_path

    def _open_camera(self):
        self.logger.log(f"Opening webcam index={self.camera_index}")
        self.camera = cv2.VideoCapture(self.camera_index)
        if self.camera is None or not self.camera.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la webcam index={self.camera_index}")
        ret, frame = self.camera.read()
        if not ret or frame is None:
            self.camera.release()
            self.camera = None
            raise RuntimeError(
                f"Webcam ouverte mais lecture impossible sur index={self.camera_index}"
            )
        self.logger.ok(f"Webcam ouverte sur index={self.camera_index}")

    def _close_camera(self):
        if self.camera is not None:
            try:
                self.camera.release()
                self.logger.log("Webcam fermée.")
            except Exception:
                pass
            self.camera = None

    # =========================================================================
    # DESIGN / RANDOMISATION
    # =========================================================================

    def _build_block_trials(self, block_idx):
        trials = []
        for miniblock_idx in range(10):
            miniblock_positions = self.positions.copy()
            random.shuffle(miniblock_positions)
            for trial_in_miniblock, pos in enumerate(miniblock_positions):
                trial_global = len(trials)
                trials.append({
                    'block_idx': block_idx,
                    'miniblock_idx': miniblock_idx,
                    'trial_in_miniblock': trial_in_miniblock,
                    'trial_in_block': trial_global,
                    'position_label': pos['label'],
                    'finger': pos['finger'],
                    'zone': pos['zone'],
                    'image_file': pos['image'],
                })
        return trials

    # =========================================================================
    # AFFICHAGE
    # =========================================================================

    def _show_instructions(self):
        hand_txt = "main gauche" if self.hand == 'gauche' else "main droite"
        txt = (
            "Tâche de représentation de la main\n\n"
            f"Main utilisée : {hand_txt}\n\n"
            "Une image indiquant une zone d'un doigt va apparaître.\n"
            "Gardez la position demandée jusqu'à la fin de la barre de progression.\n"
            "Une photo sera prise automatiquement à la fin.\n\n"
            "Appuyez sur une touche pour commencer."
        )
        self.show_instructions(text_override=txt)

    def _draw_progress_screen(self, image_path, elapsed, duration):
        """
        Dessine image + barre de progression.
        Le Rect de remplissage est repositionné par son centre
        pour grandir vers la droite depuis BAR_LEFT.
        """
        progress = min(max(elapsed / duration, 0.0), 1.0)
        fill_w = max(0.001, self.BAR_MAX_WIDTH * progress)
        fill_cx = self.BAR_LEFT + fill_w * 0.5

        self.image_stim.image = image_path

        self.progress_fill.width = fill_w
        self.progress_fill.pos = (fill_cx, self.BAR_Y)

        self.image_stim.draw()
        self.progress_track.draw()
        self.progress_fill.draw()
        self.win.flip()

    # =========================================================================
    # ACQUISITION PHOTO
    # =========================================================================

    def _build_photo_filename(self, trial):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        return (
            f"{self.nom}_"
            f"{self.hand}_"
            f"B{trial['block_idx'] + 1:02d}_"
            f"M{trial['miniblock_idx'] + 1:02d}_"
            f"T{trial['trial_in_block'] + 1:03d}_"
            f"{trial['finger']}_z{trial['zone']}_"
            f"{timestamp}.jpg"
        )

    def _capture_photo(self, trial):
        if self.camera is None:
            raise RuntimeError("Webcam non initialisée.")
        frame = None
        for _ in range(3):
            ret, current = self.camera.read()
            if ret and current is not None:
                frame = current
        if frame is None:
            raise RuntimeError("Échec acquisition webcam.")
        filename = self._build_photo_filename(trial)
        save_path = os.path.join(self.photo_dir, filename)
        ok = cv2.imwrite(save_path, frame)
        if not ok:
            raise RuntimeError(f"Échec sauvegarde photo: {save_path}")
        return save_path, filename

    # =========================================================================
    # LOGGING
    # =========================================================================

    def _log_trial(self, trial, image_path, photo_path, photo_filename,
                   image_onset, capture_time):
        record = {
            'participant': self.nom,
            'session': self.session,
            'task_name': self.task_name,
            'hand': self.hand,
            'flip_horiz': self.flip_horiz,
            'block_idx': trial['block_idx'],
            'block_number': trial['block_idx'] + 1,
            'miniblock_idx': trial['miniblock_idx'],
            'miniblock_number': trial['miniblock_idx'] + 1,
            'trial_in_miniblock': trial['trial_in_miniblock'],
            'trial_in_block': trial['trial_in_block'],
            'position_label': trial['position_label'],
            'finger': trial['finger'],
            'zone': trial['zone'],
            'image_file': trial['image_file'],
            'image_path': image_path,
            'photo_filename': photo_filename,
            'photo_path': photo_path,
            'image_onset': round(image_onset, 4),
            'capture_time_task': round(capture_time, 4),
            'trial_duration': self.trial_duration,
            'wall_timestamp': datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f'),
        }
        self.global_records.append(record)
        self.save_trial_incremental(record)

    def _print_trial_feedback(self, trial, capture_time, photo_filename):
        print(
            f"  B{trial['block_idx'] + 1:02d} "
            f"M{trial['miniblock_idx'] + 1:02d} "
            f"T{trial['trial_in_block'] + 1:03d} | "
            f"{self.hand[0].upper()} | "
            f"{trial['finger']} z{trial['zone']} | "
            f"t={capture_time:7.3f}s | "
            f"{photo_filename}"
        )

    # =========================================================================
    # TRIAL / BLOCK
    # =========================================================================

    def run_trial(self, trial, total_trials):
        image_path = self.loaded_images[trial['position_label']]

        onset = self.task_clock.getTime()
        trial_clock = core.Clock()

        while trial_clock.getTime() < self.trial_duration:
            elapsed = trial_clock.getTime()
            self._draw_progress_screen(
                image_path=image_path,
                elapsed=elapsed,
                duration=self.trial_duration
            )
            self.get_keys(key_list=[])

        capture_time = self.task_clock.getTime()
        photo_path, photo_filename = self._capture_photo(trial)

        self._log_trial(
            trial=trial,
            image_path=image_path,
            photo_path=photo_path,
            photo_filename=photo_filename,
            image_onset=onset,
            capture_time=capture_time
        )
        self._print_trial_feedback(trial, capture_time, photo_filename)

    def run_block(self, block_idx):
        trials = self._build_block_trials(block_idx)
        total_trials = len(trials)

        print("\n" + "=" * 60)
        print(f"BLOCK {block_idx + 1}/{self.n_blocks} — {total_trials} trials — Main {self.hand}")
        print("=" * 60)

        self.logger.log(f"START BLOCK {block_idx + 1}")
        for trial in trials:
            self.run_trial(trial, total_trials)
        self.logger.log(f"END BLOCK {block_idx + 1}")

    # =========================================================================
    # SESSION
    # =========================================================================

    def _start_session(self):
        self._show_instructions()
        self.task_clock.reset()
        self.logger.ok("Session started.")

    def _end_session(self):
        saved_path = self.save_data(
            data_list=self.global_records,
            filename_suffix="_final"
        )
        try:
            if self.win and not self.win._closed:
                self.instr_stim.text = "Fin de la session.\nMerci."
                self.instr_stim.draw()
                self.win.flip()
                core.wait(2.0)
        except Exception:
            pass
        return saved_path

    # =========================================================================
    # ENTRY POINT
    # =========================================================================

    def run(self):
        saved_path = None
        try:
            self._open_camera()
            self._start_session()
            for block_idx in range(self.n_blocks):
                self.run_block(block_idx)
            self.logger.ok("Task completed successfully.")
        except (KeyboardInterrupt, SystemExit):
            self.logger.warn("Interruption manuelle.")
        except Exception as e:
            self.logger.err(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            self._close_camera()
            saved_path = self._end_session()
        return saved_path