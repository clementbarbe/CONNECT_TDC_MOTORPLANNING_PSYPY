# tasks/_calibration_ui.py
"""
Script standalone lancé en subprocess par CameraCalibrationTask.
Crée sa propre QApplication — aucun conflit avec le process principal.

Usage interne (ne pas appeler directement) :
    python _calibration_ui.py --type table --camera 0
                               --nom X --session 1 --output /tmp/res.json [--flip]
"""
import sys
import os
import json
import argparse

import cv2
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui  import QImage, QPixmap


# ── Résolution imposée à la caméra ───────────────────────────────────────────
CAMERA_W = 1920
CAMERA_H = 1080
CAMERA_FPS = 10

# ── Configurations physiques ──────────────────────────────────────────────────
CALIBRATION_CONFIGS = {
    "table": {
        "label": "Table",
        "physical_points": [
            {"id": 1, "name": "Haut-Gauche", "x_mm":   0.0, "y_mm":   0.0, "x_rel": 0.15, "y_rel": 0.15},
            {"id": 2, "name": "Haut-Droit",  "x_mm": 400.0, "y_mm":   0.0, "x_rel": 0.85, "y_rel": 0.15},
            {"id": 3, "name": "Bas-Droit",   "x_mm": 400.0, "y_mm": 300.0, "x_rel": 0.85, "y_rel": 0.85},
            {"id": 4, "name": "Bas-Gauche",  "x_mm":   0.0, "y_mm": 300.0, "x_rel": 0.15, "y_rel": 0.85},
        ],
    },
    "plateau": {
        "label": "Plateau",
        "physical_points": [
            {"id": 1, "name": "Haut-Gauche", "x_mm":   0.0, "y_mm":   0.0, "x_rel": 0.15, "y_rel": 0.15},
            {"id": 2, "name": "Haut-Droit",  "x_mm": 200.0, "y_mm":   0.0, "x_rel": 0.85, "y_rel": 0.15},
            {"id": 3, "name": "Bas-Droit",   "x_mm": 200.0, "y_mm": 150.0, "x_rel": 0.85, "y_rel": 0.85},
            {"id": 4, "name": "Bas-Gauche",  "x_mm":   0.0, "y_mm": 150.0, "x_rel": 0.15, "y_rel": 0.85},
        ],
    },
}

RATIO     = 0.8
DISPLAY_W = round(CAMERA_W * RATIO)   # 1536
DISPLAY_H = round(CAMERA_H * RATIO)   # 864


def _open_camera(index: int) -> cv2.VideoCapture:
    """Ouvre la caméra et force la résolution 1920×1080 @ 30 fps."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return cap                          # l'appelant vérifie isOpened()

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAMERA_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_H)
    cap.set(cv2.CAP_PROP_FPS,          CAMERA_FPS)

    # Vérification : log si la caméra n'a pas accepté la résolution demandée
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (actual_w, actual_h) != (CAMERA_W, CAMERA_H):
        print(
            f"[CALIB] Résolution demandée {CAMERA_W}×{CAMERA_H}, "
            f"obtenue {actual_w}×{actual_h} (caméra non compatible ?)",
            file=sys.stderr,
        )

    return cap


class CalibrationWindow(QMainWindow):

    def __init__(self, camera, cal_type, nom, session, flip_feed, output_path):
        super().__init__()
        self.camera      = camera
        self.config      = CALIBRATION_CONFIGS[cal_type]
        self.cal_type    = cal_type
        self.nom         = nom
        self.session     = session
        self.flip_feed   = flip_feed
        self.output_path = output_path
        self.confirmed   = False

        # Positions des 4 croix en pixels d'affichage
        self.dot_px = [
            (int(p["x_rel"] * DISPLAY_W), int(p["y_rel"] * DISPLAY_H))
            for p in self.config["physical_points"]
        ]

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(33)   # ~30 fps

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle(f"Calibration — {self.config['label']}")
        self.setStyleSheet("background:#1a1a1a; color:white;")

        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        # Titre
        title = QLabel(f"CALIBRATION  —  {self.config['label'].upper()}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size:16px; font-weight:bold; color:#FFE066; padding:6px;"
        )
        lay.addWidget(title)

        # Résolution & instruction
        res_label = QLabel(
            f"Flux caméra : {CAMERA_W}×{CAMERA_H} px  "
            f"(affiché à {DISPLAY_W}×{DISPLAY_H})"
        )
        res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        res_label.setStyleSheet("font-size:11px; color:#88aaff; padding:2px;")
        lay.addWidget(res_label)

        instr = QLabel(
            "Ajustez physiquement la caméra jusqu'à ce que les croix rouges\n"
            "coïncident exactement avec vos marqueurs, puis cliquez sur Confirmer."
        )
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instr.setStyleSheet("font-size:12px; color:#cccccc; padding:4px;")
        lay.addWidget(instr)

        # Flux caméra
        self.feed_label = QLabel()
        self.feed_label.setFixedSize(DISPLAY_W, DISPLAY_H)
        self.feed_label.setStyleSheet("background:black; border:1px solid #444;")
        lay.addWidget(self.feed_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Boutons
        row = QHBoxLayout()
        btn_ok = QPushButton("✓  Confirmer  [Entrée]")
        btn_ok.setStyleSheet(
            "background:#2a7a2a; color:white; font-weight:bold;"
            "padding:8px 28px; font-size:13px;"
        )
        btn_ok.clicked.connect(self._confirm)

        btn_cancel = QPushButton("✕  Annuler  [Échap]")
        btn_cancel.setStyleSheet(
            "background:#7a2a2a; color:white; padding:8px 28px; font-size:13px;"
        )
        btn_cancel.clicked.connect(self.close)

        row.addStretch()
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        row.addStretch()
        lay.addLayout(row)

        self.adjustSize()

    # ── Clavier ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        k = event.key()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm()
        elif k == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    # ── Affichage ─────────────────────────────────────────────────────────────

    def _update_frame(self):
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return
        if self.flip_feed:
            frame = cv2.flip(frame, 0)

        display = cv2.resize(frame, (DISPLAY_W, DISPLAY_H))
        self._draw_overlay(display)

        rgb  = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self.feed_label.setPixmap(QPixmap.fromImage(qimg))

    def _draw_overlay(self, frame):
        """Dessine les 4 croix rouges + labels sur le frame (in-place)."""
        for i, (x, y) in enumerate(self.dot_px):
            p = self.config["physical_points"][i]

            # Grande croix blanche
            cross_size = 15
            cv2.line(frame, (x - cross_size, y),      (x + cross_size, y),      (255, 255, 255), 1, cv2.LINE_AA)
            cv2.line(frame, (x,      y - cross_size),  (x,      y + cross_size), (255, 255, 255), 1, cv2.LINE_AA)

            # Cercle rouge + contour blanc
            circle_size = 5
            cv2.circle(frame, (x, y), circle_size, (0,   0,   255), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), circle_size, (255, 255, 255),  2, cv2.LINE_AA)

            # Label avec ombre
            label = (
                f"{p['id']}  {p['name']}"
                f"  ({p['x_mm']:.0f}, {p['y_mm']:.0f} mm)"
            )
            tx, ty = x + 18, y - 5
            cv2.putText(frame, label, (tx + 1, ty + 1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.47, (0, 0, 0),       2, cv2.LINE_AA)
            cv2.putText(frame, label, (tx, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.47, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Confirmation ──────────────────────────────────────────────────────────

    def _confirm(self):
        self._timer.stop()

        # Dimensions natives de la caméra pour la conversion pixel → mm
        actual_w = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # Fallback si la propriété retourne 0
        if actual_w == 0 or actual_h == 0:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                actual_h, actual_w = frame.shape[:2]
            else:
                actual_w, actual_h = CAMERA_W, CAMERA_H

        sx = actual_w / DISPLAY_W
        sy = actual_h / DISPLAY_H
        img_px = [[int(x * sx), int(y * sy)] for (x, y) in self.dot_px]
        phys   = self.config["physical_points"]

        # Homographie pixels caméra → mm
        homography = None
        try:
            src = np.array(img_px,                                  dtype=np.float32)
            dst = np.array([[p["x_mm"], p["y_mm"]] for p in phys], dtype=np.float32)
            H, _ = cv2.findHomography(src, dst)
            if H is not None:
                homography = H.tolist()
        except Exception as exc:
            print(f"[CALIB] Homography failed: {exc}", file=sys.stderr)

        result = {
            "calibration_type": self.cal_type,
            "label"           : self.config["label"],
            "nom"             : self.nom,
            "session"         : self.session,
            "image_points_px" : img_px,
            "physical_points" : phys,
            "homography"      : homography,
            "frame_size"      : [actual_w, actual_h],
            "flip_feed"       : self.flip_feed,
            "timestamp"       : datetime.now().strftime("%Y-%m-%d_%H:%M:%S.%f"),
        }

        with open(self.output_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)

        self.confirmed = True
        self.close()

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)


# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type",    required=True, choices=["table", "plateau"])
    ap.add_argument("--camera",  type=int, default=0)
    ap.add_argument("--nom",     default="unknown")
    ap.add_argument("--session", default="1")
    ap.add_argument("--output",  required=True)
    ap.add_argument("--flip",    action="store_true")
    args = ap.parse_args()

    # ── Ouverture caméra avec résolution forcée ────────────────────────────
    cap = _open_camera(args.camera)

    if not cap.isOpened():
        print(f"[CALIB] Cannot open camera {args.camera}", file=sys.stderr)
        sys.exit(1)

    ret, _ = cap.read()
    if not ret:
        cap.release()
        print("[CALIB] Camera read failed", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    win = CalibrationWindow(
        camera=cap,
        cal_type=args.type,
        nom=args.nom,
        session=args.session,
        flip_feed=args.flip,
        output_path=args.output,
    )
    win.show()
    win.raise_()
    win.activateWindow()
    app.exec()

    cap.release()
    sys.exit(0 if win.confirmed else 1)