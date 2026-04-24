# hand_representation.py
"""
Hand Representation Task

Displays finger-position images, captures a webcam photo at the end of each
trial, and logs all results to a CSV file.

Block structure:
    1 block  = 100 trials
    10 miniblocks × 10 positions, each miniblock shuffled independently

Trial sequence:
    0. Warn → SPACE → countdown → REF1 captured → SPACE → start trials
    1. Display target image  (horizontally flipped for right hand)
    2. Fill progress bar over `trial_duration` seconds
    3. Capture webcam photo  →  S{session}_T{trial}__{finger}_Z{zone}.jpg
    4. Show "return to base" message for BASE_RETURN_DURATION seconds  ← NEW
    5. Append row to CSV log
    6. After all trials: warn → SPACE → countdown → REF2 captured

Photo naming:
    Trial photos : S{session}_T{global_trial}__{finger}_Z{zone}.jpg
    Ref photos   : S{session}_REF{1|2}.jpg          (single block)
                   S{session}_B{block}_REF{1|2}.jpg  (multiple blocks)

Finger inversion on flip:
    Source images depict a LEFT hand. When flip_horiz=True (right hand),
    the anatomical mirror is applied to the finger name in the filename:
        thumb ↔ little  |  index ↔ ring  |  middle → middle

Image orientation:
    → hand='gauche' : displayed as-is       (flip_horiz = False)
    → hand='droite' : mirrored horizontally (flip_horiz = True)

Expected directory layout:
    projet/
    ├── images/          ← finger-position images (a1.png … a10.png)
    └── tasks/
        └── hand_representation.py
"""

import os
import cv2
import random
from datetime import datetime

from psychopy import visual, core, event

from utils.base_task import BaseTask


# ---------------------------------------------------------------------------
# Image folder: <project_root>/images/
# The script lives in tasks/, so we go one level up.
# ---------------------------------------------------------------------------
_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
IMAGES_DIR    = os.path.join(_PROJECT_ROOT, "images")


class HandRepresentationTask(BaseTask):
    """PsychoPy task: hand-position display and webcam capture.

    Source images show a LEFT hand. Passing hand='droite' applies a
    horizontal mirror so the displayed hand always matches the participant's
    active hand.

    When the image is flipped, finger labels are also remapped
    (thumb ↔ little, index ↔ ring, middle unchanged) so that filenames
    always reflect the anatomically correct displayed finger.
    """

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

    FINGER_FLIP_MAP = {
        "thumb":  "little",
        "index":  "ring",
        "middle": "middle",
        "ring":   "index",
        "little": "thumb",
    }

    # Progress bar geometry in normalised (-1 → +1) coordinates
    BAR_Y         = -0.75
    BAR_LEFT      = -0.59
    BAR_MAX_WIDTH = 1.18
    BAR_TRACK_W   = 1.2
    BAR_TRACK_H   = 0.08
    BAR_FILL_H    = 0.06

    # ── NEW ──────────────────────────────────────────────────────────────────
    BASE_RETURN_DURATION = 2.0
    # ─────────────────────────────────────────────────────────────────────────
    CAPTURE_WIDTH  = 1920
    CAPTURE_HEIGHT = 1080

    # =========================================================================
    # CONSTRUCTOR
    # =========================================================================

    def __init__(
        self,
        win,
        nom,
        session="01",
        n_blocks=1,
        trial_duration=4.0,
        camera_index=1,
        hand="droite",
        enregistrer=True,
        positions=None,
        images_dir=None,
        **kwargs,
    ):
        super().__init__(
            win=win,
            nom=nom,
            session=session,
            task_name="HandRepresentation",
            folder_name="hand_representation",
            eyetracker_actif=False,
            parport_actif=False,
            enregistrer=enregistrer,
            et_prefix="HND",
        )

        self.n_blocks       = int(n_blocks)
        self.trial_duration = float(trial_duration)
        self.camera_index   = int(camera_index)
        self.images_dir     = images_dir or IMAGES_DIR

        self.hand = hand.lower().strip()
        if self.hand not in ("droite", "gauche"):
            raise ValueError(f"'hand' must be 'droite' or 'gauche'. Got: '{hand}'")

        self.flip_horiz = self.hand == "droite"

        self.positions      = positions if positions is not None else self.DEFAULT_POSITIONS
        self.global_records = []
        self.camera         = None

        self._global_trial_idx = 0

        self.photo_dir = os.path.join(self.data_dir, "photos")
        if self.enregistrer:
            os.makedirs(self.photo_dir, exist_ok=True)

        self.win.color = self.BACKGROUND_COLOR

        self._validate_positions()
        self._setup_stimuli()
        self._preload_images()
        self._init_incremental_file()
        self._log_startup()

    # =========================================================================
    # INITIALISATION
    # =========================================================================

    def _log_startup(self):
        if self.flip_horiz:
            hand_label = "DROITE (mirrored from left-hand source images)"
        else:
            hand_label = "GAUCHE (source images used as-is)"

        self.logger.ok("=" * 60)
        self.logger.ok("HAND REPRESENTATION TASK — READY")
        self.logger.ok(f"Participant : {self.nom}  |  Session : {self.session}")
        self.logger.ok(f"Hand        : {hand_label}")
        self.logger.ok(f"Flip horiz  : {self.flip_horiz}  →  finger map active: {self.flip_horiz}")
        self.logger.ok(f"Blocks      : {self.n_blocks}  |  Duration : {self.trial_duration} s")
        self.logger.ok(f"Base return : {self.BASE_RETURN_DURATION} s after each trial")
        self.logger.ok(f"Images dir  : {self.images_dir}")
        self.logger.ok(f"Positions   : {len(self.positions)}")
        self.logger.ok("=" * 60)

    def _validate_positions(self):
        if len(self.positions) != 10:
            raise ValueError(
                f"Expected exactly 10 positions, got {len(self.positions)}."
            )
        required = {"label", "finger", "zone", "image"}
        for i, pos in enumerate(self.positions):
            missing = required - set(pos.keys())
            if missing:
                raise ValueError(f"Position {i} is missing fields: {missing}")

    def _setup_stimuli(self):
        """Create PsychoPy stimuli: target image, progress bar, countdown text."""
        self.image_stim = visual.ImageStim(
            self.win,
            image=None,
            pos=(0, 0.1),
            size=(1.1, 1.1),
            flipHoriz=self.flip_horiz,
        )
        self.progress_track = visual.Rect(
            self.win,
            width=self.BAR_TRACK_W,
            height=self.BAR_TRACK_H,
            pos=(0, self.BAR_Y),
            lineColor=[0.6, 0.6, 0.6],
            lineWidth=2,
            fillColor=[0.3, 0.3, 0.3],
        )
        self.progress_fill = visual.Rect(
            self.win,
            width=0.001,
            height=self.BAR_FILL_H,
            pos=(self.BAR_LEFT, self.BAR_Y),
            lineColor=None,
            fillColor=[-1, -1, -1],
        )
        self.countdown_stim = visual.TextStim(
            self.win,
            text="",
            pos=(0, 0),
            color=[1, 1, 1],
            height=0.3,
            bold=True,
        )

        # ── NEW ──────────────────────────────────────────────────────────────
        # Dedicated stimulus for the "return to base" inter-trial message.
        self.return_base_stim = visual.TextStim(
            self.win,
            text="Revenez à la position de base.",
            pos=(0, 0),
            color=[1, 1, 1],
            height=0.08,
            bold=True,
            wrapWidth=1.8,
        )
        # ─────────────────────────────────────────────────────────────────────

    def _preload_images(self):
        """Resolve and validate every image path before the task starts."""
        self.loaded_images = {}
        for pos in self.positions:
            img_path = os.path.join(self.images_dir, pos["image"])
            if not os.path.exists(img_path):
                raise FileNotFoundError(f"Image not found: {img_path}")
            self.loaded_images[pos["label"]] = img_path

    # =========================================================================
    # SESSION LABEL HELPER
    # =========================================================================

    @property
    def _session_label(self):
        try:
            return str(int(self.session))
        except ValueError:
            return self.session

    # =========================================================================
    # CAMERA
    # =========================================================================

    def _open_camera(self):
        self.logger.log(f"Opening webcam (index={self.camera_index})")
        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            raise RuntimeError(f"Cannot open webcam at index {self.camera_index}.")

        # ── Force Full HD resolution ──────────────────────────────────────────
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH,  self.CAPTURE_WIDTH)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.CAPTURE_HEIGHT)

        # Read back the resolution actually granted by the driver/hardware
        actual_w = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if actual_w != self.CAPTURE_WIDTH or actual_h != self.CAPTURE_HEIGHT:
            self.logger.warn(
                f"Requested {self.CAPTURE_WIDTH}×{self.CAPTURE_HEIGHT} "
                f"but camera returned {actual_w}×{actual_h}. "
                "Check that your webcam supports 1080p."
            )
        else:
            self.logger.ok(f"Webcam resolution set to {actual_w}×{actual_h} (Full HD).")
        # ─────────────────────────────────────────────────────────────────────

        ret, frame = self.camera.read()
        if not ret or frame is None:
            self.camera.release()
            self.camera = None
            raise RuntimeError(
                f"Webcam opened but first read failed (index={self.camera_index})."
            )
        self.logger.ok(f"Webcam ready (index={self.camera_index})")

    def _close_camera(self):
        if self.camera is not None:
            try:
                self.camera.release()
                self.logger.log("Webcam closed.")
            except Exception:
                pass
            self.camera = None

    # =========================================================================
    # BLOCK DESIGN
    # =========================================================================

    def _build_block_trials(self, block_idx):
        """Return 100 trial dicts: 10 shuffled miniblocks × 10 positions."""
        trials = []
        for miniblock_idx in range(10):
            miniblock_positions = self.positions.copy()
            random.shuffle(miniblock_positions)
            for trial_in_miniblock, pos in enumerate(miniblock_positions):
                trials.append({
                    "block_idx":          block_idx,
                    "miniblock_idx":      miniblock_idx,
                    "trial_in_miniblock": trial_in_miniblock,
                    "trial_in_block":     len(trials),
                    "position_label":     pos["label"],
                    "finger":             pos["finger"],
                    "zone":               pos["zone"],
                    "image_file":         pos["image"],
                })
        return trials

    # =========================================================================
    # FINGER NAME HELPER
    # =========================================================================

    def _get_displayed_finger(self, finger):
        if self.flip_horiz:
            return self.FINGER_FLIP_MAP.get(finger, finger)
        return finger

    # =========================================================================
    # DISPLAY HELPERS
    # =========================================================================

    def _show_instructions(self):
        hand_txt = "main gauche" if self.hand == "gauche" else "main droite"
        text = (
            "Tâche de représentation de la main\n\n"
            f"Main utilisée : {hand_txt}\n\n"
            "À chaque essai, une image apparaît indiquant un doigt et une zone précise.\n\n"
            "→ Pointez cette zone avec votre doigt AVANT la fin de la barre de progression.\n"
            "→ Maintenez ensuite votre doigt en place sans bouger\n"
            "   jusqu'à l'apparition du message « Revenez à la position de base ».\n"
            "→ Revenez alors à la position de repos pendant 2 secondes.\n\n"
            "Une photo de votre main sera prise automatiquement à la fin de chaque essai.\n\n"
            "Appuyez sur une touche pour commencer."
        )
        self.show_instructions(text_override=text)

    def _show_ref_screen(self, message):
        """Display a plain text message and flip the window."""
        try:
            self.instr_stim.text = message
            self.instr_stim.draw()
            self.win.flip()
        except Exception:
            msg = visual.TextStim(
                self.win,
                text=message,
                pos=(0, 0),
                color=[1, 1, 1],
                height=0.05,
                wrapWidth=1.8,
            )
            msg.draw()
            self.win.flip()

    def _wait_for_space(self, message=None):
        """Optionally display `message`, then block until SPACE is pressed."""
        if message is not None:
            self._show_ref_screen(message)
        event.clearEvents()
        event.waitKeys(keyList=["space"])

    def _show_countdown(self, seconds=3):
        """Display a large centred countdown: 3 … 2 … 1, one digit per second."""
        for count in range(seconds, 0, -1):
            self.countdown_stim.text = str(count)
            self.countdown_stim.draw()
            self.win.flip()
            core.wait(1.0)

    def _draw_progress_screen(self, image_path, elapsed, duration):
        """Render the target image and the growing progress bar, then flip."""
        progress = min(max(elapsed / duration, 0.0), 1.0)
        fill_w   = max(0.001, self.BAR_MAX_WIDTH * progress)

        self.image_stim.image    = image_path
        self.progress_fill.width = fill_w
        self.progress_fill.pos   = (self.BAR_LEFT + fill_w * 0.5, self.BAR_Y)

        self.image_stim.draw()
        self.progress_track.draw()
        self.progress_fill.draw()
        self.win.flip()

    # ── NEW ──────────────────────────────────────────────────────────────────
    def _show_return_to_base(self):
        """Display 'Revenez à la position de base.' for BASE_RETURN_DURATION s.

        Called after every trial photo capture so the participant has time to
        reset their hand before the next image appears.
        """
        self.return_base_stim.draw()
        self.win.flip()
        core.wait(self.BASE_RETURN_DURATION)
    # ─────────────────────────────────────────────────────────────────────────

    # =========================================================================
    # PHOTO CAPTURE
    # =========================================================================

    def _build_photo_filename(self, trial):
        finger = self._get_displayed_finger(trial["finger"])
        return (
            f"S{self._session_label}_"
            f"T{self._global_trial_idx + 1}__"
            f"{finger}_"
            f"Z{trial['zone']}.jpg"
        )

    def _build_ref_photo_filename(self, ref_number, block_idx):
        sl = self._session_label
        if self.n_blocks > 1:
            return f"S{sl}_B{block_idx + 1}_REF{ref_number}.jpg"
        return f"S{sl}_REF{ref_number}.jpg"

    def _read_camera_frame(self):
        """Read up to 3 frames to flush buffered stale frames; return latest."""
        frame = None
        for _ in range(3):
            ret, current = self.camera.read()
            if ret and current is not None:
                frame = current
        return frame

    def _capture_photo(self, trial):
        if self.camera is None:
            raise RuntimeError("Webcam is not initialised.")

        frame = self._read_camera_frame()
        if frame is None:
            raise RuntimeError("Webcam capture failed after 3 attempts.")

        filename  = self._build_photo_filename(trial)
        save_path = os.path.join(self.photo_dir, filename)
        if not cv2.imwrite(save_path, frame):
            raise RuntimeError(f"Could not save photo: {save_path}")
        return save_path, filename

    def _capture_ref_photo(self, filename):
        if self.camera is None:
            raise RuntimeError("Webcam is not initialised.")

        frame = self._read_camera_frame()
        if frame is None:
            raise RuntimeError("Reference webcam capture failed after 3 attempts.")

        save_path = os.path.join(self.photo_dir, filename)
        if not cv2.imwrite(save_path, frame):
            raise RuntimeError(f"Could not save reference photo: {save_path}")
        self.logger.ok(f"Reference photo saved: {filename}")
        return save_path

    def _capture_ref_with_countdown(self, filename, post_capture_message):
        self._wait_for_space(
            "Une photo de référence de votre main va être prise.\n\n"
            "Placez votre main dans la position de repos,\n"
            "puis appuyez sur ESPACE pour lancer le compte à rebours."
        )
        self._show_countdown(seconds=3)
        self._show_ref_screen("Capture en cours…")
        core.wait(0.1)
        self._capture_ref_photo(filename)
        print(f"  [REF] {filename} enregistrée.")
        self._wait_for_space(post_capture_message)

    # =========================================================================
    # LOGGING
    # =========================================================================

    def _log_trial(self, trial, image_path, photo_path, photo_filename,
                   image_onset, capture_time):
        record = {
            "participant":        self.nom,
            "session":            self.session,
            "task_name":          self.task_name,
            "hand":               self.hand,
            "flip_horiz":         self.flip_horiz,
            "block_idx":          trial["block_idx"],
            "block_number":       trial["block_idx"] + 1,
            "miniblock_idx":      trial["miniblock_idx"],
            "miniblock_number":   trial["miniblock_idx"] + 1,
            "trial_in_miniblock": trial["trial_in_miniblock"],
            "trial_in_block":     trial["trial_in_block"],
            "global_trial":       self._global_trial_idx + 1,
            "position_label":     trial["position_label"],
            "finger_source":      trial["finger"],
            "finger_displayed":   self._get_displayed_finger(trial["finger"]),
            "zone":               trial["zone"],
            "image_file":         trial["image_file"],
            "image_path":         image_path,
            "photo_filename":     photo_filename,
            "photo_path":         photo_path,
            "image_onset":        round(image_onset, 4),
            "capture_time_task":  round(capture_time, 4),
            "trial_duration":     self.trial_duration,
            "wall_timestamp":     datetime.now().strftime("%Y-%m-%d_%H:%M:%S.%f"),
        }
        self.global_records.append(record)
        self.save_trial_incremental(record)

    def _print_trial_summary(self, trial, capture_time, photo_filename):
        displayed_finger = self._get_displayed_finger(trial["finger"])
        print(
            f"  B{trial['block_idx'] + 1:02d} "
            f"M{trial['miniblock_idx'] + 1:02d} "
            f"T{self._global_trial_idx + 1:04d} | "
            f"{self.hand[0].upper()} | "
            f"{displayed_finger} z{trial['zone']} | "
            f"t={capture_time:7.3f} s | "
            f"{photo_filename}"
        )

    # =========================================================================
    # TRIAL & BLOCK EXECUTION
    # =========================================================================

    def run_trial(self, trial, total_trials):
        image_path  = self.loaded_images[trial["position_label"]]
        onset       = self.task_clock.getTime()
        trial_clock = core.Clock()

        # ── Phase 1 : display image + fill progress bar ──────────────────────
        while trial_clock.getTime() < self.trial_duration:
            self._draw_progress_screen(
                image_path=image_path,
                elapsed=trial_clock.getTime(),
                duration=self.trial_duration,
            )
            self.get_keys(key_list=[])

        # ── Phase 2 : capture photo ───────────────────────────────────────────
        capture_time         = self.task_clock.getTime()
        photo_path, photo_fn = self._capture_photo(trial)

        # ── Phase 3 : log ─────────────────────────────────────────────────────
        self._log_trial(
            trial=trial,
            image_path=image_path,
            photo_path=photo_path,
            photo_filename=photo_fn,
            image_onset=onset,
            capture_time=capture_time,
        )
        self._print_trial_summary(trial, capture_time, photo_fn)

        # ── Phase 4 : return-to-base inter-trial screen (NEW) ─────────────────
        self._show_return_to_base()

        # Increment AFTER logging so all methods above see the correct index.
        self._global_trial_idx += 1

    def run_block(self, block_idx):
        trials = self._build_block_trials(block_idx)
        print(f"\n{'=' * 60}")
        print(f"BLOCK {block_idx + 1}/{self.n_blocks} — {len(trials)} trials — Main {self.hand}")
        print("=" * 60)
        self.logger.log(f"START BLOCK {block_idx + 1}")

        # ── REF1 ──────────────────────────────────────────────────────────────
        ref1_fn = self._build_ref_photo_filename(1, block_idx)
        self._capture_ref_with_countdown(
            filename=ref1_fn,
            post_capture_message=(
                "Photo de référence initiale enregistrée  ✓\n\n"
                "Appuyez sur ESPACE pour lancer la tâche."
            ),
        )

        # ── 100 trials ────────────────────────────────────────────────────────
        for trial in trials:
            self.run_trial(trial, len(trials))

        # ── REF2 ──────────────────────────────────────────────────────────────
        ref2_fn = self._build_ref_photo_filename(2, block_idx)
        self._capture_ref_with_countdown(
            filename=ref2_fn,
            post_capture_message=(
                "Photo de référence finale enregistrée  ✓\n\n"
                "Appuyez sur ESPACE pour continuer."
            ),
        )

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
            filename_suffix="_final",
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
        """Open the camera, execute all blocks, save data, close the camera."""
        saved_path = None
        try:
            self._open_camera()
            self._start_session()
            for block_idx in range(self.n_blocks):
                self.run_block(block_idx)
            self.logger.ok("Task completed successfully.")
        except (KeyboardInterrupt, SystemExit):
            self.logger.warn("Manual interruption.")
        except Exception as e:
            self.logger.err(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            self._close_camera()
            saved_path = self._end_session()
        return saved_path